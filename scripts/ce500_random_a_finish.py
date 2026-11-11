"""Rebuild only the failed dependency chain after verified checkpoint completion."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def read(p):return json.loads(p.read_text())


def write(p,obj):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(p)


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    args=p.parse_args();cfg=read(args.manifest);out=Path(cfg['output'])
    plan=read(out/'formal_plan.json');formal=read(out/'submission-formal.json')
    ids=[formal['jobs']['rank_'+str(r)] for r in cfg['ranks']]
    recoveries=[read(q) for q in sorted(out.glob('submission-recovery-*.json'))]
    for q in recoveries:ids+=list(q['jobs'].values())
    txt=subprocess.check_output(['sacct','-j',','.join(ids),'-X','-n','-P',
        '--format=JobID,State,ElapsedRaw,AllocCPUS'],text=True)
    rows=[q.split('|') for q in txt.splitlines() if q]
    assert rows and all(q[1] in ('COMPLETED','TIMEOUT','FAILED','OUT_OF_MEMORY','CANCELLED') for q in rows)
    for r in cfg['ranks']:
        for seed in cfg['confirm_seeds']:
            raw=read(out/'raw'/f'ce-r{r:03d}-s{seed:04d}.json')
            assert raw['rank']==r and raw['seed']==seed
            assert raw['budgets']==plan['budgets_by_rank'][str(r)]
    recovery_cases=[c for q in out.glob('recovery-plan-*.json') for c in read(q)['cases']]
    assert len({c['task'] for c in recovery_cases})==len(recovery_cases)
    for c in recovery_cases:
        proof=read(out/'recovery-receipts'/f"ce-r{c['rank']:03d}-s{c['seed']:04d}.json")
        assert proof['status']=='complete' and proof['prior_rows_and_policy_hashes_preserved']
        assert proof['burn_repeated'] is False
    spent=plan['prior_allocated_core_hours']+sum(int(q[2] or 0)*int(q[3] or 0)/3600 for q in rows)
    bound=spent+3+1/3+1/3
    assert bound<60,(spent,bound)
    receipt_path=out/'submission-finish.json';assert not receipt_path.exists(),'Inspect existing receipt; never replay a submission blindly'
    receipt=dict(status='submitting',jobs={},epoch=time.time(),completed_formal_trajectories=150,
        one_time_resumed_trajectories=len(recovery_cases),measured_allocated_core_hours_before_final_audits=spent,
        final_audit_report_archive_SU_bound=11/3,total_revised_SU_bound=bound,cap=60,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    write(receipt_path,receipt)
    (out/'accounting/before-rebuilt-finish.psv').write_text(txt)
    numeric=args.manifest.resolve().parents[1]
    wrapper='/scratch/user/changze/lqr_experiments/releases/ce500-random-a-ops-v3/slurm/ce500_random_a_fixed.sbatch'
    def submit(key,opts):
        job=subprocess.check_output(['sbatch','--parsable','-A',cfg['resources']['account'],
            '-p','short','--exclude=c136,c189,c197,c258,c294']+opts,cwd=numeric,text=True).strip()
        assert job.isdigit();receipt['jobs'][key]=job;write(receipt_path,receipt);return job
    audit=submit('audits',['-t','00:30:00','--array=0-5%6','-J','ce500-rnda-audit-final',
        '-o',str(out/'logs/audit-%A_%a.out'),wrapper,'audit-shard'])
    report=submit('report',['-t','00:20:00','--dependency=afterok:'+audit,
        '-J','ce500-rnda-report-final','-o',str(out/'logs/confirm-report-%j.out'),wrapper,'confirm'])
    archive=Path(__file__).resolve().parents[1]/'slurm/ce500_random_a_archive.sbatch'
    submit('execution_audit_and_archive',['-t','00:20:00','--dependency=afterok:'+report,
        '-J','ce500-rnda-exec-archive','-o',str(out/'logs/archive-%j.out'),str(archive)])
    receipt['status']='submitted';write(receipt_path,receipt);print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
