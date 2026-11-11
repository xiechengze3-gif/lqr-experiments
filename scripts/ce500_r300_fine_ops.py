"""Submit the bounded fine-grid supplement after measured main plan is saved."""
import argparse
import json
from pathlib import Path
import subprocess
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    cfg=json.loads(a.manifest.read_text());out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True);(out/'logs').mkdir(exist_ok=True)
    receipt_path=out/'submission.json';assert not receipt_path.exists(),'Inspect existing receipt, never replay uncertain submissions'
    mainplan=json.loads((Path(cfg['base_output'])/'formal_plan.json').read_text())
    combined=mainplan['total_worst_case_SU_bound']+cfg['supplement_worst_case_SU_bound']
    assert combined<85,(combined,mainplan)
    balance=subprocess.check_output(['myproject'],text=True);(out/'balance.txt').write_text(balance)
    line=next(x for x in balance.splitlines() if '|132685389143|' in x);available=float(line.split('|')[6].strip());assert available>85
    receipt=dict(status='planned',jobs={},epoch=time.time(),combined_total_worst_case_SU_bound=combined,
                 supplement_worst_case_SU_bound=cfg['supplement_worst_case_SU_bound'],balance_available=available,automatic_retries=0)
    def save():
        tmp=receipt_path.with_suffix('.tmp');tmp.write_text(json.dumps(receipt,indent=2)+'\n');tmp.replace(receipt_path)
    def submit(key,wall,mode,phase,array=None,dependency=None):
        cmd=['sbatch','--parsable','-A','132685389143','-p','short','-t',str(wall),'--exclude=c136,c294',
             '-J','ce300-fine-'+key,'-o',str(out/'logs'/(key+'-%A_%a.out'))]
        if array:cmd+=['--array='+array]
        if dependency:cmd+=['--dependency=afterok:'+dependency]
        cmd+=[str(a.manifest.resolve().parents[1]/'slurm/ce500_r300_fine.sbatch'),mode,'--phase',phase]
        receipt.update(status='submitting',pending_submission=dict(key=key,command=cmd));save()
        job=subprocess.check_output(cmd,text=True).strip();assert job.isdigit();receipt['jobs'][key]=job
        receipt.pop('pending_submission');receipt['status']='submitted';save();return job
    pilot=submit('pilot',12,'task','pilot',array='0-1%2')
    submit('pilot_report',5,'report','pilot',dependency=pilot)
    formal=submit('formal',12,'task','confirm',array='0-29%6')
    submit('formal_report',10,'report','confirm',dependency=formal)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
