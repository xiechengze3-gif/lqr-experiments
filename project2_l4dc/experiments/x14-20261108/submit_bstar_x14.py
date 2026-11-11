"""Submit the B* pilot-only calibration and its zero-sample report."""
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import admit_x14 as a


def main(stage):
    r=a.ROOT
    assert (r/'x14f-full-report/REPORT_DONE.json').is_file()
    assert a.call('id','-un').strip()=='changze'
    key=f'c-{stage}'
    previous='pilot' if stage=='bstar' else 'bstar'
    a.read(r/f'submit-c-{previous}-DONE.json')
    books=a.history()
    assert books['outstanding_upper_SU']==0
    begin,response,done=(r/f'submit-{key}-{s}.json' for s in ('BEGIN','RESPONSE','DONE'))
    assert not any(p.exists() for p in (begin,response,done)), 'Reconcile existing receipts.'
    assert not a.call('sacct','-X','-n','-P','-u','changze','-S','2026-11-08','--name=x14-'+key,'--format=JobID').strip()
    tasks,minutes=(8,6) if stage=='bstar' else (1,5)
    requested=tasks*minutes/60
    exposure=books['settled_SU']+requested+a.REPORT_RESERVE
    projected=exposure+5
    assert projected<=60 and exposure<=80
    queue=a.call('squeue','-r','-h','-u','changze','-o','%i %T')
    concurrency=min(tasks,64-len(queue.splitlines()))
    assert concurrency>=1
    balance=a.call('myproject')
    acct=next(row.split('|') for row in balance.splitlines() if '|'+a.ACCOUNT+'|' in row)
    assert float(acct[6])>=requested+a.REPORT_RESERVE
    quota=a.quota(24*tasks+128,68*2**20*tasks+256*2**20)
    script=Path(__file__).resolve().parent/f'{key}.sbatch'
    cmd=['sbatch','--parsable',f'--account={a.ACCOUNT}','--partition=medium','--ntasks=1','--cpus-per-task=1',
         '--mem=2048M',f'--time={minutes}','--no-requeue',f'--job-name=x14-{key}',f'--array=0-{tasks-1}%{concurrency}',
         f'--output={r}/x14c-{stage}-%A_%a.out',str(script)]
    receipt=dict(item='c',stage=stage,tasks=tasks,minutes=minutes,requested_SU=requested,exposure_SU=exposure,
                 expected_actual_SU=projected,books=books,own_queue=queue,balance=balance,quota=quota,command=cmd,
                 utc=datetime.now(timezone.utc).isoformat())
    a.write(begin,receipt)
    job=subprocess.run(cmd,text=True,capture_output=True)
    a.write(response,dict(stdout=job.stdout,stderr=job.stderr,returncode=job.returncode))
    assert job.returncode==0 and re.fullmatch(r'\d+(;\S+)?',job.stdout.strip()), 'Reconcile before submitting again.'
    result=dict(receipt,job=job.stdout.strip().split(';')[0],status='SUBMITTED_ONCE')
    a.write(done,result)
    print(json.dumps({k:result[k] for k in ('status','job','tasks','minutes','requested_SU','exposure_SU','expected_actual_SU')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['bstar','report'])
    main(parser.parse_args().stage)
