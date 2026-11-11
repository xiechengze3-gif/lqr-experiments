"""Submit measured, bounded sparse arrays and immutable per-five-seed bundles."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def read(path):return json.loads(path.read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    cfg=read(a.manifest);out=Path(cfg['output']);release=a.manifest.resolve().parents[1]
    plan=read(out/'formal_plan.json');assert plan['status']=='frozen' and plan['initial_total_SU_bound']<60
    assert read(out/'report-pilot/audit.json')['status']=='PASS'
    receipt=out/'formal_submission.json';assert not receipt.exists(),'Do not resubmit an existing campaign'
    result=dict(status='submitting',arrays_by_rank={},formal_plan_sha256=hashlib.sha256((out/'formal_plan.json').read_bytes()).hexdigest(),
        formal_paired_tasks=150,confirm_seeds=cfg['confirm_seeds'],budgets=plan['budgets'],bundle_jobs=[])
    def save():receipt.write_text(json.dumps(result,indent=2)+'\n')
    def submit(arguments):
        return subprocess.check_output(['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short']+arguments,
                                       universal_newlines=True,cwd=str(release)).strip()
    save();arrays={}
    for j,rank in enumerate(cfg['ranks']):
        indices=[i*len(cfg['ranks'])+j for i in range(len(cfg['confirm_seeds']))]
        array=submit(['-t','00:%02d:00'%plan['formal_wall_minutes_by_rank'][str(rank)],
            '--array='+','.join(str(i) for i in indices)+'%5','-J','ce500-confirm-r%d'%rank,
            '-o',str(out/'logs'/'confirm-%A_%a.out'),'slurm/ce500_matched_gap.sbatch','task','confirm',
            '--plan',str(out/'formal_plan.json')])
        arrays[rank]=array;result['arrays_by_rank'][str(rank)]=array;save()
    dependency='afterok:'+':'.join(arrays.values())
    result['formal_report']=submit(['-t','02:00:00','--dependency='+dependency,'-J','ce500-confirm-report',
        '-o',str(out/'logs'/'confirm-report-%j.out'),'slurm/ce500_report.sbatch','--phase','confirm','--plan',str(out/'formal_plan.json'),'--full-audit']);save()
    result['identification_audit']=submit(['-t','00:10:00','--dependency='+dependency,'-J','ce500-identification-audit',
        '-o',str(out/'logs'/'identification-audit-%j.out'),'slurm/ce500_identification_audit.sbatch','--phase','confirm']);save()
    archive_log=out.parent.parent/'accounting'/cfg['experiment']
    archive_log.mkdir(parents=True,exist_ok=True)
    for group in range(6):
        dep='afterok:'+':'.join(arrays[rank]+'_'+str(i*5+j) for i in range(group*5,(group+1)*5) for j,rank in enumerate(cfg['ranks']))
        job=submit(['-t','00:10:00','--dependency='+dep,'-J','ce500-archive-g%d'%group,
            '-o',str(archive_log/('formal-%02d-archive-%%j.out'%group)),
            'slurm/ce500_bundle.sbatch','--kind','formal','--group',str(group)])
        result['bundle_jobs'].append(dict(group=group,job_id=job));save()
    result['status']='submitted';save();print(json.dumps(result,indent=2))


if __name__=='__main__':main()
