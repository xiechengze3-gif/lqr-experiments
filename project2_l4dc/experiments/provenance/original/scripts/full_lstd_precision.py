"""Original-coordinate full LSTD with uniform, more generous Krylov budgets.

No whitening, regularization or low-rank critic restriction. Both attempts
solve the identical centered empirical equation; acceptance uses its residual.
"""
import time
import numpy as np
from scipy.sparse.linalg import LinearOperator, gmres
from full_lstd import svec, smat


def solve(z,next_z,costs,rtol=1e-8,attempts=((100,20),(200,20))):
    start=time.monotonic();count,d=z.shape;p=d*(d+1)//2
    if count<=p+1:
        return None,dict(converged=False,reason='underidentified_full_critic',samples=count,
                         coefficients=p,iterations=0,coordinates='original',whitening=False)
    mean=z.T@z/count;mean_cost=float(np.mean(costs));rhs_matrix=np.zeros((d,d))
    for lo in range(0,count,4096):
        aa=z[lo:lo+4096]
        rhs_matrix+=aa.T@((costs[lo:lo+4096]-mean_cost)[:,None]*aa)
    rhs=svec(rhs_matrix/count)
    def apply(v):
        h=smat(v,d);result=np.zeros((d,d));total=0.
        for lo in range(0,count,4096):
            aa,bb=z[lo:lo+4096],next_z[lo:lo+4096]
            delta=np.einsum('ij,ij->i',aa@h,aa)-np.einsum('ij,ij->i',bb@h,bb)
            result+=aa.T@(delta[:,None]*aa);total+=float(np.sum(delta))
        return svec((result-mean*total)/count)
    operator=LinearOperator((p,p),matvec=apply,dtype=np.float64)
    estimate=None;records=[];converged=False
    for restart,maxiter in attempts:
        history=[];wall=time.monotonic()
        estimate,info=gmres(operator,rhs,x0=estimate,rtol=rtol,atol=0.,restart=restart,
            maxiter=maxiter,callback=history.append,callback_type='pr_norm')
        residual=float(np.linalg.norm(apply(estimate)-rhs)/max(np.linalg.norm(rhs),1e-30))
        converged=bool(info==0 and residual<=2*rtol)
        records.append(dict(restart=restart,max_cycles=maxiter,iterations=len(history),
            solver_info=int(info),relative_residual=residual,converged=converged,
            seconds=time.monotonic()-wall,residual_history=[float(x) for x in history]))
        if converged:break
    diag=dict(converged=converged,attempts=records,relative_residual=residual,
        iterations=sum(r['iterations'] for r in records),samples=count,coefficients=p,
        seconds=time.monotonic()-start,coordinates='original',whitening=False,
        regularization=False,low_rank_critic=False)
    return smat(estimate,d),diag


def verify():
    rng=np.random.default_rng(421)
    z=rng.normal(size=(1400,8));nxt=.25*rng.normal(size=z.shape)
    transform=np.diag(np.linspace(.5,1.7,8));transform[0,3]=.3
    z,nxt=z@transform,nxt@transform
    costs=rng.normal(size=len(z))
    h,diag=solve(z,nxt,costs)
    phi=np.asarray([svec(np.outer(x,x)) for x in z])
    psi=np.asarray([svec(np.outer(x,x)) for x in nxt])
    center=phi-phi.mean(axis=0)
    expected=np.linalg.solve(center.T@(phi-psi),center.T@costs)
    assert diag['converged'] and np.allclose(svec(h),expected,rtol=1e-6,atol=1e-8)
    known=rng.normal(size=(8,8));known=(known+known.T)/2
    labels=np.einsum('ij,ij->i',z@known,z)-np.einsum('ij,ij->i',nxt@known,nxt)+4.3
    # Exact coefficient recovery uses a tighter residual than noisy production
    # solves; the correlated raw coordinates amplify a 1e-8 residual slightly.
    recovered,diag=solve(z,nxt,labels,rtol=1e-11)
    assert diag['converged'] and np.allclose(recovered,known,rtol=1e-6,atol=1e-7)
    _,failed=solve(z,nxt,costs,attempts=((1,1),))
    assert not failed['converged']
    return dict(original_equation_explicit_match=True,dense_bellman_recovery=True,
                genuine_residual_failure_retained=True,whitening=False)
