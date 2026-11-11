"""Admit the X14f extension in the shared X14f ledger."""
import argparse
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import admit_x14 as common
import x14f_ops as f


ROOT=f.ROOT
SOURCE=Path(__file__).resolve().parent
RESERVE=4


def formal_timing(config):
    receipt=f.read(ROOT/'f-receipt-f-full-pilot-DONE.json')
    rows=f.allocations(receipt['job'])
    assert len(rows)==2 and all(r['state']=='COMPLETED' and r['exitcode']=='0:0' for r in rows)
    rules=f.read(SOURCE/'RESOURCE_HISTORY_FLOOR_X12.json')['rules']
    transitions=2*sum(row['primitive_per_arm_per_algorithm'] for row in config['all_schedules'])
    forecasts=[]
    for i,alg in enumerate(('NPG','PI')):
        prefix=ROOT/f'x14f-full-pilot-{i:03d}'
        p=json.loads(prefix.with_suffix('.jsonl').read_bytes().splitlines()[-1])
        assert p['kind']=='TASK_FINAL' and p['status']=='COMPLETE'
        assert (p['algorithm'],p['index'],p['system'],p['seed'])==(alg,i,9102,9801)
        assert len(p['paths'])==8 and p['observation_transitions']==transitions
        assert p['peak_RSS_KiB']<=.8*2*1024**2 and p['physical_store_files']==2
        assert p['archive_bytes']==prefix.with_suffix('.tar').stat().st_size
        floor=next(r['reference_seconds_per_transition'] for r in rules if r['algorithm']==alg)*transitions
        forecasts.append(dict(algorithm=alg,measured_body_seconds=p['body_seconds'],historical_floor_seconds=floor,
                              effective_body_seconds=max(p['body_seconds'],floor),archive_bytes=p['archive_bytes'],
                              peak_RSS_KiB=p['peak_RSS_KiB']))
    return forecasts


def main(stage,check):
    key=f'f-full-{stage}'
    receipt_paths=[ROOT/f'f-receipt-{key}-{suffix}.json' for suffix in ('BEGIN','RESPONSE','DONE')]
    assert not any(p.exists() for p in receipt_paths), 'Reconcile earlier attempt first.'
    assert not f.call('sacct','-X','-n','-P','-u','changze','-S','2026-11-08','--name=x14-'+key,'--format=JobID').strip()
    books=f.history()
    assert common.history()['outstanding_upper_SU']==0
    cfg=f.read(SOURCE/'config-x14f-full-v1.json')
    plan=None
    if stage=='pilot':
        assert (ROOT/'f-receipt-f-formal-DONE.json').is_file()
        tasks,minutes=2,160
        expected=tasks*minutes/60+105
    elif stage=='formal':
        assert (ROOT/'x14f-report/REPORT_DONE.json').is_file() and books['outstanding_upper_SU']==0
        tasks=64
        plan=formal_timing(cfg)
        minutes=math.ceil((1.2*max(r['effective_body_seconds'] for r in plan)+30)/60)
        expected=32*sum(r['effective_body_seconds']+30 for r in plan)/3600
    else:
        assert (ROOT/'f-receipt-f-full-formal-DONE.json').is_file() and books['outstanding_upper_SU']==0
        tasks,minutes=1,25
        expected=tasks*minutes/60
    requested=tasks*minutes/60
    spent=books['settled_SU']+books['outstanding_upper_SU']
    projected=spent+expected+RESERVE
    exposure=spent+requested+RESERVE
    assert projected<=250 and exposure<=320 and exposure-RESERVE<=250, (projected,exposure)
    queue=f.call('squeue','-r','-h','-u','changze','-o','%i %T')
    available=64-len(queue.splitlines())
    assert available>=min(tasks,2) if stage=='pilot' else available>=1
    throttle=min(available,tasks)
    balance=f.call('myproject')
    acct=next(row.split('|') for row in balance.splitlines() if '|'+common.ACCOUNT+'|' in row)
    assert float(acct[6])>=requested+RESERVE
    size=64*2**20 if plan is None else math.ceil(1.5*max(r['archive_bytes'] for r in plan))+2**20
    quota=common.quota(24*tasks+128,(size+64*2**20)*tasks+512*2**20)
    script=SOURCE/f'{key}.sbatch'
    assert script.is_file()
    cmd=['sbatch','--parsable',f'--account={common.ACCOUNT}','--partition=medium','--ntasks=1','--cpus-per-task=1',
         '--mem=2048M',f'--time={minutes}','--no-requeue','--job-name=x14-'+key,f'--array=0-{tasks-1}%{throttle}',
         f'--output={ROOT}/x14f-full-{stage}-%A_%a.out',str(script)]
    receipt=dict(item='f-full',stage=stage,tasks=tasks,minutes=minutes,requested_SU=requested,exposure_SU=exposure,
                 expected_actual_SU=projected,timing=plan,books=books,quota=quota,balance=balance,own_queue=queue,
                 command=cmd,utc=datetime.now(timezone.utc).isoformat())
    if check:
        print(json.dumps(receipt))
        return
    begin,response,done=receipt_paths
    f.write(begin,receipt)
    job=subprocess.run(cmd,text=True,capture_output=True)
    f.write(response,dict(stdout=job.stdout,stderr=job.stderr,returncode=job.returncode))
    assert job.returncode==0 and re.fullmatch(r'\d+(;\S+)?',job.stdout.strip()), 'Reconcile Slurm before any new attempt.'
    result=dict(receipt,job=job.stdout.strip().split(';')[0],status='SUBMITTED_ONCE')
    f.write(done,result)
    print(json.dumps({k:result[k] for k in ('status','job','tasks','minutes','requested_SU','exposure_SU','expected_actual_SU')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['pilot','formal','report'])
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    main(args.stage,args.check)
