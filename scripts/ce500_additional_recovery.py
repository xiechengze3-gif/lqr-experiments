"""Bounded same-code checkpoint resumes for two late c136 TIMEOUT attempts."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from ce500_recovery import metadata,read,sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--submit',action='store_true');a=p.parse_args()
    cfg=read(a.manifest);out=Path(cfg['output']);release=a.manifest.resolve().parents[1]
    recovery=read(out/'recovery_plan.json');assert not recovery.get('additional_cases')
    budgets=read(out/'formal_plan.json')['budgets'];cases=[]
    for task_id,failed in [(136,'20205931'),(141,'20205934')]:
        rank=cfg['ranks'][task_id%5];seed=cfg['confirm_seeds'][task_id//5]
        assert rank==8 and seed in (227,228)
        status=subprocess.check_output(['sacct','-j',failed,'-X','-n','-P','-o','JobIDRaw,State,ElapsedRaw'],universal_newlines=True).strip().split('|')
        assert status[1]=='TIMEOUT'
        stem=f'ce-r{rank:03d}-s{seed:04d}';cp=out/'checkpoints'/(stem+'.npz');meta=metadata(cp)
        assert meta['identity']==recovery['identity'] and meta['done'] in budgets[:-1]
        assert not (out/'raw'/(stem+'.json')).exists()
        assert len(meta['rows'])==2*sum(b<=meta['done'] for b in budgets)
        for row in meta['rows']:assert sha(out/row['policy_file'])==row['policy_sha256']
        next_budget=next(b for b in budgets if b>meta['done'])
        cases.append(dict(rank=rank,seed=seed,task_id=task_id,failed_job_id=failed,failed_elapsed_seconds=int(status[2]),
            checkpoint_sha256=sha(cp),committed_OLS_samples=meta['done'],committed_primitive_transitions=meta['done']+cfg['burn'],
            remaining_OLS_samples=budgets[-1]-meta['done'],
            discarded_uncommitted_transition_lower_bound=0,discarded_uncommitted_transition_upper_bound=next_budget-meta['done'],
            discarded_count_is_not_exact=True,last_committed_gaps={q['method']:q['gap'] for q in meta['rows'][-2:]},
            both_targets_attained_before_failure_for_this_seed=all(q['stable'] and q['gap']<=.05 for q in meta['rows'][-2:])))
    result=dict(status='verified',cases=cases,full_audit_scope_retained=4050,source_sha256=sha(Path(__file__)),
        resume_wall_minutes=15,resume_cpus=1,resume_memory_MiB=2048,resume_attempts_per_task=1,
        excluded_slow_nodes=['c136','c294'],sampling_and_numeric_sources_unchanged=True)
    (out/'additional_recovery_inspection.json').write_text(json.dumps(result,indent=2)+'\n')
    if a.submit:
        backups=out/'recovery_checkpoints';backups.mkdir(exist_ok=True)
        for case in cases:
            stem=f'ce-r{case["rank"]:03d}-s{case["seed"]:04d}'
            shutil.copyfile(out/'checkpoints'/(stem+'.npz'),backups/(stem+'-before-resume.npz'))
        command=['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short','-t','00:15:00','--exclude=c136,c294',
            '--array=136,141%2','-J','ce500-resume-r8-late','-o',str(out/'logs/resume-%A_%a.out'),
            'slurm/ce500_matched_gap.sbatch','task','confirm','--plan',str(out/'formal_plan.json')]
        job=subprocess.check_output(command,cwd=str(release),universal_newlines=True).strip();assert job.isdigit()
        for case in cases:case.update(resume_array=job,manual_resumes_for_task=1)
        recovery['additional_cases']=cases
        (out/'recovery_plan.json').write_text(json.dumps(recovery,indent=2)+'\n')
        formal=read(out/'formal_submission.json');formal['recovery_jobs'].append(job);formal['recovery_attempts']=3
        (out/'formal_submission.json').write_text(json.dumps(formal,indent=2)+'\n')
        result.update(status='submitted',resume_array=job)
        (out/'additional_recovery_submission.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
