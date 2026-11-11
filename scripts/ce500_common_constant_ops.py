"""Receipt-based bounded CE submissions; standard library, no model work."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import time


def read(p):return json.loads(p.read_text())


def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(p)


def balance(cfg,label):
    out=Path(cfg['output']);txt=subprocess.check_output(['myproject'],text=True)
    (out/('balance-'+label+'.txt')).write_text(txt)
    line=next(x for x in txt.splitlines() if '|'+cfg['resources']['account']+'|' in x)
    amount=float(line.split('|')[6].strip())
    assert amount>cfg['resources']['total_SU_cap']
    return amount


def ledger(cfg,label):
    out=Path(cfg['output']);ids=[]
    for p in out.glob('submission-*.json'):ids+=list(read(p)['jobs'].values())
    if not ids:return 0.
    txt=subprocess.check_output(['sacct','-j',','.join(ids),'-n','-P',
        '--format=JobIDRaw,JobID,State,ElapsedRaw,AllocCPUS,AllocTRES'],text=True)
    dest=out/'accounting';dest.mkdir(exist_ok=True);(dest/(label+'.psv')).write_text(txt)
    items={}
    for line in txt.splitlines():
        c=line.split('|')
        if len(c)>=6 and c[0] and '.' not in c[1]:
            assert int(c[4] or 0)==1 and 'billing=1' in c[5],line
            items[c[0]]=dict(job=c[1],state=c[2],elapsed=int(c[3] or 0),cpus=1,tres=c[5])
    spent=sum(x['elapsed']/3600 for x in items.values())
    write(dest/(label+'.json'),dict(allocated_core_hours=spent,own_jobs=list(items.values()),
        basis='current allocated billing=1, one CPU / 2GiB; AMS settlement recorded separately'))
    return spent


def submit(cfg,release,receipt,key,wall,mode,args=None,dependency=None,array=None):
    assert key not in receipt['jobs'];out=Path(cfg['output'])
    receipt['status']='submitting';write(out/receipt['filename'],receipt)
    cmd=['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short','-t',str(wall),
        '--exclude='+','.join(cfg['resources']['excluded_hosts']),'-J','ce500-common-'+key,
        '-o',str(out/'logs'/f'{key}-%A_%a.out')]
    if dependency:cmd+=['--dependency=afterok:'+dependency]
    if array:cmd+=['--array='+array]
    cmd+=[str(release/'slurm/ce500_common_constants.sbatch'),mode]+(args or [])
    job=subprocess.check_output(cmd,cwd=release,text=True).strip();assert job.isdigit(),job
    receipt['jobs'][key]=job;receipt['status']='submitted';write(out/receipt['filename'],receipt)
    return job


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','pilot','formal'])
    p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    cfg=read(a.manifest);out=Path(cfg['output']);(out/'logs').mkdir(parents=True,exist_ok=True)
    release=a.manifest.resolve().parents[1];filename='submission-'+a.mode+'.json'
    assert not (out/filename).exists(),'Inspect existing receipt; never replay an uncertain submission'
    available=balance(cfg,a.mode);spent=ledger(cfg,'before-'+a.mode)
    receipt=dict(filename=filename,jobs={},epoch=time.time(),balance_available=available,
        total_SU_cap=cfg['resources']['total_SU_cap'])
    if a.mode=='preflight':
        submit(cfg,release,receipt,'preflight',cfg['resources']['preflight_wall_minutes'],'prepare')
    elif a.mode=='pilot':
        pre=read(out/'preflight.json');assert pre['status']=='PASS'
        ratio=max(cfg['budgets'])/pre['benchmark_maximum_budget']
        predicted=max(sum(t['collector_seconds'] for t in x['timings'])*ratio+max(t['solve_and_save_seconds'] for t in x['timings'])*len(cfg['budgets']) for x in pre['benchmarks'])
        wall=max(5,math.ceil((1.6*predicted+120)/60))
        assert wall<=cfg['resources']['pilot_wall_minutes_maximum']
        tasks=len(cfg['ranks'])*len(cfg['pilot_seeds'])
        bound=spent+tasks*wall/60+cfg['resources']['report_wall_minutes']/60
        assert bound<cfg['resources']['total_SU_cap']
        receipt.update(tasks=tasks,wall_minutes=wall,requested_SU_bound=bound)
        job=submit(cfg,release,receipt,'pilot',wall,'task',['--phase','pilot'],array=f'0-{tasks-1}%10')
        submit(cfg,release,receipt,'pilot_report',cfg['resources']['report_wall_minutes'],'report',['--phase','pilot'],dependency=job)
    else:
        assert read(out/'report-pilot/summary.json')['status']=='complete'
        measurements=[]
        for rank in cfg['ranks']:
            data=[read(out/'raw'/f'ce-r{rank:03d}-s{s:04d}.json') for s in cfg['pilot_seeds']]
            wall=max(5,math.ceil((1.6*max(x['seconds_this_invocation'] for x in data)+120)/60))
            assert wall<=cfg['resources']['formal_wall_minutes_maximum']
            measurements.append(dict(rank=rank,wall_minutes=wall,pilot_max_seconds=max(x['seconds_this_invocation'] for x in data)))
        formal=len(cfg['confirm_seeds'])*sum(x['wall_minutes'] for x in measurements)/60
        bound=spent+formal+cfg['resources']['audit_shards']*cfg['resources']['audit_wall_minutes']/60+cfg['resources']['report_wall_minutes']/60+cfg['resources']['manual_recovery_SU_reserve']
        assert bound<cfg['resources']['total_SU_cap'],bound
        plan=dict(status='frozen_before_formal_sampling',budgets=cfg['budgets'],seeds=cfg['confirm_seeds'],
            absolute_targets=cfg['absolute_targets'],primary_absolute_target=cfg['primary_absolute_target'],supplied_common_bounds=cfg['supplied_common_bounds'],initial_gain='shared fixed-pole K0; identical F0/P0; p0=47',
            resource_measurements=measurements,prior_allocated_core_hours=spent,
            formal_requested_SU_bound=formal,total_worst_case_SU_bound=bound,
            science_grid_frozen_before_pilot=True,automatic_retries=0)
        write(out/'formal_plan.json',plan);receipt['plan']=plan
        jobs=[];size=len(cfg['confirm_seeds'])
        for i,m in enumerate(measurements):
            jobs.append(submit(cfg,release,receipt,'r'+str(m['rank']),m['wall_minutes'],'task',
                ['--phase','confirm'],array=f'{i*size}-{(i+1)*size-1}%4'))
        job=submit(cfg,release,receipt,'audits',cfg['resources']['audit_wall_minutes'],'audit',
            ['--phase','confirm'],dependency=':'.join(jobs),array='0-5%6')
        submit(cfg,release,receipt,'report',cfg['resources']['report_wall_minutes'],'report',
            ['--phase','confirm'],dependency=job)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
