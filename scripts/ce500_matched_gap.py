"""500d matched-gap CE, same trajectory OLS/DARE as rank_sweep100.

Storage differs: immutable per-prefix policy files, compact sufficient-statistic
checkpoints, and a commit marker per prefix. No past policies are rewritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):
    sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_discrete_lyapunov
from scipy.optimize import brentq
from threadpoolctl import threadpool_limits, threadpool_info
import rank_sweep100 as e
from ce_matched_initial_gap import performance_gap

SOURCES = e.SOURCES + ['scripts/ce_matched_initial_gap.py',
                          'scripts/ce500_matched_gap.py']


def identity(cfg):
    return dict(config_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
                sources={p:e.sha(ROOT/p) for p in SOURCES})


def load_system(cfg, rank):
    path=Path(cfg['output'])/'systems'/f'r{rank:03d}.npz'
    verification=e.read(Path(cfg['output'])/'verification.json')
    assert e.sha(path)==verification['system_hashes'][str(rank)]
    with np.load(path,allow_pickle=False) as a:
        return {k:float(a[k]) if a[k].ndim==0 else a[k].copy() for k in a.files}


def rngs(cfg, seed):
    return tuple(e.rng_for(cfg['sampling_seed'],cfg['sampling_route'],seed,0,i) for i in (0,1))


def task(cfg, ident, rank, seed, budgets, out=None):
    out=Path(out or cfg['output']);stem=f'ce-r{rank:03d}-s{seed:04d}'
    destination=out/'raw'/(stem+'.json');start=time.monotonic()
    if destination.exists():
        prior=e.read(destination);assert prior['identity']==ident
        if prior['budgets']==budgets:return dict(rank=rank,seed=seed,reused=True)
        assert all(b in budgets for b in prior['budgets'])
    s=load_system(cfg,rank);n=cfg['n'];k=s['K0']
    f=np.ascontiguousarray(s['A']-s['B']@k)
    pulse,noise=rngs(cfg,seed);x=np.zeros(n)
    gram=np.zeros((2*n,2*n));cross=np.zeros((n,2*n));done=0;rows=[]
    cp=out/'checkpoints'/(stem+'.npz')
    if cp.exists():
        with np.load(cp,allow_pickle=False) as a:
            meta=json.loads(str(a['meta']));assert meta['identity']==ident
            done=meta['done'];rows=meta['rows'];x=a['x'].copy()
            gram=a['gram'].copy();cross=a['cross'].copy()
            pulse.bit_generator.state=meta['pulse_rng'];noise.bit_generator.state=meta['noise_rng']
        assert all(b in [q['ols_samples'] for q in rows] for b in budgets if b<=done)
    else:
        x,_=e.nominal_chunk(f,x,noise.normal(size=(cfg['burn'],n)))
    times=[]
    for budget in budgets:
        if budget<=done:continue
        tick=time.monotonic();previous=done
        while done<budget:
            size=min(cfg['chunk_size'],budget-done)
            x,inputs,outputs=e.ce_chunk(f,s['B'],k,x,cfg['sigma']*pulse.normal(size=(size,n)),
                                       noise.normal(size=(size,n)))
            gram+=inputs.T@inputs;cross+=outputs.T@inputs;done+=size
        collector_seconds=time.monotonic()-tick;tick=time.monotonic()
        theta=cho_solve(cho_factor((gram+gram.T)/2),cross.T).T
        ahat,bhat=theta[:,:n],theta[:,n:]
        residual=float(np.linalg.norm(theta@gram-cross)/max(np.linalg.norm(cross),1e-30))
        assert residual<1e-10
        btr=e.corrected(bhat,'truncated',rank);pair=[];pair_rows=[]
        for method,bfit in [('dense',bhat),('truncated',btr)]:
            base=dict(route='ce',method=method,rank=rank,seed=seed,transitions=done+cfg['burn'],
                actual_transitions=done+cfg['burn'],ols_samples=done,observed=True,ols_residual=residual,
                B_error_fro2=float(np.sum((bfit-s['B'])**2)),A_error_fro2=float(np.sum((ahat-s['A'])**2)))
            if rank==n and method=='truncated':
                candidate=pair[0].copy();row=dict(pair_rows[0],method=method)
            else:
                candidate=np.full((n,n),np.nan)
                try:
                    candidate,_=e.dare(ahat,bfit,s['Q'],s['R'])
                    row=e.quality_row(s,candidate,**base)
                except (ValueError,np.linalg.LinAlgError) as err:
                    row=dict(base,stable=False,rho=None,cost=None,gap=None,relative_gap=None,
                             failure='riccati_failure',error=repr(err))
            pair.append(candidate);pair_rows.append(row)
        if rank==n:np.testing.assert_array_equal(*pair)
        # Policy written first, checkpoint second. Uncommitted files may be safely overwritten.
        policy_path=out/'policies'/stem/f'n{done:09d}.npz'
        e.save_npz(policy_path,**({'shared':pair[0]} if rank==n else dict(dense=pair[0],truncated=pair[1])))
        for row in pair_rows:
            row.update(policy_file=str(policy_path.relative_to(out)),policy_sha256=e.sha(policy_path))
        rows+=pair_rows
        meta=dict(identity=ident,done=done,rows=rows,pulse_rng=pulse.bit_generator.state,noise_rng=noise.bit_generator.state)
        e.save_npz(cp,meta=json.dumps(meta),x=x,gram=gram,cross=cross)
        times.append(dict(budget=done,additional_samples=done-previous,collector_seconds=collector_seconds,
                          solve_and_save_seconds=time.monotonic()-tick))
        print(json.dumps(dict(rank=rank,seed=seed,budget=done,
            gaps=[q['gap'] for q in pair_rows],seconds=time.monotonic()-start)),flush=True)
    e.save_npz(out/'estimates'/(stem+'.npz'),Ahat=theta[:,:n],Bhat=theta[:,n:]) if times else None
    raw=dict(identity=ident,route='ce',rank=rank,seed=seed,budgets=budgets,records=rows,
             physical_transitions=done+cfg['burn'],seconds_this_invocation=time.monotonic()-start,
             timings_this_invocation=times,slurm_job_id=os.environ['SLURM_JOB_ID'])
    e.atomic_json(destination,raw)
    return {key:raw[key] for key in ('rank','seed','physical_transitions','seconds_this_invocation')}


def prepare(cfg, ident, manifest):
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    if (out/'preflight.json').exists():
        assert e.read(out/'preflight.json')['identity']==ident;return
    for source in SOURCES:
        dst=out/'frozen'/source;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/source,dst)
    shutil.copyfile(manifest,out/'frozen/config.json')
    direction=e.orth(e.rng_for(cfg['initialization_seed']),cfg['n'])
    reference=None;checks=[];hashes={};began=time.monotonic()
    for rank in cfg['ranks']:
        s,private=e.system(cfg,rank);s.update(private)
        if reference is not None:
            for name in ('A','U','V','F0','P0','K0'):np.testing.assert_array_equal(s[name],reference[name])
        else:reference={k:s[k].copy() for k in ('A','U','V','F0','P0','K0')}
        residual=float(np.max(abs(s['A']-s['B']@s['K0']-s['F0'])))
        radius_a=float(max(abs(np.linalg.eigvals(s['A']))));radius_f=float(max(abs(np.linalg.eigvals(s['F0']))))
        assert residual<2e-12 and radius_a>1 and radius_f<1
        np.testing.assert_allclose(s['F0']@s['U'][:,0],.75*s['U'][:,0],atol=1e-12)
        assert np.linalg.matrix_rank(s['B'],tol=1e-10)==rank
        hi=.01
        while performance_gap(s,s['Kstar']+hi*direction)[0]<cfg['initial_gap']:hi*=2
        alpha=brentq(lambda a:performance_gap(s,s['Kstar']+a*direction)[0]-cfg['initial_gap'],
                     0,hi,xtol=5e-15,rtol=1e-14)
        k=s['Kstar']+alpha*direction;gap,rho,cov=performance_gap(s,k)
        f=s['A']-s['B']@k;p=solve_discrete_lyapunov(f.T,s['Q']+k.T@k)
        actual=float(np.trace(p)-s['Jstar']);certificate=float(np.max(abs(p-f.T@p@f-(s['Q']+k.T@k))))
        assert abs(actual-1)<1e-9 and abs(gap-1)<1e-10 and certificate<1e-10 and rho<1
        assert np.linalg.matrix_rank(k,tol=1e-10)==cfg['n']
        exploration=solve_discrete_lyapunov(f,s['W']+cfg['sigma']**2*s['B']@s['B'].T)
        s.update(K0_original=s['K0'],P0_original=s['P0'],F0_original=s['F0'],K0=k,P0=p,F0=f,
                 initial_gap=cfg['initial_gap'],actual_initial_gap=actual,
                 initialization_direction=direction,initialization_alpha=alpha)
        path=out/'systems'/f'r{rank:03d}.npz';e.save_npz(path,**s);hashes[str(rank)]=e.sha(path)
        checks.append(dict(rank=rank,initial_gap=actual,J0=float(np.trace(p)),Jstar=s['Jstar'],
            rho_K0=rho,rho_A=radius_a,rho_F0_original=radius_f,K0_rank=cfg['n'],alpha=alpha,
            original_closed_loop_max_error=residual,certificate_residual=certificate,
            exploration_covariance_trace=float(np.trace(exploration)),
            exploration_covariance_condition=float(np.linalg.cond(exploration))))
        print(json.dumps(dict(prepared_rank=rank,seconds=time.monotonic()-began,**checks[-1])),flush=True)
    e.atomic_json(out/'verification.json',dict(status='PASS',identity=ident,systems=checks,system_hashes=hashes))
    e.atomic_json(out/'resolved_config.json',dict(cfg,identity=ident))
    # Actual trajectory labels: confirm [x_t,u_t] -> x_{t+1}, joint OLS, no whitening.
    s=load_system(cfg,cfg['n']);n=cfg['n'];pulse,noise=rngs(cfg,9000)
    f=np.ascontiguousarray(s['A']-s['B']@s['K0'])
    x,z,y=e.ce_chunk(f,s['B'],s['K0'],np.zeros(n),cfg['sigma']*pulse.normal(size=(2048,n)),np.zeros((2048,n)))
    theta=np.concatenate((s['A'],s['B']),axis=1)
    recovered=np.linalg.lstsq(z,y,rcond=None)[0].T
    error=float(np.max(abs(recovered-theta)));assert error<2e-11
    np.testing.assert_allclose(z@theta.T,y,atol=2e-12)
    # Restart replay covers low rank and full rank; excluded diagnostic seed.
    diagnostic=2048
    for rank in (cfg['ranks'][0],cfg['n']):
        paths={name:out/'diagnostics'/f'{name}-r{rank:03d}' for name in ('continuous','resumed')}
        task(cfg,ident,rank,9001,[2048,4096],paths['continuous'])
        task(cfg,ident,rank,9001,[2048],paths['resumed'])
        task(cfg,ident,rank,9001,[2048,4096],paths['resumed'])
        a=e.read(paths['continuous']/'raw'/f'ce-r{rank:03d}-s9001.json')
        b=e.read(paths['resumed']/'raw'/f'ce-r{rank:03d}-s9001.json')
        assert a['records']==b['records']
        with np.load(paths['continuous']/'checkpoints'/f'ce-r{rank:03d}-s9001.npz') as aa,\
             np.load(paths['resumed']/'checkpoints'/f'ce-r{rank:03d}-s9001.npz') as bb:
            for key in ('x','gram','cross'):np.testing.assert_array_equal(aa[key],bb[key])
        diagnostic+=2*(cfg['burn']+4096)
    benchmark=[]
    for rank in (cfg['ranks'][0],cfg['n']):
        result=task(cfg,ident,rank,9002,[2048,8192,32768,131072],out/'diagnostics/benchmark')
        benchmark.append(result);diagnostic+=result['physical_transitions']
    e.atomic_json(out/'preflight.json',dict(status='PASS',identity=ident,benchmark=benchmark,
        diagnostic_primitive_transitions=diagnostic,trajectory_OLS_max_error=error,
        checkpoint_resume_tests=2,peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        seconds=time.monotonic()-began,threadpools=threadpool_info(),slurm_job_id=os.environ['SLURM_JOB_ID']))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','task'])
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--phase',default='pilot',choices=['pilot','confirm'])
    p.add_argument('--task-id',type=int);p.add_argument('--plan',type=Path);args=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID'),'Numerical work requires a Grace compute node'
    cfg=e.read(args.manifest);ident=identity(cfg)
    for name,wanted in [('TMPDIR',cfg['temp']),('NUMBA_CACHE_DIR',str(Path(cfg['cache'])/'numba')),
                        ('MPLCONFIGDIR',str(Path(cfg['cache'])/'matplotlib'))]:
        assert os.environ.get(name)==wanted;Path(wanted).mkdir(parents=True,exist_ok=True)
    with threadpool_limits(1):
        if args.mode=='prepare':prepare(cfg,ident,args.manifest)
        else:
            assert e.read(Path(cfg['output'])/'preflight.json')['identity']==ident
            plan=e.read(args.plan) if args.plan else None
            budgets=plan['budgets'] if plan else cfg['pilot_budgets']
            jobs=[(r,s) for s in cfg[args.phase+'_seeds'] for r in cfg['ranks']]
            rank,seed=jobs[args.task_id]
            result=task(cfg,ident,rank,seed,budgets)
            e.atomic_json(Path(cfg['output'])/'task_receipts'/f'{args.phase}-{args.task_id:03d}.json',
                dict(result,phase=args.phase,task_id=args.task_id,slurm_job_id=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':main()
