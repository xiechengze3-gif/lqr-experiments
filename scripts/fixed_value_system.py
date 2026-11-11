"""Controlled contrasts in spectra, dynamics, rank, costs and supplied K0."""
import hashlib
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import rng_for,orth,dare


def digest(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def system(task):
    n,r=task['n'],task['r'];rng=rng_for(202610130,n,task['system_seed'])
    o,u,v,uq,ur=[orth(rng,n) for _ in range(5)]
    family=task['family'];q=rr=np.eye(n);qmax=rmax=1.
    if family=='anisotropic':
        q=(uq*np.linspace(1.,3.,n))@uq.T;rr=(ur*np.linspace(1.,3.,n))@ur.T
        qmax=rmax=3.
    if family in ('orthogonal','anisotropic'):
        a=.8*o
    else:
        lat_rng=rng_for(202610131,n,task['system_seed'])
        diagonal=lat_rng.uniform(-.4,.6,n)
        if family=='unstable':
            diagonal[0]=1.08;diagonal[1:min(8,n)]=.72
            latent=np.diag(diagonal)+.04*np.diag(np.ones(n-1),1)
            perturb=lat_rng.normal(size=(n,n));latent+=.02*perturb/np.linalg.norm(perturb,2)
        elif family=='nonnormal':
            latent=np.diag(diagonal)+.4*np.diag(np.ones(n-1),1)
            perturb=lat_rng.normal(size=(n,n));latent+=.02*perturb/np.linalg.norm(perturb,2)
            latent*=.8/np.linalg.norm(latent,2)
        else:raise ValueError(family)
        a=u@latent@u.T
    singular=np.ones(n);spectrum=task['spectrum']
    if spectrum=='exact':singular[r:]=0.
    elif spectrum=='tail003':singular[r:]=.03
    elif spectrum=='tail010':singular[r:]=.1
    elif spectrum=='decay':singular[r:]=.3*np.arange(1,n-r+1,dtype=float)**(-.7)
    elif spectrum!='flat':raise ValueError(spectrum)
    b=(u*singular)@v.T
    ko=orth(rng_for(202610132,n,task['system_seed'],task['policy_seed']),n)
    if family=='unstable':
        strength=(.30,.40,.50)[task['policy_seed']]
        k0=strength*v@u.T+.015*ko
        fbound,kbound=.855,.515
    else:
        strength=task['initial_strength'];k0=strength*ko
        fbound,kbound=.92,.12
    pbar=(qmax+rmax*kbound**2)/(1-fbound**2)
    eta=.5/(rmax+2*pbar)
    ks,ps=dare(a,b,q,rr);f=a-b@k0
    pinit=solve_discrete_lyapunov(f.T,q+k0.T@rr@k0)
    s=dict(A=a,B=b,Q=q,R=rr,W=np.eye(n),K0=k0,Kstar=ks,Jstar=float(np.trace(ps)),
           initial_gap=float(np.trace(pinit-ps)))
    sr,_=np.linalg.qr(np.linalg.solve(rr,v[:,:r]));outside=k0-sr@(sr.T@k0)
    true_rank=int(np.count_nonzero(singular>1e-10))
    diag=dict(matrix_sha256={k:digest(s[k]) for k in ('A','B','Q','R','W','K0')},
        A_rho=float(np.max(np.abs(np.linalg.eigvals(a)))),A_op=float(np.linalg.norm(a,2)),
        A_nonnormality=float(np.linalg.norm(a.T@a-a@a.T,2)),
        Q_condition=float(np.linalg.cond(q)),R_condition=float(np.linalg.cond(rr)),
        initial_rho=float(np.max(np.abs(np.linalg.eigvals(f)))),initial_F_op=float(np.linalg.norm(f,2)),
        initial_P_op=float(np.linalg.norm(pinit,2)),initial_certificate=pbar,npg_eta=eta,
        initial_K_rank=int(np.linalg.matrix_rank(k0)),initial_strength_actual=strength,
        initial_outside_leading_R_subspace_fraction=float(np.sum(outside**2)/np.sum(k0**2)),
        outside_true_effective_subspace=true_rank<n,B_true_rank=true_rank,
        B_singular=singular.tolist(),tail_op=float(singular[r]) if r<n else 0.,
        tail_fro2=float(np.sum(singular[r:]**2)),Jstar=s['Jstar'],initial_gap=s['initial_gap'])
    assert diag['initial_K_rank']==n and diag['initial_rho']<1
    assert diag['initial_F_op']<=fbound+1e-9 and diag['initial_P_op']<=pbar+1e-8
    assert diag['initial_outside_leading_R_subspace_fraction']>.5
    if family=='unstable':assert diag['A_rho']>1
    return s,diag
