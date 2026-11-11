"""Bounded, receipt-based submissions. Standard library; no login-node numerics."""
import argparse
import itertools
import json
import math
from pathlib import Path
import subprocess
import time


def read(p):return json.loads(p.read_text())


def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(p)


def stein_tasks(cfg,phase):
    return [dict(n=n,seed=seed,N=count,method=method) for n in cfg['dimensions']
        for seed in cfg[phase+'_system_seeds'] for count in cfg['PI'][phase+'_N'] for method in cfg['methods']]


def main():
    p=argparse.ArgumentParser();p.add_argument('study',choices=['ce','stein']);p.add_argument('phase',choices=['preflight','pilot','formal'])
    p.add_argument('--release',type=Path,required=True);a=p.parse_args()
    name='ce500' if a.study=='ce' else 'stein'
    cfg=read(a.release/'configs'/(name+'_independent_stabilizer_20261022.json'))
    out=Path(cfg['output']);(out/'logs').mkdir(parents=True,exist_ok=True)
    filename=out/('submission-'+a.phase+'-resources-v2.json');assert not filename.exists(),'Inspect prior receipt; never replay an uncertain submission'
    balance=subprocess.check_output(['myproject'],text=True);(out/('balance-'+a.phase+'.txt')).write_text(balance)
    line=next(x for x in balance.splitlines() if '|'+cfg['resources']['account']+'|' in x)
    available=float(line.split('|')[6]);assert available>cfg['resources']['total_SU_cap']
    ids=[]
    for receipt in out.glob('submission-*.json'):ids+=list(read(receipt)['jobs'].values())
    spent=0.;ledger=[]
    if ids:
        raw=subprocess.check_output(['sacct','-j',','.join(ids),'-n','-P','--format=JobIDRaw,JobID,State,ElapsedRaw,AllocCPUS,AllocTRES'],text=True)
        (out/('accounting-before-'+a.phase+'.psv')).write_text(raw)
        unique={}
        for row in raw.splitlines():
            c=row.split('|')
            if len(c)<6 or '.' in c[1] or not c[0]:continue
            assert int(c[4])==1 and 'billing=1' in c[5],row
            unique[c[0]]=dict(job=c[1],state=c[2],seconds=int(c[3]),tres=c[5])
        ledger=list(unique.values());spent=sum(x['seconds']/3600 for x in ledger)
    receipt=dict(status='planning',jobs={},study=a.study,phase=a.phase,epoch=time.time(),
        balance_available=available,prior_allocated_core_hours=spent,prior_own_jobs=ledger,
        total_SU_cap=cfg['resources']['total_SU_cap'],automatic_retries=0)
    write(filename,receipt)

    def submit(key,wall,mode,phase='pilot',array=None,dependency=None):
        assert key not in receipt['jobs'];receipt.update(status='submitting',pending_key=key);write(filename,receipt)
        cmd=['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short','-t',str(wall),
             '--exclude='+','.join(cfg['resources']['excluded_hosts']),'-J','lqr-indep-'+a.study+'-'+key,
             '-o',str(out/'logs'/(key+'-%A_%a.out'))]
        if array:cmd+=['--array='+array]
        if dependency:cmd+=['--dependency=afterok:'+dependency]
        driver=Path(__file__).resolve().parents[1]/'slurm/independent_ab_report_recovery.sbatch' if mode=='report' else a.release/'slurm/independent_ab_studies.sbatch'
        cmd+=[str(driver),a.study,mode,phase]
        job=subprocess.check_output(cmd,text=True,cwd=a.release).strip();assert job.isdigit(),job
        receipt['jobs'][key]=job;receipt.update(status='submitted',pending_key=None);write(filename,receipt)
        return job

    reserve=5.;report_wall=cfg['resources']['report_wall_minutes']
    if a.phase=='preflight':
        wall=cfg['resources']['preflight_wall_minutes'];receipt['requested_core_hour_bound']=wall/60
        submit('preflight',wall,'prepare')
    elif a.phase=='pilot':
        pre=read(out/'preflight.json');assert pre['status']=='PASS'
        if a.study=='ce':
            ratio=max(cfg['budgets'])/pre['benchmark_maximum_budget']
            predicted=max(sum(t['collector_seconds'] for t in x['timings'])*ratio + max(t['solve_and_save_seconds'] for t in x['timings'])*len(cfg['budgets']) for x in pre['benchmarks'])
            wall=max(5,math.ceil((1.6*predicted+120)/60))
            assert wall<=cfg['resources']['pilot_wall_minutes_maximum'],wall
            count=len(cfg['ranks'])*len(cfg['pilot_seeds']);jobspec=[(0,count-1,wall)]
        else:
            items=stein_tasks(cfg,'pilot');jobspec=[]
            for n in cfg['dimensions']:
                b=next(b for b in pre['benchmarks'] if b['n']==n)
                seconds=(b['seconds_per_block']*max(cfg['PI']['pilot_N'])+b['postprocess_seconds_for_methods'])*cfg['PI']['updates']
                wall=max(5,math.ceil((1.6*seconds+120)/60));assert wall<=cfg['resources']['maximum_task_wall_minutes'],wall
                indices=[i for i,t in enumerate(items) if t['n']==n];jobspec.append((min(indices),max(indices),wall))
        bound=spent+sum((hi-lo+1)*wall/60 for lo,hi,wall in jobspec)+report_wall/60
        assert bound+reserve<cfg['resources']['total_SU_cap'],bound
        receipt.update(resource_plan=jobspec,requested_core_hour_bound=bound);write(filename,receipt)
        jobs=[submit('pilot-'+str(i),wall,'task',array=f'{lo}-{hi}%8') for i,(lo,hi,wall) in enumerate(jobspec)]
        submit('pilot-report',report_wall,'report',dependency=':'.join(jobs))
    else:
        assert read(out/'report-pilot/summary.json')['status']=='complete'
        if a.study=='ce':
            jobspec=[];size=len(cfg['confirm_seeds'])
            for i,rank in enumerate(cfg['ranks']):
                observed=[read(out/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json')['seconds_this_invocation'] for seed in cfg['pilot_seeds']]
                wall=max(5,math.ceil((1.6*max(observed)+120)/60));assert wall<=cfg['resources']['formal_wall_minutes_maximum'],wall
                jobspec.append((i*size,(i+1)*size-1,wall))
            extra=cfg['resources']['audit_shards']*cfg['resources']['audit_wall_minutes']/60+report_wall/60
        else:
            pilot=stein_tasks(cfg,'pilot');formal=stein_tasks(cfg,'confirm');jobspec=[]
            for n,count in itertools.product(cfg['dimensions'],cfg['PI']['confirm_N']):
                data=[read(out/'raw'/f'pilot-{i:04d}.json') for i,t in enumerate(pilot) if t['n']==n and t['N']==max(cfg['PI']['pilot_N'])]
                # Measure the slowest actual stage, then reserve all six stages.
                # No cold-JIT benchmark is multiplied into every future stage.
                stage_seconds=max(t['seconds'] for x in data for t in x['stage_timings'])
                seconds=stage_seconds*cfg['PI']['updates']*count/max(cfg['PI']['pilot_N'])
                wall=max(5,math.ceil((1.3*seconds+120)/60))
                assert wall<=cfg['resources']['maximum_task_wall_minutes'],wall
                indices=[i for i,t in enumerate(formal) if t['n']==n and t['N']==count]
                jobspec.append((indices,wall))
            extra=report_wall/60
        requested=sum(((hi-lo+1)*wall/60) for lo,hi,wall in jobspec) if a.study=='ce' else sum(len(indices)*wall/60 for indices,wall in jobspec)
        bound=spent+requested+extra+reserve;assert bound<cfg['resources']['total_SU_cap'],bound
        receipt.update(resource_plan=jobspec,requested_core_hour_bound=bound,science_grid_frozen_before_pilot=True);write(filename,receipt)
        jobs=[]
        for i,spec in enumerate(jobspec):
            if a.study=='ce':lo,hi,wall=spec;array=f'{lo}-{hi}%4'
            else:indices,wall=spec;array=','.join(map(str,indices))+'%4'
            jobs.append(submit('formal-'+str(i),wall,'task','confirm',array=array))
        dependency=':'.join(jobs)
        if a.study=='ce':dependency=submit('formal-audits',cfg['resources']['audit_wall_minutes'],'audit','confirm',array='0-5%6',dependency=dependency)
        submit('formal-report',report_wall,'report','confirm',dependency=dependency)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
