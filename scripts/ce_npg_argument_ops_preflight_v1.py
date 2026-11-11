"""Receipt-first scheduler with measured total cost and a 12 allocated-core-hour cap."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from ce_npg_argument_grid import NAME,BASE,OUT,RELEASE,all_specs,bundles

CAP=12.
ACCOUNT='132685389143'


def read(path):return json.loads(path.read_text())


def write(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(path)


def records():return [read(p) for p in OUT.glob('submission-*.json')]


def status(account=False):
    previous=records();jobs=[str(r['job']) for r in previous if r.get('job')]
    accounting=subprocess.check_output(['sacct','-X','-j',','.join(jobs),'-n','-P',
        '--format=JobIDRaw,JobName,State,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES'],text=True) if jobs else ''
    used=0.;states=[]
    for line in accounting.splitlines():
        cols=line.split('|')
        if len(cols)>=7:
            used+=float(cols[3])*int(cols[4])/3600
            states.append(cols[2])
    data=dict(study=NAME,jobs=jobs,accounting=accounting,allocated_core_hours_so_far=used,
        raw_completed=len([p for p in (OUT/'raw').glob('*.json') if '.checkpoint.' not in p.name]),
        expected_new=1728,formal_requested=any(r.get('mode')=='formal' for r in previous),
        all_allocations_complete=bool(states) and all(s=='COMPLETED' for s in states),epoch=time.time())
    if account:
        data['myproject']=subprocess.check_output(['myproject'],text=True)
        data['settled_account']=subprocess.check_output(['myproject','-j',ACCOUNT],text=True)
        write(OUT/'accounting.json',data)
    print(json.dumps(data,indent=2))


def measured_plan():
    pre=read(OUT/'preflight.json');assert pre['status']=='PASS' and pre['reused']==336
    assert max(b['peak_rss_KiB'] for b in pre['benchmarks'])<1500*1024
    by={}
    for b in pre['benchmarks']:
        # Never extrapolate a stopped short run as if it had completed its full assigned trajectory.
        factor=b['assigned_transitions']/max(1,b['actual_transitions'])
        key=(b['algorithm'],b['n'])
        by[key]=max(by.get(key,0.),b['seconds']*factor)
    estimates=[]
    for system,trial in bundles():
        seconds=0.;count=0
        for s in all_specs():
            if s['system']!=system or s['trial']!=trial or s['reuse_id'] is not None:continue
            key=(s['algorithm'],s['n'])
            if key not in by:
                # CE dimension12 and48 are reused; all new exact CE are dimension24.
                raise RuntimeError(('Unmeasured workload',key))
            seconds+=by[key];count+=1
        estimates.append(dict(system=system,trial=trial,seconds=seconds,new_trajectories=count))
    assert all(e['new_trajectories']==72 for e in estimates)
    wall=max(5,math.ceil((max(e['seconds'] for e in estimates)*1.35+60)/60))
    bound=wall*len(estimates)/60
    previous=sum(r['requested_bound_core_hours'] for r in records())
    data=dict(measured_seconds_by_algorithm_dimension={str(k):v for k,v in by.items()},bundles=estimates,
        predicted_formal_core_hours=sum(e['seconds'] for e in estimates)/3600,
        requested_wall_minutes=wall,requested_formal_bound_core_hours=bound,
        previous_requested_bound_core_hours=previous,report_and_reserve_core_hours=.75,
        total_requested_bound_with_reserve=previous+bound+.75,cap_core_hours=CAP)
    write(OUT/'resource-plan.json',data)
    assert previous+bound+.75<=CAP,('Measured complete grid does not fit cap; do not submit',data)
    return data


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['preflight','formal','report','plan','status','account'])
    args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True);(OUT/'logs').mkdir(exist_ok=True)
    if args.mode in ['status','account']:status(args.mode=='account');return
    if args.mode=='plan':print(json.dumps(measured_plan(),indent=2));return
    receipt_path=OUT/('submission-'+args.mode+'.json')
    assert not receipt_path.exists(),'Inspect receipt and scheduler before any uncertain submission replay'
    balance=subprocess.check_output(['myproject'],text=True)
    account_line=next(x for x in balance.splitlines() if '|'+ACCOUNT+'|' in x)
    available=float(account_line.split('|')[6].strip());assert available>CAP
    # Current user's jobs only; record already pending/running commitments alongside the balance.
    queue=subprocess.check_output(['squeue','-u','changze','-h','-o','%i|%j|%T|%C|%m|%L'],text=True)
    n_bundles=0;plan=None
    if args.mode=='preflight':wall=20
    elif args.mode=='formal':
        plan=measured_plan();wall=plan['requested_wall_minutes'];n_bundles=24
        assert read(OUT/'reuse-audit.json')['count']==336
    else:
        expected={s['id'] for s in all_specs() if s['reuse_id'] is None}
        found={p.stem for p in (OUT/'raw').glob('*.json') if '.checkpoint.' not in p.name}
        assert found==expected,('Incomplete formal grid',len(found),len(expected))
        wall=30
    bound=wall*max(1,n_bundles)/60
    previous=sum(r['requested_bound_core_hours'] for r in records())
    assert previous+bound+(.25 if args.mode!='report' else 0)<=CAP
    receipt=dict(mode=args.mode,job=None,epoch=time.time(),wall_minutes=wall,bundles=n_bundles,
        cpus=1,memory_MiB=2048,requested_bound_core_hours=bound,previous_requested_bound=previous,
        cap_core_hours=CAP,available_balance=available,current_user_queue=queue,balance_snapshot=balance,
        automatic_retries=0,scheduler_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),resource_plan=plan)
    write(receipt_path,receipt)
    cmd=['sbatch','--parsable','-A',ACCOUNT,'-p','short','-t',str(wall),
        '-J','lqrarg-'+args.mode,'-o',str(OUT/'logs'/(args.mode+'-%A_%a.out'))]
    if n_bundles:cmd+=['--array=0-23%12']
    cmd += [str(RELEASE/'slurm/ce_npg_argument.sbatch'),args.mode]
    receipt['command']=cmd;write(receipt_path,receipt)
    job=subprocess.check_output(cmd,cwd=RELEASE,text=True).strip();assert job.isdigit(),job
    receipt['job']=job;write(receipt_path,receipt);print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
