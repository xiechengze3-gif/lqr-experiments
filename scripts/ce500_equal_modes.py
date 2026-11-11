"""Equal scalar difficulty in every actuated mode; unchanged trajectory CE."""
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

SOURCES = run.SOURCES + ['scripts/ce500_equal_modes.py']


def identity(cfg):
    result = run.identity(cfg)
    result['family_sources'] = {'scripts/ce500_equal_modes.py':e.sha(Path(__file__))}
    return result


def prepare(cfg, ident, manifest):
    out = Path(cfg['output']); out.mkdir(parents=True, exist_ok=True)
    if (out/'preflight.json').exists():
        assert e.read(out/'preflight.json')['identity'] == ident
        return
    began = time.monotonic(); n = cfg['n']; eye = np.eye(n)
    source = Path(cfg['source_output'])/'systems/r002.npz'
    assert e.sha(source) == cfg['source_system_sha256']
    with np.load(source, allow_pickle=False) as data:
        u, v, direction = [data[key].copy() for key in ('U','V','initialization_direction')]
    on, off, b = cfg['a_controlled'], cfg['a_uncontrolled'], cfg['b']
    assert b == 1.0 and abs(off) < 1 and on > 1
    p_on = (on**2 + np.sqrt(on**4+4))/2
    p_off = 1/(1-off**2); kappa = on*p_on/(1+p_on)
    checks, hashes = [], {}
    for rank in cfg['ranks']:
        projector = u[:,:rank]@u[:,:rank].T
        actuation = u[:,:rank]@v[:,:rank].T
        a = off*eye + (on-off)*projector
        ks = kappa*actuation.T
        ps = p_off*eye + (p_on-p_off)*projector
        cert_k = cfg['certificate_feedback']*actuation.T
        cert_f = a-actuation@cert_k
        cert_p = solve_discrete_lyapunov(cert_f.T, eye+cert_k.T@cert_k)
        s = dict(A=a, B=actuation, Q=eye, R=eye, W=eye, U=u, V=v,
                 Kstar=ks, Pstar=ps, Jstar=float(np.trace(ps)), initial_gap=1.0,
                 initialization_direction=direction, K0_original=cert_k,
                 F0_original=cert_f, P0_original=cert_p)
        dk, dp = e.dare(a,actuation,eye,eye)
        analytic_error = max(float(np.max(abs(dk-ks))),float(np.max(abs(dp-ps))))
        assert analytic_error < 2e-11
        hi=.01
        while performance_gap(s,ks+hi*direction)[0] < cfg['initial_gap']:
            hi*=2
        alpha = brentq(lambda x:performance_gap(s,ks+x*direction)[0]-cfg['initial_gap'],
                       0,hi,xtol=5e-15,rtol=1e-14)
        k0=ks+alpha*direction; gap,rho,_=performance_gap(s,k0)
        f0=a-actuation@k0
        p0=solve_discrete_lyapunov(f0.T,eye+k0.T@k0)
        actual=float(np.trace(p0)-s['Jstar'])
        residual=float(np.max(abs(p0-f0.T@p0@f0-eye-k0.T@k0)))
        sv=np.linalg.svd(ks,compute_uv=False)
        np.testing.assert_allclose(sv[:rank],kappa,atol=1e-12)
        assert np.linalg.matrix_rank(actuation,tol=1e-10)==rank
        assert np.linalg.matrix_rank(k0,tol=1e-10)==n
        assert abs(gap-1)<1e-10 and abs(actual-1)<1e-9 and rho<1 and residual<1e-10
        np.testing.assert_allclose(a@u[:,:rank],on*u[:,:rank],atol=1e-12)
        if rank<n:
            np.testing.assert_allclose(a@u[:,rank:],off*u[:,rank:],atol=1e-12)
        np.testing.assert_allclose(cert_f@u[:,:rank],.75*u[:,:rank],atol=1e-12)
        exploration=solve_discrete_lyapunov(f0,eye+cfg['sigma']**2*actuation@actuation.T)
        s.update(K0=k0,P0=p0,F0=f0,actual_initial_gap=actual,initialization_alpha=alpha)
        system_path=out/'systems'/f'r{rank:03d}.npz';e.save_npz(system_path,**s)
        hashes[str(rank)]=e.sha(system_path)
        check=dict(rank=rank,initial_gap=actual,J0=float(np.trace(p0)),Jstar=s['Jstar'],
                   rho_K0=rho,rho_A=on,unstable_modes=rank,B_rank=rank,K0_rank=n,alpha=alpha,
                   Kstar_nonzero_singular_value=kappa,Pstar_op=p_on,
                   certificate_P_op=float(np.linalg.eigvalsh(cert_p)[-1]),
                   analytic_DARE_max_error=analytic_error,certificate_residual=residual,
                   exploration_covariance_trace=float(np.trace(exploration)),
                   exploration_covariance_condition=float(np.linalg.cond(exploration)))
        checks.append(check);print(json.dumps(dict(prepared_rank=rank,**check)),flush=True)
    for name in SOURCES:
        dest=out/'frozen'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    shutil.copyfile(manifest,out/'frozen/config.json')
    e.atomic_json(out/'verification.json',dict(status='PASS',identity=ident,systems=checks,system_hashes=hashes,
        scalar_controlled_P=p_on,scalar_uncontrolled_P=p_off,scalar_optimal_K=kappa,
        source_system_sha256=e.sha(source),A_is_common_across_ranks=False))
    e.atomic_json(out/'resolved_config.json',dict(cfg,identity=ident))
    audit=[];physical=0
    for rank in (cfg['ranks'][0],n):
        s=run.load_system(cfg,rank);pulse,noise=run.rngs(cfg,9000)
        f=np.ascontiguousarray(s['F0']);count=4096
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
        audit.append(dict(rank=rank,raw_joint_OLS_error=err,noiseless_AB_error=noiseless,label_error=label))
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
    # Representative complete solve plus larger collector prefix, measured before pilot.
    for rank in (cfg['ranks'][0],n):
        run.task(cfg,ident,rank,9002,[131072],out/'diagnostics/benchmark')
        physical+=131072+cfg['burn']
    e.atomic_json(out/'preflight.json',dict(status='PASS',identity=ident,seconds=time.monotonic()-began,
        raw_identification_audit=audit,checkpoint_resume_bitwise_equal=True,
        diagnostic_primitive_transitions=physical,peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        threadpools=threadpool_info(),slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS',preflight_seconds=time.monotonic()-began)),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','task'])
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--phase',choices=['pilot','confirm'],default='pilot');p.add_argument('--task-id',type=int)
    args=p.parse_args();assert os.environ.get('SLURM_JOB_ID')
    cfg=e.read(args.manifest);ident=identity(cfg)
    for key,expected in [('TMPDIR',cfg['temp']),('XDG_CACHE_HOME',cfg['cache']),
                         ('NUMBA_CACHE_DIR',cfg['cache']+'/numba'),('MPLCONFIGDIR',cfg['cache']+'/matplotlib')]:
        assert os.environ.get(key)==expected;Path(expected).mkdir(parents=True,exist_ok=True)
    with threadpool_limits(1):
        if args.mode=='prepare':prepare(cfg,ident,args.manifest)
        else:
            assert e.read(Path(cfg['output'])/'preflight.json')['identity']==ident
            seeds=cfg[args.phase+'_seeds'];rank=cfg['ranks'][args.task_id//len(seeds)]
            seed=seeds[args.task_id%len(seeds)]
            budgets=cfg['pilot_budgets'] if args.phase=='pilot' else e.read(Path(cfg['output'])/'formal_plan.json')['budgets_by_rank'][str(rank)]
            result=run.task(cfg,ident,rank,seed,budgets)
            e.atomic_json(Path(cfg['output'])/'task_receipts'/f'{args.phase}-{args.task_id:03d}.json',
                          dict(result,phase=args.phase,task_id=args.task_id,slurm_job_id=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':main()
