"""Direct Stein critic and damped PI, with an observation-only learner boundary.

Simulation and exact evaluation belong in the experiment runner. The critic
receives only observed block starts, Gaussian pulses and realized returns.
"""
import numpy as np
from scipy.linalg import cho_factor, cho_solve


def sufficient(starts, pulses, returns, previous, sigma):
    if sigma <= 0 or len(starts) != len(returns) or not len(returns):
        raise ValueError('Positive sigma and nonempty matching observations required')
    delta = np.diff(np.r_[previous, returns])
    labels = -pulses * delta[:, None] / (2*sigma**2)
    m = pulses.shape[1]
    return dict(gram=starts.T@starts, cross=labels.T@starts,
                curvature=((pulses*delta[:, None]).T@pulses
                           -sigma**2*delta.sum()*np.eye(m))/(2*sigma**4),
                count=len(returns))


def combine(a, b):
    return {key: a[key]+b[key] for key in a}


def fit(stats, rtol=1e-10):
    gram, cross = stats['gram'], stats['cross']
    z = cho_solve(cho_factor((gram+gram.T)/2), cross.T).T
    residual = np.linalg.norm(z@gram-cross)/max(np.linalg.norm(cross), 1e-30)
    if not np.isfinite(residual) or residual > rtol:
        raise np.linalg.LinAlgError('Critic normal-equation residual exceeds tolerance')
    g = stats['curvature']/stats['count']
    return (g+g.T)/2, z, dict(gram_condition=float(np.linalg.cond(gram)),
                              critic_relative_residual=float(residual))


def psd(g):
    eig, u = np.linalg.eigh((g+g.T)/2)
    return (u*np.maximum(eig, 0.))@u.T


def joint_matrix(g, z, weights=(1., 1.)):
    # Both blocks use the same predeclared weights in full and split estimates.
    if min(weights) <= 0:
        raise ValueError('Positive block weights required')
    return np.concatenate((g/weights[0], z/weights[1]), axis=1)


def correct(g, z, method, halves=None, known_rank=None, multiplier=1., weights=(1., 1.)):
    matrix = joint_matrix(g, z, weights)
    threshold = None
    if method == 'dense':
        rank = g.shape[0]
    elif method == 'known_rank':
        if known_rank is None or not 0 <= known_rank <= g.shape[0]:
            raise ValueError('Known rank outside action dimension')
        rank = known_rank
    elif method == 'adaptive':
        if halves is None or multiplier <= 0:
            raise ValueError('Adaptive needs observed half estimates and positive multiplier')
        threshold = multiplier*np.linalg.norm(joint_matrix(*halves[0], weights)
                                              -joint_matrix(*halves[1], weights), 2)/2
        rank = int(np.count_nonzero(np.linalg.svd(matrix, compute_uv=False) > threshold))
    else:
        raise ValueError(method)
    # Full-rank benchmark is exactly the dense code path, including roundoff.
    if rank == g.shape[0]:
        gg, zz = psd(g), z.copy()
    else:
        u = np.linalg.svd(matrix, full_matrices=False)[0][:, :rank]
        gg, zz = u@psd(u.T@g@u)@u.T, u@(u.T@z)
    return gg, zz, dict(retained_rank=rank, threshold=None if threshold is None else float(threshold),
                        raw_G_min_eigenvalue=float(np.linalg.eigvalsh((g+g.T)/2)[0]),
                        G_clip_change_fro=float(np.linalg.norm(gg-g)),
                        block_weights=list(weights))


def update(k, r, g, z, eta, solve_rtol=1e-10):
    if not 0 < eta <= 1:
        raise ValueError('Damped PI requires 0 < eta <= 1')
    lhs, rhs = r+g, r@k+z
    direction = cho_solve(cho_factor((lhs+lhs.T)/2), rhs)
    residual = np.linalg.norm(lhs@direction-rhs)/max(np.linalg.norm(rhs), 1e-30)
    if not np.isfinite(residual) or residual > solve_rtol:
        raise np.linalg.LinAlgError('PI solve residual exceeds tolerance')
    return k-eta*direction, dict(update_relative_residual=float(residual),
                                R_plus_G_condition=float(np.linalg.cond(lhs)))
