"""Nested-rank dense systems; identical A,Q,R,K0 within each system seed."""
import hashlib
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import rng_for, orth, op, dare, tails, require_compute


def array_hash(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def system(task):
    require_compute()
    n, rank = task['n'], task['r']
    assert task['m'] == n and 1 <= rank <= n
    rng = rng_for(773291, n, task['system_seed'])
    u, v, uq, ur = [orth(rng, n) for _ in range(4)]
    diagonal = rng.uniform(-.25, .55, n)
    diagonal[0] = 1.12
    latent = np.diag(diagonal) + .10*np.diag(np.ones(n-1), 1)
    latent += .025/np.sqrt(n)*rng.normal(size=(n,n))
    a = u@latent@u.T
    q = (uq*np.linspace(1.,3.,n))@uq.T
    r = (ur*np.linspace(1.,2.5,n))@ur.T
    singular = np.zeros(n); singular[:rank] = 1.2
    b = (u*singular)@v.T
    k0 = .35*v@u.T
    # Bounds are fixed across rank and seeds, not recomputed by the learner.
    f_bound = .925
    p0 = (3.+2.5*.35**2)/(1.-f_bound**2)
    f0 = a-b@k0
    kstar,pstar = dare(a,b,q,r)
    p_initial = solve_discrete_lyapunov(f0.T,q+k0.T@r@k0)
    s = dict(A=a,B=b,Q=q,R=r,W=np.eye(n),K0=k0,Kstar=kstar,
             Jstar=float(np.trace(pstar)),p0=p0)
    s['initial_gap'] = float(np.trace(p_initial)-s['Jstar'])
    assert op(f0) < f_bound and op(p_initial) < p0
    assert float(np.max(np.abs(np.linalg.eigvals(a)))) > 1.
    assert s['initial_gap'] > 0.
    s['diagnostics'] = dict(Jstar=s['Jstar'],initial_gap=s['initial_gap'],
        p0_bound=p0,p0_actual=op(p_initial),F0_op=op(f0),
        A_op=op(a),A_rho=float(np.max(np.abs(np.linalg.eigvals(a)))),
        B_op=op(b),B_fro2=float(np.sum(b*b)),K0_op=op(k0),
        Q_condition=3.,R_condition=2.5,
        A_nonnormality=op(a.T@a-a@a.T),Q_R_commutator=op(q@r-r@q),
        density={name:float(np.mean(np.abs(s[name])>1e-10))
                 for name in ('A','B','Q','R','K0')},
        hashes={name:array_hash(s[name]) for name in ('A','B','Q','R','K0')},
        B=tails(b,rank),Kstar=tails(kstar,rank),
        K0_spectrum=np.linalg.svd(k0,compute_uv=False).tolist())
    return s
