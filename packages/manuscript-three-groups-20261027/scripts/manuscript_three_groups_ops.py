"""Stdlib-only receipt-based scheduler; never replay an uncertain submission."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

NAME='manuscript-three-groups-20261027'
BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results'/NAME
RELEASE=BASE/'releases'/NAME
CAP=12.


def read(p):return json.loads(p.read_text())


def write(p,value):
    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(p)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['preflight','formal','report','status','account'])
    a=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True);(OUT/'logs').mkdir(exist_ok=True)
    if a.mode in ['status','account']:
        jobs=[str(v['job']) for p in OUT.glob('submission-*.json') if (v:=read(p)).get('job')]
        accounting=subprocess.check_output(['sacct','-X','-j',','.join(jobs),'-n','-P',
            '--format=JobIDRaw,JobName,State,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES'],text=True) if jobs else ''
        data=dict(jobs=jobs,accounting=accounting,raw_files=len(list((OUT/'raw').glob('*.json'))),
            expected_raw_files=576,epoch=time.time())
        if a.mode=='account':
            data['myproject']=subprocess.check_output(['myproject'],text=True)
            data['settled_account']=subprocess.check_output(['myproject','-j','132685389143'],text=True)
            write(OUT/'accounting.json',data)
        print(json.dumps(data,indent=2));return
    receipt_path=OUT/('submission-'+a.mode+'.json')
    assert not receipt_path.exists(),'Inspect remote receipt/job state; no blind replay'
    balance=subprocess.check_output(['myproject'],text=True)
    line=next(x for x in balance.splitlines() if '|132685389143|' in x)
    available=float(line.split('|')[6].strip());assert available>CAP
    (OUT/('balance-'+a.mode+'.txt')).write_text(balance)
    bundles=0;prediction=None
    if a.mode=='preflight':wall=10
    elif a.mode=='formal':
        pre=read(OUT/'preflight.json');assert pre['status']=='PASS'
        bench={(r['algorithm'],r['n']):r for r in pre['benchmarks']}
        # CE96 is a measured maximum, so charge all eight exact paths at that cost.
        prediction=8*bench['CE',96]['seconds']+4*bench['CE',16]['seconds']+12*bench['NPG',12]['seconds']
        startup=120.
        wall=max(5,math.ceil((2.0*prediction+startup)/60))
        bundles=24
        assert max(r['peak_rss_KiB'] for r in bench.values())<1500*1024
    else:
        assert len(list((OUT/'raw').glob('*.json')))==576,'All planned trajectories required'
        wall=10
    bound=max(1,bundles)*wall/60
    previous=sum(read(p)['requested_bound_core_hours'] for p in OUT.glob('submission-*.json'))
    assert previous+bound+(.5 if a.mode!='report' else 0)<CAP,(previous,bound,'12 core-hour cap')
    receipt=dict(mode=a.mode,job=None,epoch=time.time(),wall_minutes=wall,bundles=bundles,
        cpus=1,memory_MiB=2048,requested_bound_core_hours=bound,previous_bound=previous,
        cap_core_hours=CAP,predicted_seconds_per_bundle=prediction,available_balance=available,
        automatic_retries=0,scheduler_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    write(receipt_path,receipt)
    cmd=['sbatch','--parsable','-A','132685389143','-p','short','-t',str(wall),
        '-J','lqr3-'+a.mode,'-o',str(OUT/'logs'/(a.mode+'-%A_%a.out'))]
    if bundles:cmd+=['--array=0-23%12']
    cmd+=[str(RELEASE/'slurm/manuscript_three_groups.sbatch'),a.mode]
    receipt['command']=cmd;write(receipt_path,receipt)
    job=subprocess.check_output(cmd,cwd=RELEASE,text=True).strip();assert job.isdigit(),job
    receipt['job']=job;write(receipt_path,receipt);print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
