"""Independent unstable plants and a stability-only initial feedback.

The initializer has no cost matrices, optimal controller or policy evaluator.
It preserves the already-stable Schur block and places the unstable poles.
"""
import warnings

import numpy as np
from scipy.linalg import schur
from scipy.signal import place_poles


def rng(namespace, n, seed):
    return np.random.default_rng(np.random.SeedSequence([namespace, n, seed]))


def draw_plant(n, rank, seed, radius=1.05):
    # Disjoint independent streams: no A quantity enters the B generator.
    raw = rng(2026102291, n, seed).normal(size=(n, n)) / np.sqrt(n)
    a = raw * (radius / np.max(np.abs(np.linalg.eigvals(raw))))
    brng = rng(2026102292, n, seed)
    u = np.linalg.qr(brng.normal(size=(n, n)))[0]
    v = np.linalg.qr(brng.normal(size=(n, n)))[0]
    b = u[:, :rank] @ v[:, :rank].T
    return a, b


def initial_gain(a, b, rank, seed, prior_scale=0.1, pole_scale=0.8):
    """Return a stabilizer; no optimization of the experiment's objective."""
    n, m = b.shape
    prior = prior_scale * rng(2026102293, n, seed).normal(size=(m, n)) / np.sqrt(n)
    f = a - b @ prior
    # Stable FIRST is essential: the lower-left Schur block is then zero.
    # SciPy 1.13's built-in 'iuc' callback accepts only the real component
    # for a real Schur decomposition; use both components explicitly.
    t, z, stable_count = schur(f, output='real', sort=lambda wr, wi: wr*wr+wi*wi < 1.)
    unstable = n - stable_count
    assert unstable == int(np.count_nonzero(np.abs(np.linalg.eigvals(f)) >= 1.))
    meta = dict(unstable_poles_before_correction=unstable,
                prior_scale=prior_scale, pole_scale=pole_scale,
                uses_Kstar=False, uses_cost_matrices=False, gap_matching=False)
    if not unstable:
        k = prior
        meta.update(placement_iterations=0, placement_warnings=[])
    else:
        _, singular, vh = np.linalg.svd(b, full_matrices=False)
        assert singular[rank-1] > 1e-8
        assert rank == len(singular) or singular[rank] < 1e-8
        vr = vh[:rank].T
        zu = z[:, stable_count:]
        tu = t[stable_count:, stable_count:]
        bu = zu.T @ b @ vr
        poles = np.linalg.eigvals(tu)
        target = pole_scale / np.conj(poles)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            fitted = place_poles(tu, bu, target, method='YT', rtol=1e-8, maxiter=100)
        k = prior + vr @ fitted.gain_matrix @ zu.T
        meta.update(placement_iterations=int(fitted.nb_iter) if np.isfinite(fitted.nb_iter) else None,
                    placement_warnings=[str(w.message) for w in caught])
    radius_a = float(np.max(np.abs(np.linalg.eigvals(a))))
    radius_f = float(np.max(np.abs(np.linalg.eigvals(a-b@k))))
    meta.update(rho_A=radius_a, rho_F0=radius_f,
                K0_rank=int(np.linalg.matrix_rank(k)), K0_fro=float(np.linalg.norm(k)),
                correction_fro=float(np.linalg.norm(k-prior)))
    if not (radius_a > 1 and radius_f < 1-1e-10):
        raise ArithmeticError(str(meta))
    return k, meta
