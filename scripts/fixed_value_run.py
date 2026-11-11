"""Fixed batch and fixed updates; compare values at equal assigned data budgets."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from dense_scaling import atomic_json,rng_for,evaluate,targets,trunc,pi_gain,dare
from adaptive_rank_run import transition_data,model_fit,direct_data,record_update
from adaptive_rank import noise_proxy
from full_lstd_precision import solve
from npg_batched_collector import collect
from fixed_value_system import system,digest


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(manifest):
    names=['scripts/fixed_value_run.py','scripts/fixed_value_system.py','scripts/full_lstd_precision.py',
           'scripts/full_lstd.py','scripts/adaptive_rank.py','scripts/adaptive_rank_run.py',
           'scripts/npg_batched_collector.py','dense_scaling.py']
    return dict(manifest_sha256=sha(manifest),sources={n:sha(ROOT/n) for n in names})


def fit_lstd(z,y,k,s,cfg):
    n=len(k);nxt=np.concatenate((y,-y@k.T),axis=1)
    costs=np.einsum('ij,ij->i',z[:,:n]@s['Q'],z[:,:n])+np.einsum('ij,ij->i',z[:,n:]@s['R'],z[:,n:])
    h,diag=solve(z,nxt,costs,rtol=cfg['solver_rtol'],attempts=cfg['solver_attempts'])
    return ((h[n:,n:]-s['R'],h[n:,:n]) if diag['converged'] else None),diag


def estimate(s,k,x,algorithm,count,cfg,rng,need_scale,ce_history=None):
    if algorithm=='NPG':
        prefixes=[count//2,count] if need_scale else [count]
        parts=list(collect(s,k,x,prefixes,cfg['horizon'],1.,rng,burn=cfg['burn']))
        _,x,z,_,gram,used=parts[-1];scale=None
        if need_scale:
            _,_,z1,_,gram1,_=parts[0]
            g2=count*gram-(count//2)*gram1
            cross2=z@(count*gram)-z1@((count//2)*gram1)
            z2=np.linalg.solve(g2,cross2.T).T
            scale=noise_proxy(z1,z2)
        return x,(None,None,z),scale,used,{}
    if algorithm=='DIRECT_PI':
        x,full,halves,used=direct_data(s,k,x,count,cfg['burn'],cfg['horizon'],rng)
        scale=noise_proxy(np.concatenate(halves[0][:2],axis=1),np.concatenate(halves[1][:2],axis=1)) if need_scale else None
        return x,full,scale,used,{}
    x,z,y=transition_data(s,k,x,count,cfg['burn'],rng);mid=count//2
    if algorithm=='CE':
        # A/B are common to all behavior policies; keep sufficient statistics
        # from every observed training transition, in the original coordinates.
        history={} if ce_history is None else ce_history
        updated={}
        for half,(zz,yy) in enumerate(((z[:mid],y[:mid]),(z[mid:],y[mid:]))):
            gg=zz.T@zz;cc=yy.T@zz
            updated[f'ce_gram{half}']=history.get(f'ce_gram{half}',np.zeros_like(gg))+gg
            updated[f'ce_cross{half}']=history.get(f'ce_cross{half}',np.zeros_like(cc))+cc
        updated['ce_samples']=history.get('ce_samples',0)+count
        full=np.linalg.solve(updated['ce_gram0']+updated['ce_gram1'],
                             (updated['ce_cross0']+updated['ce_cross1']).T).T
        scale=None
        if need_scale:
            a=np.linalg.solve(updated['ce_gram0'],updated['ce_cross0'].T).T
            b=np.linalg.solve(updated['ce_gram1'],updated['ce_cross1'].T).T
            scale=noise_proxy(a[:,len(k):],b[:,len(k):])
        return x,full,scale,count+cfg['burn'],dict(model_samples=updated['ce_samples'],
                                                 _ce_statistics=updated)
    full,diag=fit_lstd(z,y,k,s,cfg);diagnostics=dict(full_solver=diag)
    scale=None
    if full is not None and need_scale:
        halves=[];diags=[]
        for zz,yy in ((z[:mid],y[:mid]),(z[mid:],y[mid:])):
            part,diagnostic=fit_lstd(zz,yy,k,s,cfg);halves.append(part);diags.append(diagnostic)
        diagnostics['split_solvers']=diags
        if all(x is not None for x in halves):
            scale=noise_proxy(np.concatenate(halves[0],axis=1),np.concatenate(halves[1],axis=1))
    return x,full,scale,count+cfg['burn'],diagnostics


def cache_systems(cfg,out,ident):
    invariants={}
    for task in cfg['tasks']:
        s,diag=system(task)
        key=(task['family'],task['system_seed'],task['policy_seed'],task['initial_strength'])
        matrices={k:v for k,v in diag['matrix_sha256'].items() if k!='B'}
        if key in invariants:assert invariants[key]==matrices
        invariants[key]=matrices
        path=out/'systems'/f"task-{task['id']:03d}.npz";path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as stream:np.savez(stream,**s)
        atomic_json(path.with_suffix('.json'),dict(task=task,diagnostics=diag,cache_sha256=sha(path),identity=ident))


def load_system(task,out,ident):
    path=out/'systems'/f"task-{task['id']:03d}.npz";meta=json.loads(path.with_suffix('.json').read_text())
    assert meta['identity']==ident and meta['task']==task and meta['cache_sha256']==sha(path)
    with np.load(path,allow_pickle=False) as values:s={k:values[k].copy() for k in values.files}
    for k in ('Jstar','initial_gap'):s[k]=float(s[k])
    return s,meta['diagnostics']


def checkpoint(path,ident,states,rows,next_stage):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    values=dict(identity=np.array(json.dumps(ident,sort_keys=True)),records=np.array(json.dumps(rows,allow_nan=False)),next_stage=np.array(next_stage))
    for method,state in states.items():
        for k,v in state.items():values[method+'_'+k]=np.asarray(v)
    with tmp.open('wb') as stream:np.savez(stream,**values)
    os.replace(tmp,path)


def batch_schedule(setting):
    stages=setting['stages']
    counts=setting.get('batches',[setting['batch']]*stages)
    assert len(counts)==stages and all(isinstance(n,int) and n>0 for n in counts)
    return counts


def run(task,algorithm,cfg,out,ident,max_stages=None):
    final=out/algorithm/'raw'/f"task-{task['id']:03d}.json"
    if final.exists():
        saved=json.loads(final.read_text());assert saved['identity']==ident and saved['task']==task
        return True
    s,diagnostics=load_system(task,out,ident);local=dict(cfg,npg_eta=diagnostics['npg_eta'])
    setting=cfg['profiles'][task['profile']][algorithm]
    stages=setting['stages'];counts=batch_schedule(setting)
    uses=[cfg['burn']+(count+1)*cfg['horizon'] if algorithm in ('DIRECT_PI','NPG')
          else cfg['burn']+count for count in counts]
    cumulative=np.cumsum(uses).tolist();assigned=sum(uses)
    methods=cfg['sensitivity_methods'] if task['scenario'] in cfg['sensitivity_scenarios'] else cfg['methods']
    states={m:dict(k=s['K0'].copy(),x=np.zeros(task['n']),actual=0,failed=False) for m in methods}
    if algorithm=='CE':
        for state in states.values():
            state.update(ce_gram0=np.zeros((2*task['n'],2*task['n'])),
                         ce_gram1=np.zeros((2*task['n'],2*task['n'])),
                         ce_cross0=np.zeros((task['n'],2*task['n'])),
                         ce_cross1=np.zeros((task['n'],2*task['n'])),ce_samples=0)
    quality,_=evaluate(s,s['K0'])
    rows=[dict(algorithm=algorithm,method=m,stage=0,N=0,transitions=0,actual_transitions=0,
               assigned_total_budget=assigned,value=quality['cost'],observed=True,**quality) for m in methods]
    start_stage=0;ckpt=out/algorithm/'checkpoints'/f"task-{task['id']:03d}.npz"
    if ckpt.exists():
        with np.load(ckpt,allow_pickle=False) as values:
            assert json.loads(str(values['identity']))==ident
            rows=json.loads(str(values['records']));start_stage=int(values['next_stage'])
            for method,state in states.items():
                for k in state:
                    item=values[method+'_'+k]
                    state[k]=item.copy() if item.ndim else item.item()
    start=time.monotonic()
    for stage in range(start_stage,stages):
        count,used=counts[stage],uses[stage]
        # Sharing is computational reuse only when the entire policy AND state
        # are identical. After divergence only exogenous seeds remain matched.
        def state_key(v):
            arrays=[v['k'].ravel(),v['x']]
            if algorithm=='CE':
                arrays.extend(v[k].ravel() for k in ('ce_gram0','ce_gram1','ce_cross0','ce_cross1'))
                arrays.append(np.array([v['ce_samples']]))
            return digest(np.concatenate(arrays))
        keys={m:state_key(v) for m,v in states.items() if not v['failed']}
        cache={}
        for method,state in states.items():
            row=dict(algorithm=algorithm,method=method,stage=stage+1,N=count,transitions=cumulative[stage],
                     assigned_total_budget=assigned)
            if state['failed']:
                row.update(stable=False,gap=None,cost=None,value=None,failure='prior_failure',observed=False)
            else:
                key=keys[method]
                if key not in cache:
                    need_scale=any(m.startswith('adaptive_') for m,k in keys.items() if k==key)
                    cache[key]=estimate(s,state['k'],state['x'],algorithm,count,local,
                        rng_for(202610134,task['n'],task['system_seed'],task['policy_seed'],task['trial_seed'],stage+1),
                        need_scale,state if algorithm=='CE' else None)
                x,full,scale,actual,solver=cache[key]
                assert actual==used;state['x']=x.copy();state['actual']+=actual
                if algorithm=='CE':
                    for stat,value in solver['_ce_statistics'].items():
                        state[stat]=value.copy() if isinstance(value,np.ndarray) else value
                    row['model_samples']=state['ce_samples']
                row['solver']={k:v for k,v in solver.items() if not k.startswith('_')}
                candidate=record_update(row,s,state['k'],algorithm,full,scale,method,task['r'],local)
                row['value']=row.get('cost')
                if row.get('failure') in ('full_solver_failure','split_solver_failure'):
                    row['failure_kind']='numerical_solver'
                elif row.get('failure')=='unstable_controller':row['failure_kind']='controller_instability'
                elif row.get('failure'):row['failure_kind']='update_failure'
                state['failed']=not row['stable']
                if candidate is not None:state['k']=candidate
            row['actual_transitions']=state['actual'];rows.append(row)
        checkpoint(ckpt,ident,states,rows,stage+1)
        atomic_json(out/'progress.json',dict(task=task,algorithm=algorithm,stage=stage+1,stages=stages,
            current_batch=count,fixed_batch=count if 'batches' not in setting else None,
            batch_schedule='growing' if 'batches' in setting else 'constant',
            assigned_total_budget=assigned,seconds_this_segment=time.monotonic()-start,
            live_methods=[m for m,v in states.items() if not v['failed']]))
        print(json.dumps(dict(task=task['id'],algorithm=algorithm,stage=stage+1,stages=stages)),flush=True)
        if max_stages is not None and stage+1-start_stage>=max_stages and stage+1<stages:return False
    atomic_json(final,dict(task=task,algorithm=algorithm,identity=ident,system=diagnostics,records=rows,
        setting=setting,assigned_total_budget=assigned,actual_total_budget={m:v['actual'] for m,v in states.items()},
        execution=dict(location='local',threads=cfg['threads'],slurm_job_id=None)))
    return True


def verify(cfg,out,ident):
    from full_lstd_precision import verify as verify_solver
    from adaptive_rank_run import update
    checks=dict(solver=verify_solver())
    small=dict(cfg['tasks'][0],id=-1,n=6,r=2,system_seed=900)
    s,diag=system(small);local=dict(cfg,npg_eta=diag['npg_eta'])
    for algorithm in cfg['algorithms']:
        _,full,scale,_,solver=estimate(s,s['K0'],np.zeros(6),algorithm,4096,local,rng_for(9001),True)
        assert full is not None and scale is not None,solver
        clean,_,info=update(s,s['K0'],algorithm,full,scale,'adaptive_1',2,local)
        poison=dict(s,B=np.full((6,6),88.),Kstar=np.full((6,6),66.),Jstar=1e12,initial_gap=1e12)
        dirty,_,other=update(poison,s['K0'],algorithm,full,scale,'adaptive_1',5,local)
        assert np.array_equal(clean,dirty) and info==other
    # Independent split-OLS collector equivalence at the same policy/trajectory.
    a=estimate(s,s['K0'],np.zeros(6),'NPG',4096,local,rng_for(9002),True)
    b=direct_data(s,s['K0'],np.zeros(6),4096,cfg['burn'],cfg['horizon'],rng_for(9002))
    assert np.allclose(a[0],b[0],rtol=1e-10,atol=1e-10)
    assert np.allclose(a[1][2],b[1][2],rtol=1e-10,atol=1e-10)
    assert np.isclose(a[2],noise_proxy(b[2][0][2],b[2][1][2]),rtol=1e-10,atol=1e-10)
    checks['four_route_no_true_model_rank_or_cost_access']=True
    checks['NPG_original_adjacent_OLS_and_split_equivalence']=True
    # Prefix model OLS matches an independent fit on the concatenated raw data.
    _,z1,y1=transition_data(s,s['K0'],np.zeros(6),4096,cfg['burn'],rng_for(9003))
    first=estimate(s,s['K0'],np.zeros(6),'CE',4096,local,rng_for(9003),True)
    k2=.5*s['K0']
    _,z2,y2=transition_data(s,k2,first[0].copy(),4096,cfg['burn'],rng_for(9004))
    second=estimate(s,k2,first[0].copy(),'CE',4096,local,rng_for(9004),True,first[4]['_ce_statistics'])
    expected=model_fit(np.concatenate((z1,z2)),np.concatenate((y1,y2)))
    assert np.allclose(second[1],expected,rtol=1e-10,atol=1e-10)
    assert second[4]['model_samples']==8192
    checks['CE_cumulative_full_model_OLS_explicit_prefix_match']=True
    cache_systems(cfg,out,ident)
    # Exact checkpoint replay, including full-rank K0 outside the action subspace.
    small_cfg=dict(cfg,tasks=[dict(small,id=0)],profiles={'audit':{a:dict(batch=4096,stages=3) for a in cfg['algorithms']}})
    if any('batches' in value['NPG'] for value in cfg['profiles'].values()):
        small_cfg['profiles']['audit']['NPG']['batches']=[2048,3072,4096]
    small_cfg['tasks'][0]['profile']='audit';small_cfg['tasks'][0]['scenario']='audit'
    roots=[out/'resume_audit'/'whole',out/'resume_audit'/'resumed']
    for root in roots:cache_systems(small_cfg,root,ident)
    for algorithm in cfg['algorithms']:
        assert run(small_cfg['tasks'][0],algorithm,small_cfg,roots[0],ident)
        assert not run(small_cfg['tasks'][0],algorithm,small_cfg,roots[1],ident,1)
        assert not run(small_cfg['tasks'][0],algorithm,small_cfg,roots[1],ident,1)
        assert run(small_cfg['tasks'][0],algorithm,small_cfg,roots[1],ident,1)
        records=[json.loads((root/algorithm/'raw'/'task-000.json').read_text())['records'] for root in roots]
        strip=lambda rs:[{k:v for k,v in x.items() if k!='solver'} for x in rs]
        assert strip(records[0])==strip(records[1]),algorithm
    checks['four_route_exact_checkpoint_replay']=True
    if 'batches' in small_cfg['profiles']['audit']['NPG']:
        rows=json.loads((roots[0]/'NPG'/'raw'/'task-000.json').read_text())['records']
        expected=[cfg['burn']+(n+1)*cfg['horizon'] for n in [2048,3072,4096]]
        for method in small_cfg['methods']:
            actual=[r for r in rows if r['method']==method and r['stage']>0]
            assert [r['N'] for r in actual]==[2048,3072,4096]
            assert [r['transitions'] for r in actual]==np.cumsum(expected).tolist()
            assert all(r['assigned_total_budget']==sum(expected) for r in actual)
        checks['growing_NPG_variable_counts_and_cumulative_transitions']=True
    checks['all_systems_frozen_stable_full_rank_initialization']=True
    atomic_json(out/'verification.json',dict(status='PASS',identity=ident,checks=checks))


def reference(cfg,out,ident):
    rows=[]
    for task in cfg['tasks']:
        if task['profile']!='standard' or task['trial_seed']!=0:continue
        s,diagnostics=load_system(task,out,ident)
        for algorithm in cfg['algorithms']:
            stages=cfg['profiles']['standard'][algorithm]['stages']
            for finite in ((False,True) if algorithm in ('DIRECT_PI','NPG') else (False,)):
                for method in ('dense','fixed_rank'):
                    k=s['K0'].copy()
                    if algorithm=='CE':
                        bb=s['B'] if method=='dense' else trunc(s['B'],task['r'])
                        k,_=dare(s['A'],bb,s['Q'],s['R']);quality,_=evaluate(s,k)
                        rows.append(dict(task,algorithm=algorithm,method=method,finite_horizon=False,stage=1,**quality))
                        continue
                    cap=max(stages,128) if algorithm=='NPG' else stages
                    for stage in range(cap+1):
                        quality,p=evaluate(s,k)
                        if stage<=stages or stage==cap:
                            rows.append(dict(task,algorithm=algorithm,method=method,finite_horizon=finite,stage=stage,**quality))
                        if stage==cap or not quality['stable']:break
                        truth=targets(s,k,cfg['horizon'],p)
                        if algorithm=='NPG':
                            z=truth['ZH' if finite else 'Z']
                            if method=='fixed_rank':z=trunc(z,task['r'])
                            k=k-diagnostics['npg_eta']*(s['R']@k+z)
                        else:
                            k,_,_=pi_gain(s,truth['GH' if finite else 'G'],truth['CH' if finite else 'C'],
                                         None if method=='dense' else task['r'])
        atomic_json(out/'population_reference.json',dict(identity=ident,diagnostic_only=True,status='RUNNING',records=rows))
    atomic_json(out/'population_reference.json',dict(identity=ident,diagnostic_only=True,status='COMPLETE',records=rows))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['verify','reference','run'])
    p.add_argument('--manifest',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--task-id',type=int,default=0);p.add_argument('--algorithm');p.add_argument('--max-stages',type=int)
    a=p.parse_args();cfg=json.loads(a.manifest.read_text());ident=identity(a.manifest)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=cfg['threads']):
        if a.mode=='verify':verify(cfg,a.output,ident)
        else:
            proof=json.loads((a.output/'verification.json').read_text());assert proof['status']=='PASS' and proof['identity']==ident
            if a.mode=='reference':reference(cfg,a.output,ident)
            else:
                assert a.algorithm in cfg['algorithms']
                run(cfg['tasks'][a.task_id],a.algorithm,cfg,a.output,ident,a.max_stages)


if __name__=='__main__':main()
