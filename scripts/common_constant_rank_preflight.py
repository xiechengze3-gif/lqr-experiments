"""Validate identical initial Lyapunov certificates across independent-A/B ranks.

No new trajectories, no optimal-controller solve, no cost-gap calibration.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time

import numpy as np
from scipy.linalg import solve_discrete_lyapunov


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def atomic(p,obj):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(p)


def main():
    assert os.environ.get('SLURM_JOB_ID')
    source=Path(sys.argv[1]);out=Path(sys.argv[2]);(out/'systems').mkdir(parents=True,exist_ok=True)
    proof=json.loads((source/'construction.json').read_text());assert proof['status']=='PASS'
    ranks=[2,4,8,32,500];source_meta={}
    for r in ranks:
        meta=next(v for v in proof['systems'] if v['n']==500 and v['rank']==r)
        assert not meta['uses_Kstar'] and not meta['gap_matching']
        assert sha(Path(meta['system_file']))==meta['system_sha256'];source_meta[r]=meta
    with np.load(source_meta[2]['system_file'],allow_pickle=False) as d:
        a,bsmall,oldk,q,rr,w=[d[k].copy() for k in ('A','B','K0','Q','R','W')]
    # Unit nonzero B singular values make B^T B its input-space projector.
    projector=bsmall.T@bsmall
    assert np.linalg.norm(projector@projector-projector)<1e-10
    k0=projector@oldk
    f0=a-bsmall@k0
    np.testing.assert_allclose(bsmall@k0,bsmall@oldk,rtol=0,atol=2e-12)
    s0=q+k0.T@rr@k0
    p0=solve_discrete_lyapunov(f0.T,s0)
    pmax=float(np.linalg.eigvalsh(p0)[-1]);kmax=float(np.linalg.norm(k0,2));chi=2*pmax
    rho=math.sqrt(1-1/chi);nu=2.
    supplied=dict(q=1.,mu_minus=1.,mu_plus=1.,w_minus=1.,w_plus=1.,b_B=1.,p_0=pmax,nu=nu)
    la=math.sqrt(2*pmax)*(chi+.5);lb=2*pmax*(rho*chi+1.5)
    lam=(1+nu**2)*chi/(1-rho*rho);gam=(1+nu**2)*chi*(1+rho)/(1-rho)
    mu0=min(1.,nu**2)/(1+kmax)**2;mm0=(1+kmax)**2*max(lam+1,nu**2)
    gamz=2*(1+kmax)**2*max(gam,nu**2)
    derived=dict(chi=chi,K0_op=kmax,rho_certificate=rho,NPG_eta=1/(1+2*pmax),
        L_A=la,L_B=lb,C_Sigma=2*(2*pmax)**2,h_star_upper=1+pmax,
        CE_mu0=mu0,CE_M0=mm0,CE_Gamma_z=gamz,CE_gamma_minus=mu0/2,CE_gamma_plus=mm0+mu0/2)
    rows=[];began=time.monotonic()
    for rank in ranks:
        with np.load(source_meta[rank]['system_file'],allow_pickle=False) as d:
            ar,br,qr,rrr,wr=[d[k].copy() for k in ('A','B','Q','R','W')]
        for lhs,rhs in [(ar,a),(qr,q),(rrr,rr),(wr,w)]:np.testing.assert_array_equal(lhs,rhs)
        # Check nesting directly from matrices; no basis reconstruction needed.
        nesting=float(np.linalg.norm(br@projector-bsmall))
        assert nesting<1e-10
        fr=ar-br@k0
        f_error=float(np.max(np.abs(fr-f0)));assert f_error<2e-12
        radius=float(np.max(np.abs(np.linalg.eigvals(fr))));assert radius<1-1e-10
        sr=qr+k0.T@rrr@k0
        certificate=float(np.linalg.norm(p0-fr.T@p0@fr-sr)/np.linalg.norm(p0));assert certificate<1e-9
        pr=solve_discrete_lyapunov(fr.T,sr)
        p_error=float(np.linalg.norm(pr-p0)/np.linalg.norm(p0));assert p_error<1e-8
        singular=np.linalg.svd(br,compute_uv=False)
        assert np.max(np.abs(singular[:rank]-1))<1e-10
        assert rank==500 or singular[rank]<1e-10
        path=out/'systems'/f'r{rank:03d}.npz'
        with path.open('wb') as handle:
            np.savez(handle,A=ar,B=br,Q=qr,R=rrr,W=wr,K0=k0,F0=f0,P0=p0,p0_bound=pmax)
        rows.append(dict(rank=rank,rho_A=float(np.max(np.abs(np.linalg.eigvals(ar)))),rho_F0=radius,
            B_op=float(singular[0]),K0_rank=int(np.linalg.matrix_rank(k0,tol=1e-9)),
            K0_op=kmax,P0_op_actual=float(np.linalg.eigvalsh(pr)[-1]),
            F0_max_error=f_error,P0_relative_difference=p_error,Lyapunov_relative_residual=certificate,
            B_nesting_residual=nesting,system_sha256=sha(path),
            A_array_sha256=hashlib.sha256(ar.tobytes()).hexdigest(),
            B_array_sha256=hashlib.sha256(br.tobytes()).hexdigest(),
            K0_array_sha256=hashlib.sha256(k0.tobytes()).hexdigest(),
            P0_array_sha256=hashlib.sha256(p0.tobytes()).hexdigest()))
        print(json.dumps(rows[-1]),flush=True)
    atomic(out/'verification.json',dict(status='PASS',rows=rows,supplied_constants=supplied,
        derived_constants=derived,A_B_unchanged_from_independent_draws=True,
        K0_F0_P0_common_across_all_ranks=True,initialization_uses_Kstar=False,
        initialization_uses_objective_optimization=False,initial_gap_matching=False,
        initialization='Project pre-existing rank2 stability-only gain onto the rank2 input space; share across ranks.',
        theoretical_note='Common supplied bounds give common system constants; no claim that all realized state covariances or Pstar coincide.',
        job=os.environ['SLURM_JOB_ID'],host=os.uname().nodename,seconds=time.monotonic()-began,
        maximum_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        source_construction_sha256=sha(source/'construction.json'),
        paths={k:os.environ.get(k) for k in ('TMPDIR','XDG_CACHE_HOME','MPLCONFIGDIR')}))


if __name__=='__main__':main()
