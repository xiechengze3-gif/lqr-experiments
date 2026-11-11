"""Submit after the pilot, allowing measured software startup latency."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    cfg=read(a.manifest);release=a.manifest.resolve().parents[1];out=Path(cfg['output'])
    assert read(out/'preflight.json')['status']=='PASS'
    pilot=read(out/'report-pilot/summary.json');audit=pilot['new_policy_audit']
    assert audit['unique_policies_reevaluated']==40 and audit['final_joint_OLS_recomputed']==5
    assert all(q['status']=='reached' for q in pilot['requirements'] if q['method']=='truncated')
    initial=read(out/'submission-initial.json');receipt=out/'submission-formal.json';assert not receipt.exists()
    ledger=subprocess.check_output(['sacct','-j',','.join(initial['jobs'].values()),'-n','-P',
        '--format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU,NNodes,TimelimitRaw,MaxRSS'],text=True)
    (out/'accounting').mkdir(exist_ok=True);(out/'accounting/pilot.psv').write_text(ledger)
    wall={}
    for line in ledger.splitlines():
        cols=line.split('|')
        if '.' not in cols[1] and '_' in cols[1]:
            assert cols[2]=='COMPLETED',cols
            wall[int(cols[1].split('_')[-1])]=int(cols[4])
    assert len(wall)==5
    rates=[];solvers=[];startup=[]
    for index,seed in enumerate(cfg['pilot_seeds']):
        r=read(out/'raw'/f'ce-r004-s{seed:04d}.json');timing=r['timings_this_invocation']
        rates.append(sum(q['collector_seconds'] for q in timing)/max(cfg['pilot_budgets']))
        solvers.append(sum(q['solve_and_save_seconds'] for q in timing)/len(timing))
        startup.append(max(0,wall[index]-r['seconds_this_invocation']))
    predicted=max(rates)*max(cfg['confirm_budgets'])+max(solvers)*len(cfg['confirm_budgets'])
    total=predicted+max(startup)
    assert total*1.1<1800,(total,'Formal resource review required')
    # Resource-only change: same CPU, memory, threads, data, identity and budgets.
    # Original bound 14.5 + 30 tasks * 5 extra minutes = 17 SU.
    # At most 5 manual 30-minute resumes leave the full worst-case bound <20 SU.
    resource_plan=dict(status='frozen_before_formal_sampling',reason='Measured library import/file-read latency before learner entry',
        original_formal_wall_minutes=25,formal_wall_minutes=30,cpus=1,memory_MiB=2048,
        initial_requested_SU_bound=17.0,total_with_5_maximum_manual_resumes_SU_bound=19.5,SU_cap=20,
        pilot_startup_seconds=startup,predicted_formal_learner_seconds_upper=predicted,
        predicted_formal_total_seconds_upper=total,scientific_config_and_sources_unchanged=True,
        module_read_block_observed='/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages/llvmlite/ir',
        diagnostic_steps='Read-only ps and import-only probes inside an existing allocation; zero trajectory transitions.')
    (out/'resource_plan.json').write_text(json.dumps(resource_plan,indent=2)+'\n')
    r=dict(status='submitting',jobs={},formal_tasks=30,formal_method_outputs=900,
        full_new_policy_recheck_count=900,automatic_retries=0,manual_resumes_overall_maximum=5,
        resource_plan=resource_plan,submitted_epoch=time.time(),submit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    def save():receipt.write_text(json.dumps(r,indent=2)+'\n')
    def submit(key,args):
        value=subprocess.check_output(['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short',
            '--exclude=c136,c294']+args,cwd=release,text=True).strip();assert value.isdigit(),repr(value)
        r['jobs'][key]=value;save();return value
    save();array=submit('formal',['-t','00:30:00','--array=0-29%30','-J','ce500-r4-confirm',
        '-o',str(out/'logs/confirm-%A_%a.out'),'slurm/ce500_rank4_extension.sbatch','task','confirm'])
    report=submit('formal_report',['-t','00:30:00','--dependency=afterok:'+array,'-J','ce500-r4-confirm-report',
        '-o',str(out/'logs/confirm-report-%j.out'),'slurm/ce500_rank4_extension.sbatch','confirm'])
    identification=submit('identification',['-t','00:10:00','--dependency=afterok:'+array,'-J','ce500-r4-identification',
        '-o',str(out/'logs/identification-%j.out'),'slurm/ce500_rank4_extension.sbatch','identification'])
    submit('archive',['-t','00:10:00','--dependency=afterok:'+report+':'+identification,'-J','ce500-r4-archive',
        '-o',str(out/'logs/archive-%j.out'),'slurm/ce500_rank4_archive.sbatch'])
    r['status']='submitted';save();print(json.dumps(r,indent=2))


if __name__=='__main__':main()
