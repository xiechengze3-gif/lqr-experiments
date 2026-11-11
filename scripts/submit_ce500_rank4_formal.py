"""Measured rank-4 formal submission, preserving the old campaign unchanged."""
import argparse
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
    # Pilot endpoints must bracket the truncated targets; formal grid stays unchanged.
    assert all(q['status']=='reached' for q in pilot['requirements'] if q['method']=='truncated')
    collector=[];solver=[];max_elapsed=0
    for seed in cfg['pilot_seeds']:
        r=read(out/'raw'/f'ce-r004-s{seed:04d}.json');timing=r['timings_this_invocation']
        collector.append(sum(q['collector_seconds'] for q in timing)/max(cfg['pilot_budgets']))
        solver.append(sum(q['solve_and_save_seconds'] for q in timing)/len(timing))
        max_elapsed=max(max_elapsed,r['seconds_this_invocation'])
    predicted=max(collector)*max(cfg['confirm_budgets'])+max(solver)*len(cfg['confirm_budgets'])
    assert predicted*1.15 < cfg['resources']['formal_wall_minutes']*60,(predicted,'Review measured resources before submission')
    initial=read(out/'submission-initial.json');receipt=out/'submission-formal.json';assert not receipt.exists()
    parents=list(initial['jobs'].values())
    ledger=subprocess.check_output(['sacct','-j',','.join(parents),'-n','-P',
        '--format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU,NNodes,TimelimitRaw,MaxRSS'],text=True)
    (out/'accounting').mkdir(exist_ok=True);(out/'accounting/pilot.psv').write_text(ledger)
    r=dict(status='submitting',jobs={},pilot_max_elapsed_seconds=max_elapsed,predicted_formal_seconds_upper=predicted,
        requested_formal_wall_minutes=cfg['resources']['formal_wall_minutes'],SU_cap=20,
        formal_tasks=30,formal_method_outputs=900,full_new_policy_recheck_count=900,
        existing_fullrank_checks_reused_by_manifest=True,initial_requested_SU_bound=14.5,
        automatic_retries=0,manual_resumes_overall_maximum=5,submitted_epoch=time.time())
    def save():receipt.write_text(json.dumps(r,indent=2)+'\n')
    def submit(key,args):
        value=subprocess.check_output(['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short',
            '--exclude=c136,c294']+args,cwd=release,text=True).strip()
        assert value.isdigit(),repr(value)
        r['jobs'][key]=value;save();return value
    save();array=submit('formal',['-t','00:25:00','--array=0-29%30','-J','ce500-r4-confirm',
        '-o',str(out/'logs/confirm-%A_%a.out'),'slurm/ce500_rank4_extension.sbatch','task','confirm'])
    report=submit('formal_report',['-t','00:30:00','--dependency=afterok:'+array,'-J','ce500-r4-confirm-report',
        '-o',str(out/'logs/confirm-report-%j.out'),'slurm/ce500_rank4_extension.sbatch','confirm'])
    identification=submit('identification',['-t','00:10:00','--dependency=afterok:'+array,'-J','ce500-r4-identification',
        '-o',str(out/'logs/identification-%j.out'),'slurm/ce500_rank4_extension.sbatch','identification'])
    archive=submit('archive',['-t','00:10:00','--dependency=afterok:'+report+':'+identification,
        '-J','ce500-r4-archive','-o',str(out/'logs/archive-%j.out'),'slurm/ce500_rank4_archive.sbatch'])
    r['status']='submitted';save();print(json.dumps(r,indent=2))


if __name__=='__main__':main()
