"""Unchanged frozen S-model and CE-prefix functions; portable imports only."""
import json
import numpy as np
from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov
import frozen_engine as e

def model(family, n, system):
    if family == 'U':
        return e.plant(n, n, 2, system, null_scale=0.)
    if family != 'S':
        raise ValueError(family)
    random = e.rng(1, n, system)
    rotation = e.haar(random, n)
    eigenvalues = random.uniform(.15, .60, n)
    a = (rotation * eigenvalues) @ rotation.T
    u = e.haar(e.rng(2, n, system), n)
    v = e.haar(e.rng(3, n, n, system), n)
    b = u[:, :2] @ v[:, :2].T
    eye = np.eye(n)
    k0 = np.zeros((n, n))
    p0 = solve_discrete_lyapunov(a.T, eye)
    ps = solve_discrete_are(a, b, eye, eye)
    ks = np.linalg.solve(eye + b.T @ ps @ b, b.T @ ps @ a)
    cert = dict(family='S', n=n, m=n, r=2, system=system,
                rho_A=float(np.max(np.abs(eigenvalues))),
                rho_F0=float(np.max(np.abs(eigenvalues))),
                P0_op=float(np.linalg.norm(p0, 2)),
                initial_gap=float(np.trace(p0-ps)), J0=float(np.trace(p0)),
                Jstar=float(np.trace(ps)), A_B_independent_streams=True,
                K0_action_energy_overlap=None,
                K0_action_column_subspace_overlap=None,
                K0_overlap_note='Zero gain: normalized overlaps are undefined.',
                initializer_uses_Q_R_Kstar_cost=False,
                A_eigenvalues=eigenvalues.tolist(), null_scale=0.)
    assert cert['P0_op'] <= 1.5625 + 1e-10
    return dict(A=a, B=b, Q=eye, R=eye, W=eye, K0=k0, P0=p0,
                Kstar=ks, Pstar=ps, basis=v[:, :2], certificate=cert)

def ce_prefixes(s, prefixes, random, config):
    """Exact 512-transition chunks and half-prefix stops of frozen ce_run."""
    n,m = s['B'].shape; k=s['K0']; nu=config['nu']; burn=config['ce_burn']
    f=np.ascontiguousarray(s['A']-s['B']@k); x=np.zeros(n)
    x,_,_=e.ce_chunk(f,s['B'],k,x,nu*random.normal(size=(burn,m)),
                    random.normal(size=(burn,n)))
    gram=np.zeros((n+m,n+m)); cross=np.zeros((n,n+m)); done=0
    for stop in sorted(set(prefixes)|{v//2 for v in prefixes}):
        while done<stop:
            count=min(512,stop-done)
            x,z,y=e.ce_chunk(f,s['B'],k,x,nu*random.normal(size=(count,m)),
                             random.normal(size=(count,n)))
            gram+=z.T@z; cross+=y.T@z; done+=count
        if done in prefixes:
            theta=e.fit_model(gram,cross)
            yield dict(N=done,x=x.copy(),Ahat=theta[:,:n],Bhat=theta[:,n:],
                       gram=gram.copy(),cross=cross.copy(),
                       rng_state=json.dumps(random.bit_generator.state,sort_keys=True))
