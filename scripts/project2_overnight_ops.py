"""Receipt-based bounded submission. Login-node work is stdlib planning only."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import time

NAME='project2-overnight-20261020'
BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results'/NAME
RELEASE=BASE/'releases'/NAME
PY='/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python'


def read(path): return json.loads(Path(path).read_text())


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def submit(receipt,key,mode,minutes,array=None,manifest=None,dependency=None):
    assert key not in receipt['jobs']
    write(OUT/'submission-formal.json',receipt)
    command=['sbatch','--parsable','-A','132685389143','-p','short','--exclude=c136,c294',
             '-t',str(minutes),'-J','p2-night-'+key,'-o',str(OUT/'logs'/(key+'-%A_%a.out'))]
    if array:command+=['--array',array]
    if dependency:command+=['--dependency',dependency]
    command += [str(RELEASE/'slurm/project2_overnight.sbatch'),mode,str(manifest or OUT/'formal_plan.json')]
    job=subprocess.check_output(command,cwd=RELEASE,universal_newlines=True).strip()
    assert job.isdigit(),job
    receipt['jobs'][key]=job;write(OUT/'submission-formal.json',receipt)
    return job


def plan():
    assert not (OUT/'formal_plan.json').exists(),'Plan exists; inspect receipt'
    assert read(OUT/'verification.json')['status']=='PASS'
    pilot=[read(p) for p in sorted((OUT/'actor').glob('pilot-*.json'))]
    assert len(pilot)==18
    cfg=read(RELEASE/'configs/project2_overnight_20261020.json')
    tasks=[]
    for seed in range(101,109):
        for count in (131072,262144,524288):
            for method in ('dense','known_rank','adaptive'):
                tasks.append(dict(id=len(tasks),tag='formal',n=50,m=50,r=4,seed=seed,
                    trial=0,N=count,H=16,burn=512,updates=6,method=method))
    cfg['actor_tasks']=tasks
    cases=[dict(n=50,m=50,r=4,H=16,policy='Kstar',replicates=40,family='isotropic')]
    cases += [dict(n=n,m=n,r=4,H=16,policy='Kstar',replicates=10,family='isotropic') for n in (25,100)]
    cases += [dict(n=50,m=50,r=r,H=16,policy='Kstar',replicates=10,family='isotropic') for r in (1,2,8,16)]
    cases += [dict(n=50,m=50,r=4,H=h,policy='Kstar',replicates=10,family='isotropic') for h in (4,8,32)]
    cases += [dict(n=30,m=m,r=4,H=16,policy='Kstar',replicates=10,family='rectangular') for m in (8,16,32,64,128)]
    cases += [dict(n=50,m=50,r=4,H=16,policy='K0',replicates=10,family='isotropic')]
    mech=[]
    for case in cases:
        for seed in range(6101,6105):
            for trial in range(case['replicates']):
                mech.append(dict(id=len(mech),n=case['n'],m=case['m'],r=case['r'],H=case['H'],
                    family=case['family'],policy=case['policy'],seed=seed,trial=trial,
                    budgets=[8192,32768,131072],burn=512))
    cfg['mechanism_tasks']=mech
    assert len(mech)==760
    wall=max(3,math.ceil((2.0*max(d['seconds'] for d in pilot)+45)/60))
    assert wall<=5
    bounds=dict(initial_verification_saved_pilot=2.7333333333333334,
        formal_actor=len(tasks)*wall/60,mechanism_preflight=.15,
        formal_mechanism=len(mech)*2/60,report_and_audit=1.,recovery_reserve=3.)
    total=sum(bounds.values());assert total<100
    cfg['frozen_epoch']=time.time();cfg['resources']=dict(actor_wall_minutes=wall,
        mechanism_wall_minutes=2,cpus=1,memory_MiB=2048,maximum_concurrency=24,
        requested_SU_bounds=bounds,total_worst_case_SU_bound=total,
        automatic_retries=0,recovery_cap_SU=3.,measured_pilot_max_seconds=max(d['seconds'] for d in pilot))
    cfg['pilot_observations']=[dict(spec=d['spec'],status=d['status'],seconds=d['seconds'],last=d['rows'][-1]) for d in pilot]
    write(OUT/'formal_plan.json',cfg)
    pre=dict(cfg);pre['output']=str(OUT/'mechanism-preflight')
    pre['mechanism_tasks']=[dict(id=i,n=n,m=m,r=4,H=16,family=family,policy='Kstar',
        seed=2797,trial=0,budgets=[8192,32768,131072],burn=512)
        for i,(n,m,family) in enumerate([(50,50,'isotropic'),(100,100,'isotropic'),(30,128,'rectangular')])]
    write(OUT/'mechanism_preflight_plan.json',pre)
    receipt=dict(status='formal_actor_and_mechanism_preflight_submitting',jobs={},
        formal_actor_tasks=len(tasks),formal_mechanism_tasks=len(mech),SU_bounds=bounds,
        total_worst_case_SU_bound=total,epoch=time.time())
    submit(receipt,'actor','actor',wall,'0-71%24')
    submit(receipt,'mechanism-preflight','mechanism',3,'0-2%3',OUT/'mechanism_preflight_plan.json')
    receipt['status']='formal_actor_and_mechanism_preflight_submitted';write(OUT/'submission-formal.json',receipt)
    print(json.dumps(receipt,indent=2))


def mechanism():
    receipt=read(OUT/'submission-formal.json');cfg=read(OUT/'formal_plan.json')
    assert 'mechanism' not in receipt['jobs'],'Already submitted; inspect receipt'
    checks=[read(p) for p in (OUT/'mechanism-preflight/mechanism').glob('task-*.json')]
    assert len(checks)==3 and all(len(d['noise'])==3 and len(d['rows'])==27 for d in checks)
    assert max(d['seconds'] for d in checks)<60
    write(OUT/'mechanism-preflight/acceptance.json',dict(status='PASS',
        tasks=[dict(spec=d['spec'],seconds=d['seconds'],physical_transitions=d['physical_transitions']) for d in checks],
        formal_resources='1CPU/2GiB, 120sec ceiling versus measured largest full task',epoch=time.time()))
    submit(receipt,'mechanism','mechanism',2,'0-759%24')
    receipt['status']='formal_actor_and_mechanism_submitted';write(OUT/'submission-formal.json',receipt)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['plan','mechanism']);a=p.parse_args()
    if a.phase=='plan':plan()
    else:mechanism()
