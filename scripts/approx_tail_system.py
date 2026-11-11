"""Dense nested-rank LQR; numerical construction requires Grace Slurm."""
import hashlib
import json
import math
import os
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import (orth, op, dare, rng_for, tails, require_compute, atomic_json)


F_BOUND = .85
K_BOUND = .35
P_BOUND = (3.+2.5*K_BOUND**2)/(1.-F_BOUND**2)
ETA = .5/(2.5+2.*P_BOUND)


def digest(matrix):
    return hashlib.sha256(np.ascontiguousarray(matrix).tobytes()).hexdigest()


def system(task):
    require_compute()
    cache=os.environ.get('LQR_TAIL_SYSTEM_CACHE')
    cache_base=Path(cache)/f"task-{task['id']:03d}" if cache and task['id']>=0 else None
    source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if cache_base is not None and cache_base.with_suffix('.json').exists():
        metadata=json.loads(cache_base.with_suffix('.json').read_text())
        assert metadata['task']==task and metadata['source_sha256']==source_hash
        archive=cache_base.with_suffix('.npz')
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==metadata['npz_sha256']
        with np.load(archive,allow_pickle=False) as values:
            s={key:float(values[key]) if values[key].ndim==0 else values[key].copy() for key in values.files}
        s['diagnostics']=metadata['diagnostics']
        for key,expected in s['diagnostics']['matrix_sha256'].items():
            assert digest(s[key])==expected
        return s
    if cache_base is not None and os.environ.get('LQR_TAIL_BUILD_CACHE')!='1':
        raise RuntimeError('Frozen system cache missing; production cannot regenerate matrices')
    n, rank = task['n'], task['r']
    assert task['m'] == n and 1 <= rank <= n
    rng = rng_for(202610081, n, task['system_seed'])
    u, v, uq, ur = [orth(rng, n) for _ in range(4)]
    q = (uq*np.linspace(1., 3., n))@uq.T
    rr = (ur*np.linspace(1., 2.5, n))@ur.T
    diagonal = rng.uniform(-.4, .55, n)
    diagonal[0] = 1.10
    dense = rng.normal(size=(n, n))
    # Exact operator bounds, with nonnormal coupling and independent dense costs.
    latent = np.diag(diagonal)+.06*np.diag(np.ones(n-1), 1)+.04*dense/op(dense)
    a, k0 = u@latent@u.T, .35*v@u.T
    level, mode = task['level'], task['tail_mode']
    if mode == 'exact':
        assert level == 0
        single = 0.
    elif mode == 'singular':
        single = level
    elif mode == 'relative':
        single = level*math.sqrt(rank/(n-rank))
    elif mode == 'frobenius':
        single = level/math.sqrt(n-rank)
    else:
        raise ValueError(mode)
    assert 0 <= single <= 1 and (rank < n or single == 0)
    spectrum = np.full(n, single)
    spectrum[:rank] = 1.
    b = (u*spectrum)@v.T
    kstar, pstar = dare(a, b, q, rr)
    f = a-b@k0
    pinit = solve_discrete_lyapunov(f.T, q+k0.T@rr@k0)
    rho = float(np.max(np.abs(np.linalg.eigvals(a))))
    if rho <= 1 or op(f) > F_BOUND+1e-10 or op(pinit) > P_BOUND+1e-9:
        raise ArithmeticError('Dense nested-rank initial certificate failed')
    tail_energy = (n-rank)*single**2
    s = dict(A=a, B=b, Q=q, R=rr, W=np.eye(n), K0=k0, Kstar=kstar,
             Jstar=float(np.trace(pstar)), initial_gap=float(np.trace(pinit-pstar)), p0=P_BOUND)
    assert s['initial_gap'] > 0
    s['diagnostics'] = dict(A_rho=rho, A_op=op(a), F0_op=op(f),
        Q_condition=3., R_condition=2.5, K0_op=.35, B_op=op(b),
        head_singular_values=[1.]*rank, tail_singular=single,
        tail_energy=tail_energy, tail_fro=math.sqrt(tail_energy),
        relative_tail=math.sqrt(tail_energy/rank), P0_op=op(pinit),
        uniform_F_bound=F_BOUND, uniform_P_bound=P_BOUND, common_eta=ETA,
        density={key: float(np.mean(np.abs(s[key]) > 1e-10)) for key in ('A','B','Q','R','K0')},
        A_nonnormality=op(a.T@a-a@a.T), Q_R_commutator=op(q@rr-rr@q),
        matrix_sha256={key: digest(s[key]) for key in ('A','B','Q','R','K0')},
        B_spectrum=tails(b, rank)['spectrum'])
    if cache_base is not None:
        cache_base.parent.mkdir(parents=True,exist_ok=True)
        temp=cache_base.with_suffix(f'.{os.getpid()}.npz')
        with temp.open('wb') as stream:
            np.savez_compressed(stream,**{key:value for key,value in s.items() if key!='diagnostics'})
        archive=cache_base.with_suffix('.npz')
        os.replace(temp,archive)
        atomic_json(cache_base.with_suffix('.json'),dict(task=task,diagnostics=s['diagnostics'],
            source_sha256=source_hash,npz_sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
    return s
