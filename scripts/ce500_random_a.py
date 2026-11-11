"""Fixed independent random full-rank A; reuse the unchanged trajectory CE."""
import argparse
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
from scipy.linalg import solve_discrete_lyapunov
from scipy.optimize import brentq
from threadpoolctl import threadpool_limits, threadpool_info
import rank_sweep100 as e
import ce500_matched_gap as run
from ce_matched_initial_gap import performance_gap

SOURCES = run.SOURCES + ['scripts/ce500_random_a.py']


def identity(cfg):
    ident = run.identity(cfg)
    ident['family_sources'] = {'scripts/ce500_random_a.py': e.sha(Path(__file__))}
    return ident


def prepare(cfg, ident, manifest):
    out = Path(cfg['output']); out.mkdir(parents=True, exist_ok=True)
    if (out/'preflight.json').exists():
        assert e.read(out/'preflight.json')['identity'] == ident
        return
    began = time.monotonic(); n = cfg['n']; eye = np.eye(n)
    raw = e.rng_for(cfg['A_seed']).normal(size=(n,n))/np.sqrt(n)
    raw_radius = float(max(abs(np.linalg.eigvals(raw))))
    a = cfg['A_spectral_radius']/raw_radius*raw
    singular_a = np.linalg.svd(a,compute_uv=False)
    rho_a = float(max(abs(np.linalg.eigvals(a))))
    assert np.linalg.matrix_rank(a,tol=1e-10) == n
    assert abs(rho_a-cfg['A_spectral_radius']) < 1e-11 and rho_a < 1
    brng = e.rng_for(cfg['B_seed']); u, v = e.orth(brng,n), e.orth(brng,n)
    direction = e.orth(e.rng_for(cfg['initialization_seed']),n)
    certificate_p = solve_discrete_lyapunov(a.T,eye)
    certificate_residual = float(np.max(abs(certificate_p-a.T@certificate_p@a-eye)))
    assert certificate_residual < 1e-10
    checks, hashes = [], {}
    for rank in cfg['ranks']:
        b = cfg['b']*u[:,:rank]@v[:,:rank].T
        np.testing.assert_allclose(np.linalg.svd(b,compute_uv=False)[:rank],cfg['b'],atol=2e-12)
        assert np.linalg.matrix_rank(b,tol=1e-10) == rank
        ks, ps = e.dare(a,b,eye,eye)
        s = dict(A=a.copy(),B=b,Q=eye,R=eye,W=eye,U=u,V=v,
                 Kstar=ks,Pstar=ps,Jstar=float(np.trace(ps)),initial_gap=cfg['initial_gap'],
                 initialization_direction=direction,K0_original=np.zeros((n,n)),
                 F0_original=a,P0_original=certificate_p)
        hi = .01
        while performance_gap(s,ks+hi*direction)[0] < cfg['initial_gap']:
            hi *= 2
        alpha = brentq(lambda x:performance_gap(s,ks+x*direction)[0]-cfg['initial_gap'],
                       0,hi,xtol=5e-15,rtol=1e-14)
        k0 = ks+alpha*direction; gap,rho,_ = performance_gap(s,k0)
        f0 = a-b@k0; p0 = solve_discrete_lyapunov(f0.T,eye+k0.T@k0)
        actual = float(np.trace(p0)-s['Jstar'])
        residual = float(np.max(abs(p0-f0.T@p0@f0-eye-k0.T@k0)))
        assert abs(gap-1)<1e-10 and abs(actual-1)<1e-9 and rho<1 and residual<1e-10
        assert np.linalg.matrix_rank(k0,tol=1e-10) == n
        np.testing.assert_array_equal(s['A'],a)
        exploration = solve_discrete_lyapunov(f0,eye+cfg['sigma']**2*b@b.T)
        s.update(K0=k0,P0=p0,F0=f0,actual_initial_gap=actual,initialization_alpha=alpha)
        path = out/'systems'/f'r{rank:03d}.npz'; e.save_npz(path,**s)
        hashes[str(rank)] = e.sha(path)
        svk = np.linalg.svd(ks,compute_uv=False)
        check = dict(rank=rank,initial_gap=actual,J0=float(np.trace(p0)),Jstar=s['Jstar'],
            rho_K0=rho,rho_A=rho_a,A_rank=n,B_rank=rank,K0_rank=n,alpha=alpha,
            A_operator_norm=float(singular_a[0]),A_smallest_singular_value=float(singular_a[-1]),
            B_operator_norm=cfg['b'],Pstar_op=float(np.linalg.eigvalsh(ps)[-1]),
            Kstar_operator_norm=float(svk[0]),Kstar_fro2=float(np.sum(ks**2)),
            certificate_P_op=float(np.linalg.eigvalsh(certificate_p)[-1]),
            certificate_residual=residual,zero_policy_certificate_residual=certificate_residual,
            exploration_covariance_trace=float(np.trace(exploration)),
            exploration_covariance_condition=float(np.linalg.cond(exploration)))
        checks.append(check);print(json.dumps(dict(prepared_rank=rank,**check)),flush=True)
    for rank in cfg['ranks']:
        with np.load(out/'systems'/f'r{rank:03d}.npz',allow_pickle=False) as z:
            np.testing.assert_array_equal(z['A'],a)
    for name in SOURCES:
        dest=out/'frozen'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    shutil.copyfile(manifest,out/'frozen/config.json')
    e.atomic_json(out/'verification.json',dict(status='PASS',identity=ident,systems=checks,
        system_hashes=hashes,A_is_common_across_ranks=True,A_independent_of_B_by_construction=True,
        A_family='real iid Gaussian, scaled once to spectral radius 0.85; no rejection',
        A_seed=cfg['A_seed'],B_seed=cfg['B_seed'],raw_A_spectral_radius=raw_radius))
    e.atomic_json(out/'resolved_config.json',dict(cfg,identity=ident))
    audits=[];physical=0
    for rank in (cfg['ranks'][0],n):
        s=run.load_system(cfg,rank);pulse,noise=run.rngs(cfg,9000);count=4096
        f=np.ascontiguousarray(s['F0'])
        x,_=e.nominal_chunk(f,np.zeros(n),noise.normal(size=(cfg['burn'],n)))
        pulses=cfg['sigma']*pulse.normal(size=(count,n));noises=noise.normal(size=(count,n))
        _,z,y=e.ce_chunk(f,s['B'],s['K0'],x,pulses,noises)
        truth=np.concatenate((s['A'],s['B']),axis=1)
        direct=np.linalg.lstsq(z,y,rcond=None)[0].T
        sufficient=run.cho_solve(run.cho_factor(z.T@z),(y.T@z).T).T
        err=float(np.max(abs(direct-sufficient)))
        noiseless=float(np.max(abs(np.linalg.lstsq(z,y-noises,rcond=None)[0].T-truth)))
        label=float(np.max(abs(y-z@truth.T-noises)))
        assert max(err,noiseless,label)<2e-11
        audits.append(dict(rank=rank,raw_joint_OLS_error=err,noiseless_AB_error=noiseless,label_error=label))
        physical+=count+cfg['burn']
    rank=cfg['ranks'][0]
    for label,budgets in (('continuous',[2048,4096]),('resumed',[2048]),('resumed',[2048,4096])):
        run.task(cfg,ident,rank,9001,budgets,out/'diagnostics'/label)
    aa=e.read(out/'diagnostics/continuous/raw'/f'ce-r{rank:03d}-s9001.json')
    bb=e.read(out/'diagnostics/resumed/raw'/f'ce-r{rank:03d}-s9001.json')
    assert aa['records']==bb['records']
    for name in ('x','gram','cross'):
        with np.load(out/'diagnostics/continuous/checkpoints'/f'ce-r{rank:03d}-s9001.npz') as aa, np.load(out/'diagnostics/resumed/checkpoints'/f'ce-r{rank:03d}-s9001.npz') as bb:
            np.testing.assert_array_equal(aa[name],bb[name])
    physical+=2*(4096+cfg['burn'])
    for rank in (cfg['ranks'][0],n):
        run.task(cfg,ident,rank,9002,[131072],out/'diagnostics/benchmark')
        physical+=131072+cfg['burn']
    e.atomic_json(out/'preflight.json',dict(status='PASS',identity=ident,seconds=time.monotonic()-began,
        raw_identification_audit=audits,checkpoint_resume_bitwise_equal=True,
        diagnostic_primitive_transitions=physical,peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        threadpools=threadpool_info(),slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS',preflight_seconds=time.monotonic()-began)),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','task'])
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--phase',choices=['pilot','confirm'],default='pilot')
    p.add_argument('--task-id',type=int);args=p.parse_args();assert os.environ.get('SLURM_JOB_ID')
    cfg=e.read(args.manifest);ident=identity(cfg)
    for key,expected in [('TMPDIR',cfg['temp']),('XDG_CACHE_HOME',cfg['cache']),
                         ('NUMBA_CACHE_DIR',cfg['cache']+'/numba'),('MPLCONFIGDIR',cfg['cache']+'/matplotlib')]:
        assert os.environ.get(key)==expected;Path(expected).mkdir(parents=True,exist_ok=True)
    with threadpool_limits(1):
        if args.mode=='prepare':prepare(cfg,ident,args.manifest)
        else:
            assert e.read(Path(cfg['output'])/'preflight.json')['identity']==ident
            seeds=cfg[args.phase+'_seeds'];rank=cfg['ranks'][args.task_id//len(seeds)];seed=seeds[args.task_id%len(seeds)]
            budgets=cfg['pilot_budgets'] if args.phase=='pilot' else e.read(Path(cfg['output'])/'formal_plan.json')['budgets_by_rank'][str(rank)]
            result=run.task(cfg,ident,rank,seed,budgets)
            e.atomic_json(Path(cfg['output'])/'task_receipts'/f'{args.phase}-{args.task_id:03d}.json',
                dict(result,phase=args.phase,task_id=args.task_id,slurm_job_id=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':main()
