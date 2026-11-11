"""CE with matched initial optimality gap; reuse the unchanged CE learner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
if os.environ.get('LQR_NUMBA_SITE'):
    sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from scipy.linalg import solve_discrete_lyapunov, cho_factor, cho_solve
from threadpoolctl import threadpool_limits, threadpool_info
import rank_sweep100 as e

NUMERIC_SOURCES = e.SOURCES + ['scripts/ce_matched_initial_gap.py']


def identity(cfg):
    return dict(config_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
                sources={p:e.sha(ROOT/p) for p in NUMERIC_SOURCES})


def load_original(cfg, rank):
    path=ROOT/'system_inputs'/f'r{rank:03d}.npz'
    assert e.sha(path)==cfg['system_artifact_sha256'][str(rank)]
    with np.load(path,allow_pickle=False) as a:
        return {key:float(a[key]) if a[key].ndim==0 else a[key].copy() for key in a.files}


def performance_gap(s, k):
    f=s['A']-s['B']@k
    rho=float(max(abs(np.linalg.eigvals(f))))
    if rho>=1-1e-10:return np.inf,rho,None
    covariance=solve_discrete_lyapunov(f,s['W'])
    delta=k-s['Kstar'];weight=s['R']+s['B'].T@s['Pstar']@s['B']
    return float(np.trace(covariance@delta.T@weight@delta)),rho,covariance


def load_matched(cfg, rank):
    out=Path(cfg['output']);verified=e.read(out/'verification.json')
    path=out/'systems'/f'r{rank:03d}.npz'
    assert e.sha(path)==verified['system_hashes'][str(rank)]
    with np.load(path,allow_pickle=False) as a:
        s={key:float(a[key]) if a[key].ndim==0 else a[key].copy() for key in a.files}
    return s,{}


def innovations(cfg, route, seed, stage=0):
    # Same exogenous innovations across ranks and methods, fresh route from old runs.
    return (e.rng_for(cfg['sampling_seed'],cfg['sampling_route'],seed,stage,0),
            e.rng_for(cfg['sampling_seed'],cfg['sampling_route'],seed,stage,1))


def task(cfg, ident, phase, rank, seed, override_budgets=None, override_out=None):
    options=dict(cfg,ce_budgets=override_budgets or cfg[phase+'_budgets'])
    out=Path(override_out or cfg['output'])
    result=e.ce_task(options,rank,seed,out,ident)
    cp=out/'checkpoints'/f'ce-r{rank:03d}-s{seed:04d}.npz'
    with np.load(cp,allow_pickle=False) as arrays:
        theta=cho_solve(cho_factor((arrays['gram']+arrays['gram'].T)/2),arrays['cross'].T).T
        e.save_npz(out/'estimates'/cp.name,Ahat=theta[:,:cfg['n']],Bhat=theta[:,cfg['n']:],
                   gram=arrays['gram'],cross=arrays['cross'])
    return result


def prepare(cfg, ident, manifest):
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    if (out/'verification.json').exists():
        assert e.read(out/'verification.json')['identity']==ident
        if (out/'preflight.json').exists():
            assert e.read(out/'preflight.json')['status']=='PASS'
            print('Matched systems and preflight already verified',flush=True);return
    frozen=out/'frozen'
    for source in NUMERIC_SOURCES+['scripts/ce_matched_initial_gap_report.py']:
        dest=frozen/source;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/source,dest)
    shutil.copytree(ROOT/'system_inputs',frozen/'system_inputs',dirs_exist_ok=True)
    shutil.copyfile(manifest,frozen/'config.json')
    direction=e.orth(e.rng_for(cfg['initialization_seed']),cfg['n'])
    checks=[];hashes={};reference=None
    for rank in cfg['ranks']:
        s=load_original(cfg,rank)
        if reference is not None:
            for key in ('A','Q','R','W','U','V'):
                np.testing.assert_array_equal(s[key],reference[key])
        else:reference=s
        old_k=s['K0'].copy();lo=0.;hi=.01
        while True:
            gap,rho,_=performance_gap(s,s['Kstar']+hi*direction)
            if gap>=cfg['initial_gap']:break
            hi*=2
            assert hi<10
        for _ in range(70):
            mid=(lo+hi)/2
            gap,_,_=performance_gap(s,s['Kstar']+mid*direction)
            if gap<cfg['initial_gap']:lo=mid
            else:hi=mid
        alpha=(lo+hi)/2;k=s['Kstar']+alpha*direction
        gap,rho,covariance=performance_gap(s,k)
        f=s['A']-s['B']@k
        p=solve_discrete_lyapunov(f.T,s['Q']+k.T@s['R']@k)
        actual_gap=float(np.trace(p)-s['Jstar'])
        residual=float(np.max(abs(p-f.T@p@f-(s['Q']+k.T@s['R']@k))))
        assert abs(gap-cfg['initial_gap'])<1e-10 and abs(actual_gap-cfg['initial_gap'])<1e-10
        assert residual<1e-10 and rho<1 and np.linalg.matrix_rank(k,tol=1e-10)==cfg['n']
        assert np.linalg.matrix_rank(s['B'],tol=1e-10)==rank
        for scale in np.linspace(0,alpha,11):
            assert performance_gap(s,s['Kstar']+scale*direction)[1]<1
        exploration_covariance=solve_discrete_lyapunov(f,s['W']+cfg['sigma']**2*s['B']@s['B'].T)
        s.update(K0=k,K0_original=old_k,P0_original=s['P0'],F0_original=s['F0'],F0=f,P0=p,initial_gap=cfg['initial_gap'],
                 actual_initial_gap=actual_gap,initialization_direction=direction,initialization_alpha=alpha)
        path=out/'systems'/f'r{rank:03d}.npz';e.save_npz(path,**s);hashes[str(rank)]=e.sha(path)
        checks.append(dict(rank=rank,initial_gap=actual_gap,performance_identity_gap=gap,
            alpha=alpha,J0=float(np.trace(p)),Jstar=s['Jstar'],rho_K0=rho,
            K0_rank=int(np.linalg.matrix_rank(k,tol=1e-10)),certificate_residual=residual,
            exploration_state_covariance_trace=float(np.trace(exploration_covariance)),
            exploration_state_covariance_condition=float(np.linalg.cond(exploration_covariance)),
            original_input_sha256=cfg['system_artifact_sha256'][str(rank)]))
    e.atomic_json(out/'verification.json',dict(status='PASS',identity=ident,systems=checks,system_hashes=hashes,
        construction='Common independent full-rank orthogonal gain perturbation around each optimum; private system construction only',
        learner='Unchanged rank_sweep100.ce_task; no true subspace or Kstar supplied to OLS or DARE'))
    e.atomic_json(out/'resolved_config.json',dict(cfg,identity=ident))
    # Synthetic algebra fixture is not a trajectory or a primitive transition.
    rng=e.rng_for(2026101808);z=rng.normal(size=(800,2*cfg['n']))
    s,_=load_matched(cfg,2);theta=np.concatenate((s['A'],s['B']),axis=1)
    recovered=cho_solve(cho_factor(z.T@z),z.T@(z@theta.T)).T
    np.testing.assert_allclose(recovered,theta,atol=2e-12)
    # A bounded fault/restart comparison for low and full rank.
    diagnostic_transitions=0
    for rank in (2,100):
        paths={name:out/'diagnostics'/(name+f'-r{rank:03d}') for name in ('uninterrupted','resumed')}
        for name,dest in paths.items():
            budgets=[512,1024] if name=='uninterrupted' else [512]
            task(cfg,ident,'pilot',rank,9001,budgets,dest)
        partial=paths['resumed']/'raw'/f'ce-r{rank:03d}-s9001.json'
        partial.rename(partial.with_name('first-prefix-retained.json'))
        task(cfg,ident,'pilot',rank,9001,[512,1024],paths['resumed'])
        stem=f'ce-r{rank:03d}-s9001'
        with np.load(paths['uninterrupted']/'policies'/(stem+'.npz')) as x,np.load(paths['resumed']/'policies'/(stem+'.npz')) as y:
            np.testing.assert_array_equal(x['policies'],y['policies'])
        assert e.read(paths['uninterrupted']/'raw'/(stem+'.json'))['records']==e.read(paths['resumed']/'raw'/(stem+'.json'))['records']
        diagnostic_transitions+=2*(cfg['burn']+1024)
    benchmark=[]
    for rank in (2,100):
        start=time.monotonic()
        task(cfg,ident,'confirm',rank,9002,override_out=out/'diagnostics/maximum-budget-benchmark')
        benchmark.append(dict(rank=rank,seconds=time.monotonic()-start,transitions=cfg['burn']+max(cfg['confirm_budgets'])))
        diagnostic_transitions+=cfg['burn']+max(cfg['confirm_budgets'])
    import resource,platform
    e.atomic_json(out/'preflight.json',dict(status='PASS',identity=ident,benchmark=benchmark,
        checkpoint_resume_tests=2,synthetic_OLS_recovery_passed=True,
        diagnostic_primitive_transitions=diagnostic_transitions,
        peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        python=sys.executable,python_version=platform.python_version(),numpy=np.__version__,
        threadpools=threadpool_info(),slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS',systems=checks,benchmark=benchmark,diagnostic_transitions=diagnostic_transitions)),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','task','report'])
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--phase',choices=['pilot','confirm'],default='pilot')
    p.add_argument('--task-id',type=int);args=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID'),'New numerical work runs on Grace compute nodes'
    cfg=e.read(args.manifest);ident=identity(cfg);out=Path(cfg['output'])
    for name,wanted in [('TMPDIR',cfg['temp']),('NUMBA_CACHE_DIR',str(Path(cfg['cache'])/'numba')),('MPLCONFIGDIR',str(Path(cfg['cache'])/'matplotlib'))]:
        assert os.environ.get(name)==wanted,(name,wanted);Path(wanted).mkdir(parents=True,exist_ok=True)
    e.system=load_matched;e.innovations=innovations
    with threadpool_limits(1):
        if args.mode=='prepare':prepare(cfg,ident,args.manifest)
        elif args.mode=='task':
            assert e.read(out/'preflight.json')['status']=='PASS'
            assert e.read(out/'verification.json')['identity']==ident
            jobs=[(rank,seed) for seed in cfg[args.phase+'_seeds'] for rank in cfg['ranks']]
            rank,seed=jobs[args.task_id]
            result=task(cfg,ident,args.phase,rank,seed)
            e.atomic_json(out/'task_receipts'/f'{args.phase}-{args.task_id:03d}.json',
                dict(result,slurm_job_id=os.environ['SLURM_JOB_ID'],task_id=args.task_id,phase=args.phase))
            print(json.dumps(result),flush=True)
        else:
            from ce_matched_initial_gap_report import report
            report(cfg,ident,args.phase)


if __name__=='__main__':main()
