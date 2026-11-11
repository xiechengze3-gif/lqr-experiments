"""Dense 50d systems with independent full-rank supplied stabilizers."""
import hashlib
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import rng_for, orth, dare


def matrix_sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def system(task, cfg):
    n, rank = task['n'], task['r']
    rng=rng_for(202610121, n, task['system_seed'])
    o,u,v=[orth(rng,n) for _ in range(3)]
    singular=np.ones(n)
    singular[rank:]=task['tail']
    a,b=cfg['alpha']*o,(u*singular)@v.T
    # This independent rotation has no access to B, U or V; all singular
    # values of supplied K0 equal strength, so K0 exposes no rank-r subspace.
    ko=orth(rng_for(202610122,n,task['system_seed'],task['policy_seed']),n)
    k0=task['initial_strength']*ko
    q,r=np.eye(n),np.eye(n)
    ks,ps=dare(a,b,q,r)
    f=a-b@k0
    p0=solve_discrete_lyapunov(f.T,q+k0.T@r@k0)
    s=dict(A=a,B=b,Q=q,R=r,W=np.eye(n),K0=k0,Kstar=ks,
           Jstar=float(np.trace(ps)),initial_gap=float(np.trace(p0)-np.trace(ps)))
    outside=(np.eye(n)-v[:,:rank]@v[:,:rank].T)@k0
    bound=cfg['initial_certificate']
    diag=dict(matrix_sha256={k:matrix_sha(s[k]) for k in ('A','B','Q','R','W','K0')},
        initial_radius=float(np.max(np.abs(np.linalg.eigvals(f)))),
        initial_F_op=float(np.linalg.norm(f,2)),initial_P_op=float(np.linalg.norm(p0,2)),
        initial_certificate=bound,initial_K_singular=np.linalg.svd(k0,compute_uv=False).tolist(),
        initial_K_rank=int(np.linalg.matrix_rank(k0)),initial_gap=s['initial_gap'],
        initial_outside_effective_subspace_fro2=float(np.sum(outside**2)),
        initial_outside_fraction=float(np.sum(outside**2)/np.sum(k0**2)),
        B_singular=singular.tolist(),effective_rank=rank,tail_op=float(task['tail']),
        tail_fro2=float((n-rank)*task['tail']**2),Jstar=s['Jstar'])
    assert diag['initial_K_rank']==n
    assert diag['initial_radius']<1 and diag['initial_P_op']<=bound*(1+1e-10)
    assert diag['initial_outside_effective_subspace_fro2']>0
    assert np.isclose(diag['initial_outside_fraction'],(n-rank)/n)
    return s,diag
