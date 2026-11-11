"""Frozen, resumable four-route local study; diagnostics never select updates."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from dense_scaling import atomic_json, evaluate, targets, trunc, rng_for, dare, pi_gain
from adaptive50_system import system
from adaptive_rank_run import estimate, record_update


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(manifest):
    names=['dense_scaling.py','scripts/adaptive50_system.py','scripts/adaptive50_run.py',
           'scripts/adaptive_rank_run.py','scripts/adaptive_rank.py',
           'scripts/full_lstd.py','scripts/npg_batched_collector.py']
    return dict(manifest_sha256=sha(manifest),sources={name:sha(ROOT/name) for name in names})


def checkpoint(path,identity,states,records,next_stage):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    values=dict(identity=np.array(json.dumps(identity,sort_keys=True)),
                records=np.array(json.dumps(records,allow_nan=False)),next_stage=np.array(next_stage))
    for method,state in states.items():
        for key,value in state.items(): values[method+'_'+key]=np.asarray(value)
    with tmp.open('wb') as stream: np.savez(stream,**values)
    os.replace(tmp,path)


def load_system(out,task):
    path=out/'systems'/f"system-{task['id']:03d}.npz"
    meta=json.loads(path.with_suffix('.json').read_text())
    assert meta['task']==task
    assert sha(path)==meta['cache_sha256']
    with np.load(path,allow_pickle=False) as arrays:
        s={key:arrays[key].copy() for key in arrays.files}
    for key in ('Jstar','initial_gap'): s[key]=float(s[key])
    return s,meta['diagnostics']


def verify(cfg,out,ident):
    from full_lstd import verify as lstd_verify
    from adaptive_rank_run import update, make_system
    from adaptive_rank import select
    checks=dict(lstd=lstd_verify())
    base=cfg.copy()
    small=dict(id=-1,n=6,m=6,r=2,system_seed=900,policy_seed=0,
               trial_seed=0,initial_strength=.08,tail=0.,spectrum='exact')
    s,_=system(small,base)
    for algorithm in cfg['algorithms']:
        _,full,scale,_,solver=estimate(s,s['K0'],np.zeros(6),algorithm,4096,cfg,rng_for(5519))
        assert full is not None and scale is not None,solver
        clean,_,info=update(s,s['K0'],algorithm,full,scale,'adaptive_1',2,cfg)
        poisoned=dict(s,B=np.full((6,6),99.),Kstar=np.full((6,6),77.),Jstar=1e12,initial_gap=1e12)
        dirty,_,other=update(poisoned,s['K0'],algorithm,full,scale,'adaptive_1',5,cfg)
        assert np.array_equal(clean,dirty) and info==other
        if algorithm=='NPG':
            z=select(full[2],'adaptive_1',scale)[0]
            assert np.array_equal(clean,s['K0']-cfg['npg_eta']*(s['R']@s['K0']+z))
    checks['four_route_adaptive_information_access']=True
    matrices={}
    for task in cfg['tasks']:
        s,diag=system(task,cfg)
        key=(task['system_seed'],task['policy_seed'])
        invariant={k:v for k,v in diag['matrix_sha256'].items() if k!='B'}
        if key in matrices: assert matrices[key]==invariant
        matrices[key]=invariant
        path=out/'systems'/f"system-{task['id']:03d}.npz"
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as stream: np.savez(stream,**s)
        atomic_json(path.with_suffix('.json'),dict(task=task,diagnostics=diag,cache_sha256=sha(path)))
    checks['all_initial_policies_full_rank_stable_outside_subspace']=True
    checks['fixed_A_Q_R_K0_across_tail']=True
    atomic_json(out/'verification.json',dict(status='PASS',identity=ident,checks=checks))
    print(json.dumps(dict(status='PASS',systems=len(cfg['tasks']))),flush=True)


def benchmark(cfg,out,ident):
    task=dict(id=-1,n=50,m=50,r=4,system_seed=900,policy_seed=0,trial_seed=0,
              initial_strength=.08,tail=0.,spectrum='exact')
    s,sysdiag=system(task,cfg)
    rows=[]
    import psutil
    for algorithm in cfg['algorithms']:
        for count in cfg['benchmark_budgets']:
            wall,cpu=time.monotonic(),time.process_time()
            _,full,scale,used,solver=estimate(s,s['K0'],np.zeros(50),algorithm,count,cfg,rng_for(5520))
            row=dict(algorithm=algorithm,N=count,transitions=used,seconds=time.monotonic()-wall,
                     cpu_seconds=time.process_time()-cpu,rss_bytes=psutil.Process().memory_info().rss,
                     solver=solver,noise_proxy=scale,methods=[])
            for method in cfg['methods']:
                result=dict(method=method)
                record_update(result,s,s['K0'],algorithm,full,scale,method,4,cfg)
                row['methods'].append(result)
            rows.append(row)
            atomic_json(out/'benchmark.json',dict(identity=ident,task=task,system=sysdiag,records=rows,
                                                 status='RUNNING',diagnostic_only=True))
            print(json.dumps({k:v for k,v in row.items() if k not in ('methods','solver')}),flush=True)
    atomic_json(out/'benchmark.json',dict(identity=ident,task=task,system=sysdiag,records=rows,
                                         status='COMPLETE',diagnostic_only=True))


def verify_resume(cfg,out,ident):
    task=dict(id=0,n=6,m=6,r=2,system_seed=900,policy_seed=0,trial_seed=0,
              initial_strength=.08,tail=0.,spectrum='exact')
    small=dict(cfg,tasks=[task],schedules={a:[4096]*3 for a in cfg['algorithms']})
    s,diag=system(task,small)
    roots=[out/'resume-validation'/'whole',out/'resume-validation'/'resumed']
    for root in roots:
        path=root/'systems'/'system-000.npz';path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as stream:np.savez(stream,**s)
        atomic_json(path.with_suffix('.json'),dict(task=task,diagnostics=diag,cache_sha256=sha(path)))
    checks=[]
    for algorithm in cfg['algorithms']:
        assert learning(task,algorithm,small,roots[0],ident)
        assert not learning(task,algorithm,small,roots[1],ident,max_stages=1)
        assert not learning(task,algorithm,small,roots[1],ident,max_stages=1)
        assert learning(task,algorithm,small,roots[1],ident,max_stages=1)
        records=[json.loads((root/algorithm/'raw'/'task-000.json').read_text())['records'] for root in roots]
        # Solver wall times are observational and need not match after replay.
        scientific=lambda rs:[{k:v for k,v in row.items() if k!='solver'} for row in rs]
        assert scientific(records[0])==scientific(records[1]),algorithm
        checks.append(dict(algorithm=algorithm,exact_scientific_records=True))
    atomic_json(out/'resume_validation.json',dict(status='PASS',identity=ident,checks=checks))


def reference(cfg,out,ident):
    records=[]
    for task in cfg['tasks']:
        if task['trial_seed']!=0:continue
        s,_=load_system(out,task)
        for algorithm in cfg['algorithms']:
            for finite in ((False,True) if algorithm in ('DIRECT_PI','NPG') else (False,)):
                for method in ('dense','known_rank'):
                    k=s['K0'].copy()
                    cap=128 if algorithm=='NPG' else len(cfg['schedules'][algorithm])
                    if algorithm=='CE':
                        b=s['B'] if method=='dense' else trunc(s['B'],task['r'])
                        k,_=dare(s['A'],b,s['Q'],s['R'])
                        quality,_=evaluate(s,k)
                        records.append(dict(task,algorithm=algorithm,method=method,stage=1,
                                            finite_horizon=False,**quality))
                        continue
                    for stage in range(cap+1):
                        quality,p=evaluate(s,k)
                        if stage in (0,6,32,64,128) or stage==cap:
                            records.append(dict(task,algorithm=algorithm,method=method,stage=stage,
                                                finite_horizon=finite,**quality))
                        if stage==cap or not quality['stable']:break
                        truth=targets(s,k,cfg['horizon'],p)
                        if algorithm=='NPG':
                            z=truth['ZH' if finite else 'Z']
                            if method=='known_rank':z=trunc(z,task['r'])
                            k=k-cfg['npg_eta']*(s['R']@k+z)
                        else:
                            k,_,_=pi_gain(s,truth['GH' if finite else 'G'],truth['CH' if finite else 'C'],
                                         None if method=='dense' else task['r'])
        atomic_json(out/'population_reference.json',dict(identity=ident,records=records,
                                                        diagnostic_only=True,status='RUNNING'))
    atomic_json(out/'population_reference.json',dict(identity=ident,records=records,
                                                    diagnostic_only=True,status='COMPLETE'))


def learning(task,algorithm,cfg,out,ident,max_stages=None):
    final=out/algorithm/'raw'/f"task-{task['id']:03d}.json"
    if final.exists():
        saved=json.loads(final.read_text());assert saved['identity']==ident and saved['task']==task
        return True
    s,sysdiag=load_system(out,task)
    ckpt=out/algorithm/'checkpoints'/f"task-{task['id']:03d}.npz"
    states={m:dict(k=s['K0'].copy(),x=np.zeros(task['n']),total=0,actual=0,failed=False) for m in cfg['methods']}
    quality,_=evaluate(s,s['K0'])
    rows=[dict(phase='learning',algorithm=algorithm,method=m,stage=0,N=0,transitions=0,
               actual_transitions=0,observed=True,**quality) for m in cfg['methods']]
    next_stage=0
    if ckpt.exists():
        with np.load(ckpt,allow_pickle=False) as saved:
            assert json.loads(str(saved['identity']))==ident
            rows=json.loads(str(saved['records']));next_stage=int(saved['next_stage'])
            for method,state in states.items():
                for key in state:
                    value=saved[method+'_'+key]
                    state[key]=value.copy() if key in ('k','x') else value.item()
    schedule=cfg['schedules'][algorithm]
    completed_here=0
    for index in range(next_stage,len(schedule)):
        count=schedule[index]
        used=cfg['burn']+(count+1)*cfg['horizon'] if algorithm in ('NPG','DIRECT_PI') else cfg['burn']+count
        for method,state in states.items():
            state['total']+=used
            row=dict(phase='learning',algorithm=algorithm,method=method,stage=index+1,N=count,
                     transitions=state['total'])
            if state['failed']:
                row.update(stable=False,gap=None,failure='prior_failure',observed=False)
            else:
                state['x'],full,scale,actual,solver=estimate(s,state['k'],state['x'],algorithm,count,cfg,
                    rng_for(202610123,task['n'],task['system_seed'],task['policy_seed'],task['trial_seed'],index+1))
                assert actual==used
                state['actual']+=actual
                row['solver']=solver
                candidate=record_update(row,s,state['k'],algorithm,full,scale,method,task['r'],cfg)
                state['failed']=not row['stable']
                if candidate is not None: state['k']=candidate
            row['actual_transitions']=state['actual']
            rows.append(row)
        checkpoint(ckpt,ident,states,rows,index+1)
        atomic_json(out/'progress.json',dict(task=task,algorithm=algorithm,stage=index+1,
            total_stages=len(schedule),stable_methods=[m for m,x in states.items() if not x['failed']]))
        print(json.dumps(dict(task_id=task['id'],algorithm=algorithm,stage=index+1)),flush=True)
        completed_here+=1
        if max_stages is not None and completed_here>=max_stages and index+1<len(schedule): return False
    atomic_json(final,dict(task=task,algorithm=algorithm,identity=ident,system=sysdiag,records=rows,
        execution=dict(location='local',slurm_job_id=None,threads=cfg['threads'])))
    return True


def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['verify','verify-resume','benchmark','reference','run'])
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--task-id',type=int,default=0)
    p.add_argument('--algorithm')
    p.add_argument('--max-stages',type=int)
    a=p.parse_args();cfg=json.loads(a.manifest.read_text());ident=identity(a.manifest)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=cfg['threads']):
        if a.mode=='verify': verify(cfg,a.output,ident)
        else:
            proof=json.loads((a.output/'verification.json').read_text())
            assert proof['status']=='PASS' and proof['identity']==ident
            if a.mode=='benchmark': benchmark(cfg,a.output,ident)
            elif a.mode=='verify-resume':verify_resume(cfg,a.output,ident)
            elif a.mode=='reference':reference(cfg,a.output,ident)
            else:
                assert a.algorithm in cfg['algorithms']
                learning(cfg['tasks'][a.task_id],a.algorithm,cfg,a.output,ident,a.max_stages)


if __name__=='__main__':main()
