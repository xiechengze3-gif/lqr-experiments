"""Receipt-based submission. Standard library only on login nodes."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import time

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/final-story-20261024'
RELEASE=BASE/'releases/final-story-20261024'
CAP=12.


def read(p):return json.loads(p.read_text())


def write(p,value):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(p)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','calibration','formal','report'])
    a=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True);(OUT/'logs').mkdir(exist_ok=True)
    receipt_path=OUT/('submission-'+a.mode+'.json')
    assert not receipt_path.exists(),'Inspect receipt/remote jobs; do not replay uncertain submissions'
    balance=subprocess.check_output(['myproject'],text=True)
    (OUT/('balance-'+a.mode+'.txt')).write_text(balance)
    line=next(x for x in balance.splitlines() if '|132685389143|' in x)
    available=float(line.split('|')[6].strip());assert available>CAP
    bundles=None
    prepare_receipt=OUT/'submission-prepare.json'
    startup_allowance=0.
    if a.mode!='prepare':
        prepare_job=read(prepare_receipt)['jobs']['prepare']
        elapsed=subprocess.check_output(['sacct','-X','-j',prepare_job,'-n','-P','--format=ElapsedRaw'],text=True)
        startup_allowance=max(60.,1.25*max(float(x.split('|')[0]) for x in elapsed.splitlines() if x.strip()))
    if a.mode=='prepare':wall=10;bound=10/60
    elif a.mode=='calibration':
        pre=read(OUT/'preflight.json');assert pre['status']=='PASS'
        b={x['algorithm']:x['seconds'] for x in pre['benchmarks']}
        assert all(x['status']=='complete' for x in pre['benchmarks']), 'Scientific benchmark failures are retained; review before production'
        bundles=4
        # Each bundle has 12 NPG paths; sum of budget-scaled work is 4 maxima.
        predicted=4*b['NPG']+b['CE']
        wall=max(3,math.ceil((2.2*predicted+startup_allowance)/60))
        assert wall<=20, 'Measured run would exceed the bounded calibration plan'
        bound=10/60+bundles*wall/60+5/60
    elif a.mode=='formal':
        selected=read(OUT/'threshold_frozen.json');assert set(selected['selection'])=={'NPG','CE'}
        pre=read(OUT/'preflight.json');b={x['algorithm']:x['seconds'] for x in pre['benchmarks']}
        bundles=24
        # Per formal seed: E1 8 NPG small +8 PI +4 CE, E2 44 NPG +1 CE.
        # NPG four-budget aggregate multiplier <1.329 per rank, 11 arms.
        predicted=8*b['NPG']/4 + 8*b['PI'] + 5*b['CE'] + 11*1.329*b['NPG']
        wall=max(5,math.ceil((2.5*predicted+startup_allowance)/60))
        previous=sum(read(p)['requested_bound_SU'] for p in OUT.glob('submission-*.json'))
        bound=bundles*wall/60
        assert previous+bound+1.<CAP,(previous,bound,wall,'exceeds total12 SU cap')
    else:wall=10;bound=wall/60
    receipt=dict(mode=a.mode,jobs={},epoch=time.time(),available_balance=available,
                 wall_minutes=wall,bundles=bundles,requested_bound_SU=bound,total_cap_SU=CAP,
                 cpus=1,memory_MiB=2048,automatic_retries=0,startup_allowance_seconds=startup_allowance,
                 scheduling_source_sha256=__import__('hashlib').sha256(Path(__file__).read_bytes()).hexdigest())
    write(receipt_path,receipt)
    cmd=['sbatch','--parsable','-A','132685389143','-p','short','--exclude=c136,c294',
         '-t',str(wall),'-J','p2-final-'+a.mode,'-o',str(OUT/'logs'/(a.mode+'-%A_%a.out'))]
    if bundles:cmd+=['--array=0-'+str(bundles-1)+'%12']
    cmd += [str(RELEASE/'slurm/final_story.sbatch'),a.mode]
    if bundles:cmd+=['--bundles',str(bundles)]
    job=subprocess.check_output(cmd,cwd=RELEASE,text=True).strip();assert job.isdigit(),job
    receipt['jobs'][a.mode]=job;write(receipt_path,receipt)
    if a.mode=='calibration':
        command=['sbatch','--parsable','-A','132685389143','-p','short','--exclude=c136,c294',
            '-t','5','--dependency=afterok:'+job,'-J','p2-final-freeze',
            '-o',str(OUT/'logs/freeze-%A_%a.out'),str(RELEASE/'slurm/final_story.sbatch'),'freeze']
        frozen_job=subprocess.check_output(command,cwd=RELEASE,text=True).strip();assert frozen_job.isdigit()
        receipt['jobs']['freeze']=frozen_job;write(receipt_path,receipt)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
