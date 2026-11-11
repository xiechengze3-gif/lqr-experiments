"""Matched 100d rank sweep; local runner with stage-level restart and provenance.

The learner sees only K, Zhat, eta and the declared rank. Truth is confined to
simulation and evaluation. Existing original-coordinate Stein/OLS code is reused.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_discrete_lyapunov
from threadpoolctl import threadpool_limits, threadpool_info
from dense_scaling import (atomic_json, rng_for, orth, dare, evaluate, trunc,
                           nominal_chunk, ce_chunk, targets)
from actuation_redundancy import collect as stein_collect
from actuation_redundancy import learner as stein_update

SOURCES = ['scripts/rank_sweep100.py', 'scripts/actuation_redundancy.py',
           'scripts/npg_batched_collector.py', 'scripts/direct_stein_final.py',
           'dense_scaling.py']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_npz(path, **items):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f'.{os.getpid()}.tmp.npz')
    np.savez_compressed(temporary, **items)
    for retry in range(40):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if retry == 39:
                raise
            time.sleep(.05)


def system(cfg, rank):
    n = cfg['n']
    rng = rng_for(cfg['system_seed'])
    u, v = orth(rng, n), orth(rng, n)
    # Dense, nonnormal, stable random dynamics in the invariant complement.
    o = orth(rng, n-1)
    t = cfg['complement_rotation']*o
    perturb = rng.normal(size=(n-1, n-1))
    perturb *= cfg['complement_perturbation']/np.linalg.norm(perturb, 2)
    t += perturb
    f_latent = np.zeros((n,n)); f_latent[0,0] = .75; f_latent[1:,1:] = t
    f0 = u@f_latent@u.T
    a = f0+.45*np.outer(u[:,0], u[:,0])
    b = cfg['b']*u[:,:rank]@v[:,:rank].T
    k0 = (.45/cfg['b'])*np.outer(v[:,0], u[:,0])
    ks, ps = dare(a,b,np.eye(n),np.eye(n))
    p0 = solve_discrete_lyapunov(f0.T,np.eye(n)+k0.T@k0)
    return dict(A=a,B=b,Q=np.eye(n),R=np.eye(n),W=np.eye(n),K0=k0,
                Kstar=ks,Pstar=ps,Jstar=float(np.trace(ps)),
                initial_gap=float(np.trace(p0-ps))), dict(U=u,V=v,F0=f0,P0=p0,T=t)


def schedule(cfg):
    return [count for count, length in cfg['schedule_segments'] for _ in range(length)]


def innovations(cfg, route, seed, stage=0):
    # Excludes rank and algorithm: paired exogenous sources across both.
    return (rng_for(cfg['sampling_seed'],route,seed,stage,0),
            rng_for(cfg['sampling_seed'],route,seed,stage,1))


def corrected(matrix, method, rank):
    # This exact code path makes the full-rank control bitwise identical.
    return matrix.copy() if method == 'dense' or rank == min(matrix.shape) else trunc(matrix,rank)


def npg_update(k,z,method,eta,rank):
    return stein_update(k,corrected(z,method,rank),'dense',eta,rank)


def identity(cfg):
    scientific = {k:v for k,v in cfg.items() if k not in ('workers','output','cache','temp','pilot_seeds','confirm_seeds')}
    return dict(config_sha256=hashlib.sha256(json.dumps(scientific,sort_keys=True).encode()).hexdigest(),
                sources={p:sha(ROOT/p) for p in SOURCES})


def verify(cfg,out,ident):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    checks=[]; oracle=[]; reference=None; initial_gaps=[]
    for rank in cfg['ranks']:
        s,private=system(cfg,rank)
        f0,u,p0=private['F0'],private['U'],private['P0']
        radius_a=float(max(abs(np.linalg.eigvals(s['A']))))
        radius_f=float(max(abs(np.linalg.eigvals(f0))))
        residual=float(np.max(np.abs(s['A']-s['B']@s['K0']-f0)))
        assert radius_a>1 and radius_f<1 and residual<2e-13
        np.testing.assert_allclose(f0@u[:,0],.75*u[:,0],atol=1e-13)
        assert np.linalg.matrix_rank(s['B'],tol=1e-10)==rank
        q,p=evaluate(s,s['K0'])
        np.testing.assert_allclose(p,p0,atol=1e-11)
        # Common Lyapunov/stability certificate, including the K0 stage cost.
        certificate=p0-f0.T@p0@f0-(s['Q']+s['K0'].T@s['K0'])
        assert np.max(abs(certificate))<1e-11
        if reference is not None:
            for name,mat in [('A',s['A']),('K0',s['K0']),('P0',p0),('F0',f0)]:
                np.testing.assert_array_equal(reference[name],mat)
        else: reference=dict(A=s['A'],K0=s['K0'],P0=p0,F0=f0)
        save_npz(out/'systems'/f'r{rank:03d}.npz',**s,**private)
        initial_gaps.append(s['initial_gap'])
        checks.append(dict(rank=rank,rho_A=radius_a,rho_F0=radius_f,rank_B=rank,
                           closed_loop_max_error=residual,certificate_max_error=float(np.max(abs(certificate))),
                           J0=q['cost'],Jstar=s['Jstar'],initial_gap=s['initial_gap'],
                           complement_operator_norm=float(np.linalg.norm(private['T'],2)),
                           complement_nonnormality=float(np.linalg.norm(private['T'].T@private['T']-private['T']@private['T'].T))))
    epsilon=cfg['epsilon_fraction']*min(initial_gaps)
    for rank in cfg['ranks']:
        s,_=system(cfg,rank)
        for kind in ('exact','finite_H'):
            k=s['K0'].copy()
            for stage in range(cfg['oracle_updates']+1):
                q,p=evaluate(s,k)
                assert q['stable'],(rank,kind,stage)
                oracle.append(dict(rank=rank,kind=kind,stage=stage,**q))
                z=targets(s,k,cfg['horizon'],p)['Z' if kind=='exact' else 'ZH']
                np.testing.assert_allclose(npg_update(k,z,'dense',cfg['eta'],rank),
                                           npg_update(k,z,'truncated',cfg['eta'],rank),atol=2e-12)
                k=npg_update(k,z,'dense',cfg['eta'],rank)
    for rank in cfg['ranks']:
        for kind in ('exact','finite_H'):
            endpoint=next(r for r in oracle if r['rank']==rank and r['kind']==kind and r['stage']==len(schedule(cfg)))
            assert endpoint['gap']<=epsilon/10,(rank,kind,endpoint,epsilon)
    # Existing sequential collector vs batched collector, including full estimator.
    s,_=system(cfg,8); small=dict(cfg,burn=7)
    old=stein_collect(s,s['K0'],np.zeros(cfg['n']),256,*innovations(cfg,0,9001),small,True)
    new=stein_collect(s,s['K0'],np.zeros(cfg['n']),256,*innovations(cfg,0,9001),small,False)
    for i in (0,1):np.testing.assert_allclose(old[i],new[i],rtol=2e-10,atol=2e-10)
    assert old[2]==new[2]==7+257*cfg['horizon']
    z=new[1]
    np.testing.assert_array_equal(npg_update(s['K0'],z,'dense',cfg['eta'],100),
                                  npg_update(s['K0'],z,'truncated',cfg['eta'],100))
    # Actual maximum-batch benchmark on excluded seed; not used for tuning by rank.
    start=time.monotonic()
    bench=stein_collect(s,s['K0'],np.zeros(cfg['n']),cfg['benchmark_blocks'],*innovations(cfg,0,9001),cfg)
    result=dict(status='PASS',identity=ident,epsilon=epsilon,sensitivity_epsilon=epsilon/2,
                invariants=checks,oracle=oracle,
                tests=['common A/K0/F0/P0 and certificate','rank and unstable A',
                       'sequential/batched original Stein estimator', 'paired innovations exclude rank/method',
                       'full-rank exact update equality','exact and finite-H oracle attain at common iterations'],
                benchmark=dict(blocks=cfg['benchmark_blocks'],seconds=time.monotonic()-start,
                               transitions=bench[2],threadpools=threadpool_info()),
                execution=dict(backend='local',python=sys.executable,cache=os.environ.get('NUMBA_CACHE_DIR'),
                               temp=os.environ.get('TEMP'),matplotlib_cache=os.environ.get('MPLCONFIGDIR')))
    atomic_json(out/'verification.json',result)
    atomic_json(out/'resolved_config.json',dict(cfg,identity=ident,epsilon=epsilon))
    print(json.dumps(dict(status='verified',epsilon=epsilon,invariants=checks,benchmark=result['benchmark'])),flush=True)


def quality_row(s,k,**extra):
    q,_=evaluate(s,k)
    return dict(extra,**q,failure=None if q['stable'] else 'controller_instability')


def npg_task(cfg,rank,seed,out,ident):
    out=Path(out); dest=out/'raw'/f'npg-r{rank:03d}-s{seed:04d}.json'
    if dest.exists():
        assert read(dest)['identity']==ident
        return dict(route='npg',rank=rank,seed=seed,reused=True)
    s,_=system(cfg,rank); counts=schedule(cfg); n=cfg['n']; start=time.monotonic()
    k={method:s['K0'].copy() for method in ('dense','truncated')}
    x={method:np.zeros(n) for method in k}; failed={method:False for method in k}
    actual={method:0 for method in k}; physical=0; rows=[]; policies={method:[k[method].copy()] for method in k}
    first=0
    cp=out/'checkpoints'/dest.with_suffix('.npz').name
    if cp.exists():
        with np.load(cp,allow_pickle=False) as a:
            meta=json.loads(str(a['meta'])); assert meta['identity']==ident
            first=meta['next_stage']; failed=meta['failed']; actual=meta['actual']; rows=meta['rows']; physical=meta['physical']
            for method in k:
                k[method]=a[method+'_k'].copy(); x[method]=a[method+'_x'].copy(); policies[method]=list(a[method+'_policies'])
    else:
        for method in k:
            rows.append(quality_row(s,k[method],route='npg',method=method,rank=rank,seed=seed,stage=0,
                                    transitions=0,actual_transitions=0,observed=True,whole_path_stable=True))
    total=sum(cfg['burn']+(c+1)*cfg['horizon'] for c in counts[:first])
    for stage in range(first,len(counts)):
        uses=cfg['burn']+(counts[stage]+1)*cfg['horizon']; total+=uses
        cache=None
        for method in k:
            base=dict(route='npg',method=method,rank=rank,seed=seed,stage=stage+1,blocks=counts[stage],transitions=total)
            if failed[method]:
                row=dict(base,actual_transitions=actual[method],observed=False,whole_path_stable=False,
                         stable=False,rho=None,cost=None,gap=None,relative_gap=None,failure='prior_failure')
            else:
                try:
                    if cache is not None and np.array_equal(k[method],cache[0]) and np.array_equal(x[method],cache[1]):
                        endpoint,z,used,info=cache[2]
                    else:
                        before_k=k[method].copy(); before_x=x[method].copy()
                        endpoint,z,used,info=stein_collect(s,k[method],x[method],counts[stage],
                                                          *innovations(cfg,0,seed,stage),cfg)
                        physical+=used
                        cache=(before_k,before_x,(endpoint.copy(),z.copy(),used,info))
                    actual[method]+=used; assert used==uses
                    x[method]=endpoint.copy(); k[method]=npg_update(k[method],z,method,cfg['eta'],rank)
                    row=quality_row(s,k[method],**base,actual_transitions=actual[method],observed=True,
                                    whole_path_stable=True,**info)
                    if not row['stable']:
                        failed[method]=True; row['whole_path_stable']=False
                except (ValueError,np.linalg.LinAlgError,FloatingPointError) as error:
                    failed[method]=True
                    row=dict(base,actual_transitions=actual[method],observed=True,whole_path_stable=False,
                             stable=False,rho=None,cost=None,gap=None,relative_gap=None,
                             failure='numerical_failure',error=repr(error))
            rows.append(row); policies[method].append(k[method].copy())
        if rank==n:
            np.testing.assert_array_equal(k['dense'],k['truncated'])
            np.testing.assert_array_equal(x['dense'],x['truncated'])
        meta=dict(identity=ident,next_stage=stage+1,failed=failed,actual=actual,rows=rows,physical=physical)
        arrays={}
        for method in k:
            arrays.update({method+'_k':k[method],method+'_x':x[method],method+'_policies':np.array(policies[method])})
        save_npz(cp,meta=json.dumps(meta),**arrays)
    policy_path=out/'policies'/dest.with_suffix('.npz').name
    save_npz(policy_path,**{method:np.array(v) for method,v in policies.items()})
    data=dict(identity=ident,route='npg',rank=rank,seed=seed,records=rows,
              physical_transitions=physical,algorithm_actual_transitions=actual,
              seconds_this_invocation=time.monotonic()-start,policy_sha256=sha(policy_path))
    atomic_json(dest,data)
    return {key:data[key] for key in ('route','rank','seed','seconds_this_invocation','physical_transitions')}


def ce_task(cfg,rank,seed,out,ident):
    out=Path(out); dest=out/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json'
    if dest.exists():
        assert read(dest)['identity']==ident
        return dict(route='ce',rank=rank,seed=seed,reused=True)
    s,_=system(cfg,rank); n=cfg['n']; k=s['K0']; start=time.monotonic()
    f=np.ascontiguousarray(s['A']-s['B']@k); rows=[]; policies=[]; done=0
    pulse_rng,noise_rng=innovations(cfg,1,seed)
    x=np.zeros(n); gram=np.zeros((2*n,2*n)); cross=np.zeros((n,2*n))
    cp=out/'checkpoints'/dest.with_suffix('.npz').name
    if cp.exists():
        with np.load(cp,allow_pickle=False) as a:
            meta=json.loads(str(a['meta'])); assert meta['identity']==ident
            done=meta['done']; rows=meta['rows']; policies=list(a['policies']); x=a['x'].copy()
            gram=a['gram'].copy(); cross=a['cross'].copy()
            pulse_rng.bit_generator.state=meta['pulse_rng'];noise_rng.bit_generator.state=meta['noise_rng']
    else:
        x,_=nominal_chunk(f,x,noise_rng.normal(size=(cfg['burn'],n)))
    for budget in cfg['ce_budgets']:
        if budget<=done:continue
        while done<budget:
            size=min(cfg['chunk_size'],budget-done)
            x,inputs,outputs=ce_chunk(f,s['B'],k,x,cfg['sigma']*pulse_rng.normal(size=(size,n)),
                                      noise_rng.normal(size=(size,n)))
            gram+=inputs.T@inputs; cross+=outputs.T@inputs; done+=size
        theta=cho_solve(cho_factor((gram+gram.T)/2),cross.T).T
        ahat,bhat=theta[:,:n],theta[:,n:]
        residual=float(np.linalg.norm(theta@gram-cross)/max(np.linalg.norm(cross),1e-30))
        assert residual<1e-10
        pair=[]
        for method in ('dense','truncated'):
            base=dict(route='ce',method=method,rank=rank,seed=seed,transitions=done+cfg['burn'],
                      actual_transitions=done+cfg['burn'],ols_samples=done,observed=True,
                      ols_residual=residual,B_error_fro2=float(np.sum((corrected(bhat,method,rank)-s['B'])**2)))
            candidate=np.full((n,n),np.nan)
            try:
                candidate,_=dare(ahat,corrected(bhat,method,rank),s['Q'],s['R'])
                row=quality_row(s,candidate,**base)
            except (ValueError,np.linalg.LinAlgError) as error:
                row=dict(base,stable=False,rho=None,cost=None,gap=None,relative_gap=None,
                         failure='riccati_failure',error=repr(error))
            rows.append(row);pair.append(candidate); policies.append(candidate)
        if rank==n:np.testing.assert_array_equal(pair[0],pair[1])
        meta=dict(identity=ident,done=done,rows=rows,pulse_rng=pulse_rng.bit_generator.state,noise_rng=noise_rng.bit_generator.state)
        save_npz(cp,meta=json.dumps(meta),x=x,gram=gram,cross=cross,policies=np.array(policies))
    policy_path=out/'policies'/dest.with_suffix('.npz').name
    save_npz(policy_path,policies=np.array(policies))
    data=dict(identity=ident,route='ce',rank=rank,seed=seed,records=rows,
              physical_transitions=done+cfg['burn'],seconds_this_invocation=time.monotonic()-start,
              policy_sha256=sha(policy_path))
    atomic_json(dest,data)
    return {key:data[key] for key in ('route','rank','seed','seconds_this_invocation','physical_transitions')}


def worker(cfg,rank,seed,out,ident,route):
    with threadpool_limits(limits=cfg['blas_threads_per_worker']):
        return (npg_task if route=='npg' else ce_task)(cfg,rank,seed,out,ident)


def run(cfg,out,ident,phase,routes):
    verified=read(Path(out)/'verification.json'); assert verified['status']=='PASS' and verified['identity']==ident
    seeds=cfg[phase+'_seeds']; began=time.monotonic()
    jobs=[(route,rank,seed) for seed in seeds for rank in cfg['ranks'] for route in routes]
    with ProcessPoolExecutor(max_workers=cfg['workers']) as pool:
        pending=[pool.submit(worker,cfg,rank,seed,out,ident,route) for route,rank,seed in jobs]
        for number,future in enumerate(as_completed(pending),1):
            result=future.result()
            update=dict(phase=phase,complete=number,total=len(jobs),elapsed_seconds=time.monotonic()-began,last=result)
            atomic_json(Path(out)/f'progress-{phase}.json',update)
            print(json.dumps(update),flush=True)
    atomic_json(Path(out)/f'completion-{phase}.json',dict(status='complete',tasks=len(jobs),routes=routes,seeds=seeds,
                                                        wall_seconds=time.monotonic()-began,identity=ident))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['verify','run','audit'])
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--phase',choices=['pilot','confirm'],default='pilot')
    parser.add_argument('--routes',nargs='+',choices=['ce','npg'],default=['ce','npg'])
    args=parser.parse_args(); cfg=read(args.manifest);out=Path(cfg['output']);ident=identity(cfg)
    # Explicit storage checks before JIT, data generation or plotting.
    required={'NUMBA_CACHE_DIR':str(Path(cfg['cache'])/'numba'),'MPLCONFIGDIR':str(Path(cfg['cache'])/'matplotlib'),
              'TEMP':cfg['temp'],'TMP':cfg['temp']}
    for name,path in required.items():
        assert os.path.normcase(os.path.abspath(os.environ.get(name,'')))==os.path.normcase(os.path.abspath(path)),(name,path)
        assert Path(path).drive.upper()=='E:'
        Path(path).mkdir(parents=True,exist_ok=True)
    out.mkdir(parents=True,exist_ok=True)
    frozen=out/'frozen';frozen.mkdir(exist_ok=True)
    if (frozen/'identity.json').exists():assert read(frozen/'identity.json')==ident,'Sources/config changed; choose a new output directory'
    else:
        for source in SOURCES:
            dest=frozen/source;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/source,dest)
        shutil.copyfile(args.manifest,frozen/'config.json');atomic_json(frozen/'identity.json',ident)
    with threadpool_limits(limits=cfg['blas_threads_per_worker']):
        if args.mode=='verify':verify(cfg,out,ident)
        elif args.mode=='run':run(cfg,str(out),ident,args.phase,args.routes)
        else:
            checked=0;maximum=0.;full_rank=0
            for path in sorted((out/'raw').glob('*.json')):
                data=read(path);assert data['identity']==ident
                pp=out/'policies'/path.with_suffix('.npz').name;assert sha(pp)==data['policy_sha256']
                s,_=system(cfg,data['rank'])
                with np.load(pp) as a:
                    for i,row in enumerate(data['records']):
                        if not row['stable']:continue
                        k=a[row['method']][row['stage']] if data['route']=='npg' else a['policies'][i]
                        q,_=evaluate(s,k)
                        for key in ('gap','relative_gap','cost','rho'):
                            delta=abs(q[key]-row[key]);maximum=max(maximum,delta)
                            np.testing.assert_allclose(q[key],row[key],rtol=1e-9,atol=1e-9)
                        checked+=1
                    if data['rank']==cfg['n']:
                        if data['route']=='npg':np.testing.assert_array_equal(a['dense'],a['truncated'])
                        else:np.testing.assert_array_equal(a['policies'][::2],a['policies'][1::2])
                        full_rank+=1
            atomic_json(out/'audit.json',dict(status='PASS',checked_stable_policies=checked,
                                             full_rank_paired_trajectories=full_rank,max_difference=maximum,identity=ident))
            print(json.dumps(read(out/'audit.json')),flush=True)


if __name__=='__main__':main()
