"""Resource admission for the X14c and X14d fixed-gain stages."""
import argparse
import json
import math
import re
import subprocess
from datetime import datetime, timezone

import admit_x14 as admission


R = admission.ROOT
SHAPES = {('c','pilot'):(1,5),('d','pilot'):(2,6),('d','formal'):(32,None),('d','report'):(1,5)}


def formal_timing():
    pilot=admission.read(R/'submit-d-pilot-DONE.json')
    rows=admission.allocations(pilot['job'])
    assert len(rows)==2 and all(r['state']=='COMPLETED' and r['exitcode']=='0:0' for r in rows)
    metrics=[]
    for index in range(2):
        prefix=R/f'x14d-pilot-{index:03d}'
        final=json.loads(prefix.with_suffix('.jsonl').read_bytes().splitlines()[-1])
        assert final['kind']=='TASK_FINAL' and final['status']=='COMPLETE' and final['role']=='timing'
        assert final['index']==index and final['system']==9101+index and final['seed']==9601+index
        assert final['peak_RSS_KiB']<=.8*2*1024**2
        assert final['physical_store_files']==2 and final['archive_bytes']==prefix.with_suffix('.tar').stat().st_size
        metrics.append({k:final[k] for k in ('body_seconds','peak_RSS_KiB','archive_bytes','index')})
    body=max(r['body_seconds'] for r in metrics)
    return dict(body_seconds=body,minutes=math.ceil((1.20*body+30)/60),metrics=metrics)


def main(item,stage,check):
    tasks,minutes=SHAPES[item,stage]
    key=f'{item}-{stage}'
    begin,response,done=(R/f'submit-{key}-{suffix}.json' for suffix in ('BEGIN','RESPONSE','DONE'))
    assert not any(p.exists() for p in (begin,response,done)), 'Reconcile existing submission receipts.'
    assert not admission.call('sacct','-X','-n','-P','-u','changze','-S','2026-11-08',
                              '--name=x14-'+key,'--format=JobID').strip()
    previous={('c','pilot'):('b','report'),('d','pilot'):('c','pilot'),
              ('d','formal'):('d','pilot'),('d','report'):('d','formal')}[item,stage]
    prior=admission.read(R/f'submit-{previous[0]}-{previous[1]}-DONE.json')
    books=admission.history()
    assert books['outstanding_upper_SU']==0 and prior['job'] in {row['job'] for row in books['jobs']}
    timing=formal_timing() if stage=='formal' else None
    if timing:
        minutes=timing['minutes']
    requested=tasks*minutes/60
    expected_body=(timing['body_seconds']+30)*tasks/3600 if timing else requested
    future={('c','pilot'):5,('d','pilot'):5,('d','formal'):1/12,('d','report'):0}[item,stage]
    exposure=books['settled_SU']+books['outstanding_upper_SU']+requested+admission.REPORT_RESERVE
    projected=books['settled_SU']+expected_body+future+admission.REPORT_RESERVE
    assert projected<=60 and exposure<=80 and exposure-admission.REPORT_RESERVE<=60, (projected,exposure)
    queue=admission.call('squeue','-r','-h','-u','changze','-o','%i %T')
    concurrency=min(64-len(queue.splitlines()),tasks)
    assert concurrency>=1
    balance=admission.call('myproject')
    acct=next(line.split('|') for line in balance.splitlines() if '|'+admission.ACCOUNT+'|' in line)
    assert float(acct[6])>=requested+admission.REPORT_RESERVE
    quota=admission.quota(24*tasks+128,68*2**20*tasks+256*2**20)
    script=R/f'estimation-v1/{key}.sbatch'
    assert script.is_file()
    cmd=['sbatch','--parsable',f'--account={admission.ACCOUNT}','--partition=medium','--ntasks=1','--cpus-per-task=1',
         '--mem=2048M',f'--time={minutes}','--no-requeue',f'--job-name=x14-{key}',f'--array=0-{tasks-1}%{concurrency}',
         f'--output={R}/x14{item}-{stage}-%A_%a.out',str(script)]
    receipt=dict(item=item,stage=stage,tasks=tasks,minutes=minutes,requested_SU=requested,exposure_SU=exposure,
                 expected_actual_SU=projected,timing=timing,books=books,quota=quota,balance=balance,own_queue=queue,
                 command=cmd,utc=datetime.now(timezone.utc).isoformat())
    if check:
        print(json.dumps(receipt))
        return
    admission.write(begin,receipt)
    job=subprocess.run(cmd,text=True,capture_output=True)
    admission.write(response,dict(stdout=job.stdout,stderr=job.stderr,returncode=job.returncode))
    assert job.returncode==0 and re.fullmatch(r'\d+(;\S+)?',job.stdout.strip()), 'Reconcile before any new submission.'
    result=dict(receipt,job=job.stdout.strip().split(';')[0],status='SUBMITTED_ONCE')
    admission.write(done,result)
    print(json.dumps({k:result[k] for k in ('status','job','tasks','minutes','requested_SU','exposure_SU','expected_actual_SU')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('item',choices=['c','d'])
    parser.add_argument('stage',choices=['pilot','formal','report'])
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    main(args.item,args.stage,args.check)
