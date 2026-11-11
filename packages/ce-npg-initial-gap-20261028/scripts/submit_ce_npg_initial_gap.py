"""Submit one bounded report-only job; never invoke learning or replay uncertain writes."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

BASE=Path('/scratch/user/changze/lqr_experiments')
NAME='ce-npg-initial-gap-20261028'
OUT=BASE/'results'/NAME
RELEASE=BASE/'releases'/NAME


def write(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(path)


def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'logs').mkdir(exist_ok=True)
    receipt=OUT/'submission.json';assert not receipt.exists(),'Read existing receipt/job; do not replay an uncertain submission'
    balance=subprocess.check_output(['myproject'],text=True)
    line=next(x for x in balance.splitlines() if '|132685389143|' in x)
    available=float(line.split('|')[6].strip());assert available>.1
    queue=subprocess.check_output(['squeue','-u','changze','-h','-o','%i|%j|%T|%C|%m|%L'],text=True)
    data=dict(status='SUBMITTING',job=None,operation='saved table report only',epoch=time.time(),cpus=1,memory_MiB=2048,
        wall_minutes=6,requested_core_hours=.1,available_balance=available,balance_snapshot=balance,
        current_user_queue=queue,new_learning_runs=0,new_training_transitions=0,automatic_retries=0,
        prior_study_actual_core_hours=5.870833333333334,
        prior_actual_plus_new_request_core_hours=5.970833333333334,
        source_sha256=hashlib.sha256((RELEASE/'scripts/ce_npg_initial_gap_postprocess.py').read_bytes()).hexdigest())
    write(receipt,data)
    cmd=['sbatch','--parsable','-A','132685389143','-p','short','-t','6','-J','lqr-relative',
        '-o',str(OUT/'logs/postprocess-%j.out'),str(RELEASE/'slurm/ce_npg_initial_gap.sbatch')]
    data['command']=cmd;write(receipt,data)
    job=subprocess.check_output(cmd,cwd=RELEASE,text=True).strip();assert job.isdigit(),job
    data.update(status='SUBMITTED',job=job);write(receipt,data);print(json.dumps(data,indent=2))


if __name__=='__main__':main()
