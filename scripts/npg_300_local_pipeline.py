"""Continue automatically from corrected feasibility into frozen local calibration."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import psutil


def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');tmp.replace(path)


def run(out,project):
    out=Path(out);project=Path(project);frozen=project/'local_runs'/'npg300-20261009'
    status=out/'pipeline_status.json';started=time.monotonic()
    receipt=json.loads((project/'receipts'/'npg300-local-20261009-process.json').read_text())
    while True:
        path=out/'feasibility'/'feasibility.json'
        report=json.loads(path.read_text()) if path.exists() else {}
        if report.get('status')=='PASS':break
        if report.get('status') not in (None,'RUNNING'):
            raise RuntimeError('Feasibility did not pass: '+str(report.get('status')))
        if not psutil.pid_exists(receipt['pid']):
            raise RuntimeError('Feasibility process ended without PASS; inspect stderr.')
        if time.monotonic()-started>7200:raise TimeoutError('Feasibility wait exceeded two hours.')
        atomic(status,dict(status='WAITING_FOR_FEASIBILITY',pid=os.getpid(),
                           feasibility_elapsed_seconds=report.get('elapsed_seconds')))
        time.sleep(15)
    expected=hashlib.sha256((frozen/'engine'/'npg_300_feasibility.py').read_bytes()).hexdigest()
    assert report['source_sha256']==expected
    runner=frozen/'npg_300_local_study.py'
    runner_hash=hashlib.sha256(runner.read_bytes()).hexdigest()
    verified=json.loads((out/'resume_check'/runner_hash[:16]/'verification.json').read_text())
    assert verified['status']=='PASS' and verified['runner_sha256']==runner_hash
    config_path=out/'config.json'
    if not config_path.exists():
        measured=[r for r in report['benchmarks'] if r['n']==300]
        assert measured
        measured.sort(key=lambda r:r['N'])
        stable=all(m['one_update']['stable'] for m in measured[-1]['methods'])
        # A predeclared common floor, at least the largest measured prefix;
        # rank-4 one-update stability is calibration, not a guarantee at other ranks.
        floor=65536 if stable else 262144
        profiles={f'min-{floor}-final-{final}':dict(minimum_batch=floor,final_batch=final)
                  for final in (262144,1048576)}
        schedules={name:[max(floor,p['final_batch']//(2**(15-stage//16)))
                         for stage in range(256)] for name,p in profiles.items()}
        tasks=[]
        ranks=[1,4,16,64,300];systems=list(range(5));trials=[0,1]
        for trial in trials:
            for rank in ranks:
                for seed in systems:
                    tasks.append(dict(n=300,m=300,r=rank,system_seed=seed,trial_seed=trial,phase='critic'))
        for profile in profiles:
            for trial in trials:
                for rank in ranks:
                    for seed in systems:
                        tasks.append(dict(n=300,m=300,r=rank,system_seed=seed,trial_seed=trial,
                                          phase='actor',profile=profile))
        seconds_per_block=measured[-1]['collector_only_prefix_seconds']/measured[-1]['N']
        blocks=50*65536+sum(2*sum(schedules[t['profile']]) for t in tasks if t['phase']=='actor')
        config=dict(scope='Exploratory local 300d calibration, 5 independent systems x 2 collector trials.',
            n=300,ranks=ranks,system_seeds=systems,trial_seeds=trials,methods=['raw','truncated'],
            critic_prefixes=[4096,16384,65536],profiles=profiles,schedules=schedules,tasks=tasks,
            stages=256,epoch_length=16,horizon=16,burn=1024,sigma=1.,step_multiplier=2.,
            tolerances=[16.,8.,4.,2.,1.,.5,.25,.125],max_wall_hours=720,
            fixed_policy_budget_per_trial=1024+(65536+1)*16,
            timing_estimate=dict(seconds_per_block=seconds_per_block,
                collector_only_hours_if_all_arms_stay_stable=blocks*seconds_per_block/3600,
                caveats='Estimate excludes reference, evaluations, reports, laptop temperature/throttling, and replay. Failed arms use fewer samples.'),
            calibration_notes='Rank4 one-update benchmark chooses only a common safety floor; schedules frozen before actor learning. Five calibration seeds are exploratory, not held-out testing.',
            protocol='Paired innovations across rank/method/profile. Same predetermined budget both arms, no true-cost stopping. Fullrank equivalence; failures/censoring retained.',
            base_release='e93b7ffa7fca793e',runner_sha256=runner_hash)
        atomic(config_path,config)
        atomic(project/'receipts'/'npg300-local-20261009-design.json',dict(
            config=str(config_path),config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
            critic_tasks=50,actor_paired_tasks=100,**config['timing_estimate']))
    config=json.loads(config_path.read_text())
    assert config['runner_sha256']==runner_hash
    atomic(status,dict(status='CALIBRATION_RUNNING',pid=os.getpid(),tasks=len(config['tasks']),
                       config=str(config_path),timing_estimate=config['timing_estimate']))
    print(json.dumps(dict(status='CALIBRATION_RUNNING',timing_estimate=config['timing_estimate'])),flush=True)
    result=subprocess.run([sys.executable,'-u',str(runner),'--config',str(config_path),'--output',str(out)])
    if result.returncode:
        progress=json.loads((out/'study_progress.json').read_text())
        if progress['status']=='CHECKPOINTED_RUNTIME_LIMIT':
            atomic(status,dict(status='CHECKPOINTED_RUNTIME_LIMIT',pid=os.getpid(),
                               reason='30-day launch limit; resume with Start-Npg300Local.ps1 -Phase Study.'))
            return
        raise RuntimeError(f'Calibration worker exited {result.returncode}; checkpoints retained.')
    atomic(status,dict(status='COMPLETE',pid=os.getpid(),tasks=len(config['tasks'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--project',required=True)
    args=p.parse_args()
    try:run(args.output,args.project)
    except Exception as exc:
        atomic(Path(args.output)/'pipeline_status.json',dict(status='FAILED',error=str(exc),pid=os.getpid()))
        raise
