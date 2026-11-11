"""Independent resource and submission ledger for X14f."""
import argparse
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import admit_x14 as common


ROOT=common.ROOT
SOURCE=Path(__file__).resolve().parent
REPORT_RESERVE=4
read,write,call,allocations=common.read,common.write,common.call,common.allocations


def history():
    jobs=[]
    settled=outstanding=historical=0.
    for path in sorted(ROOT.glob('f-receipt-f-*-DONE.json')):
        receipt=read(path)
        rows=allocations(receipt['job'])
        assert len({r['id'] for r in rows})==len(rows)<=receipt['tasks']
        active={'RUNNING','PENDING','COMPLETING','CONFIGURING'}
        finished=[row for row in rows if row['state'] not in active]
        assert all(row['billing']==1 and row['state']=='COMPLETED' and row['exitcode']=='0:0' for row in finished), finished
        settled+=sum(row['elapsed_seconds']/3600 for row in finished)
        outstanding+=(receipt['tasks']-len(finished))*receipt['minutes']/60
        historical+=receipt['tasks']*receipt['minutes']/60
        jobs.append(dict(receipt,allocations=rows))
    return dict(settled_SU=settled,outstanding_upper_SU=outstanding,historical_requested_SU=historical,
                report_reserve_SU=REPORT_RESERVE,jobs=jobs)


def timing(transition_count):
    pilot=read(ROOT/'f-receipt-f-pilot-DONE.json')
    rows=allocations(pilot['job'])
    assert len(rows)==2 and all(r['state']=='COMPLETED' and r['exitcode']=='0:0' for r in rows)
    history=read(SOURCE/'RESOURCE_HISTORY_FLOOR_X12.json')
    forecasts=[]
    for i,alg in enumerate(('NPG','PI')):
        path=ROOT/f'x14f-pilot-{i:03d}'
        final=json.loads(path.with_suffix('.jsonl').read_bytes().splitlines()[-1])
        assert final['kind']=='TASK_FINAL' and final['status']=='COMPLETE'
        assert (final['algorithm'],final['system'],final['seed'],final['index'])==(alg,9102,9801,i)
        assert final['observation_transitions']==transition_count and len(final['paths'])==1
        assert final['peak_RSS_KiB']<=.8*2*1024**2
        assert final['physical_store_files']==2 and path.with_suffix('.tar').stat().st_size==final['archive_bytes']
        rule=next(r for r in history['rules'] if r['algorithm']==alg)
        floor=rule['reference_seconds_per_transition']*transition_count
        forecasts.append(dict(algorithm=alg,measured_body_seconds=final['body_seconds'],historical_floor_seconds=floor,
                              effective_body_seconds=max(final['body_seconds'],floor),peak_RSS_KiB=final['peak_RSS_KiB'],
                              archive_bytes=final['archive_bytes']))
    return forecasts


def main(stage,check):
    assert call('id','-un').strip()=='changze'
    key=f'f-{stage}'
    begin,response,done=(ROOT/f'f-receipt-{key}-{suffix}.json' for suffix in ('BEGIN','RESPONSE','DONE'))
    assert not any(p.exists() for p in (begin,response,done)), 'Reconcile prior attempts before mutation.'
    assert not call('sacct','-X','-n','-P','-u','changze','-S','2026-11-08','--name=x14-'+key,'--format=JobID').strip()
    books=history()
    assert books['outstanding_upper_SU']==0
    assert common.history()['outstanding_upper_SU']==0
    cfg=read(SOURCE/'config-x14f-v1.json')
    M=cfg['all_schedules'][0]['primitive_per_arm_per_algorithm']
    plan=None
    if stage=='pilot':
        assert not books['jobs']
        tasks,minutes=2,160
        expected=tasks*minutes/60
    elif stage=='formal':
        tasks=64
        plan=timing(2*M)
        minutes=math.ceil((1.20*max(r['effective_body_seconds'] for r in plan)+30)/60)
        expected=32*sum(r['effective_body_seconds']+30 for r in plan)/3600
    else:
        formal=read(ROOT/'f-receipt-f-formal-DONE.json')
        assert formal['tasks']==64 and (ROOT/'x14f-formal-063.tar').is_file()
        tasks,minutes=1,20
        expected=minutes/60
    requested=tasks*minutes/60
    exposure=books['settled_SU']+requested+REPORT_RESERVE
    projected=books['settled_SU']+expected+REPORT_RESERVE
    assert projected<=150 and exposure<=200 and exposure-REPORT_RESERVE<=150, (projected,exposure)
    queue=call('squeue','-r','-h','-u','changze','-o','%i %T')
    throttle=min(64-len(queue.splitlines()),tasks)
    assert throttle>=1
    balance=call('myproject')
    acct=next(line.split('|') for line in balance.splitlines() if '|'+common.ACCOUNT+'|' in line)
    assert float(acct[6])>=requested+REPORT_RESERVE
    quota=common.quota(24*tasks+128,128*2**20*tasks+512*2**20)
    script=SOURCE/f'{key}.sbatch'
    assert script.is_file()
    cmd=['sbatch','--parsable',f'--account={common.ACCOUNT}','--partition=medium','--ntasks=1','--cpus-per-task=1',
         '--mem=2048M',f'--time={minutes}','--no-requeue',f'--job-name=x14-{key}',f'--array=0-{tasks-1}%{throttle}',
         f'--output={ROOT}/x14f-{stage}-%A_%a.out',str(script)]
    receipt=dict(item='f',stage=stage,tasks=tasks,minutes=minutes,requested_SU=requested,exposure_SU=exposure,
                 expected_actual_SU=projected,timing=plan,books=books,quota=quota,balance=balance,own_queue=queue,
                 command=cmd,utc=datetime.now(timezone.utc).isoformat())
    if check:
        print(json.dumps(receipt))
        return
    write(begin,receipt)
    job=subprocess.run(cmd,text=True,capture_output=True)
    write(response,dict(stdout=job.stdout,stderr=job.stderr,returncode=job.returncode))
    assert job.returncode==0 and re.fullmatch(r'\d+(;\S+)?',job.stdout.strip()), 'Reconcile prior submission.'
    result=dict(receipt,job=job.stdout.strip().split(';')[0],status='SUBMITTED_ONCE')
    write(done,result)
    print(json.dumps({k:result[k] for k in ('status','job','tasks','minutes','requested_SU','exposure_SU','expected_actual_SU')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['pilot','formal','report'])
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    main(args.stage,args.check)
