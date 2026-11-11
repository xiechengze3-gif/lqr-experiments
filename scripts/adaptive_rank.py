"""Data-only hard SVD thresholds; split disagreement is an empirical proxy.

No true model, true rank, evaluation cost, or oracle subspace enters selection.
For two half-sample estimates M1/M2, ||M1-M2||_op/2 estimates the full-batch
noise scale under ideal equal-variance independent halves. Continuous-trajectory
dependence and LSTD nonlinearity mean this is NOT a confidence bound.
"""
import numpy as np
from dense_scaling import psd


def noise_proxy(first, second):
    return float(np.linalg.norm(first-second, 2)/2)


def select(matrix, method, scale=None, known_rank=None):
    u, singular, vt = np.linalg.svd(matrix, full_matrices=False)
    threshold = None
    if method == 'dense':
        rank = len(singular)
    elif method == 'known_rank':
        if known_rank is None or not 0 <= known_rank <= len(singular):
            raise ValueError('Valid known rank required for the reference arm')
        rank = known_rank
    elif method.startswith('adaptive_'):
        multiplier = float(method.split('_', 1)[1])
        if scale is None or not np.isfinite(scale) or scale < 0 or multiplier <= 0:
            raise ValueError('Finite nonnegative data-only noise scale required')
        threshold = multiplier*scale
        rank = int(np.count_nonzero(singular > threshold))
    else:
        raise ValueError(method)
    projected = (u[:, :rank]*singular[:rank])@vt[:rank]
    return projected, u[:, :rank], dict(retained_rank=rank, threshold=threshold,
        noise_proxy=scale, singular_values=singular.tolist(),
        threshold_type='empirical_split' if threshold is not None else 'reference')


def ce_update(a, b, q, r, method, scale=None, known_rank=None):
    from dense_scaling import dare
    bhat, _, info = select(b, method, scale, known_rank)
    k, _ = dare(a, bhat, q, r)
    return k, bhat, info


def pi_update(g, c, r, method, scale=None, known_rank=None):
    # Same [G,C] joint left projection and PSD clipping as established PI.
    _, u, info = select(np.concatenate((g, c), axis=1), method, scale, known_rank)
    if method == 'dense':
        gg, cc = psd(g), c.copy()
    else:
        gg = u@psd(u.T@g@u)@u.T
        cc = u@(u.T@c)
    return np.linalg.solve(r+gg, cc), gg, cc, info
