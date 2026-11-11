"""Full quadratic average-cost off-policy LSTD, without a dense p-by-p matrix.

Samples and critic coefficients stay in the original state/action coordinates.
No whitening, action subspace or low-rank critic restriction is used.
Centered instruments eliminate the unknown average reward; the next action
is the deterministic target policy.
"""
import time
import numpy as np
from scipy.sparse.linalg import LinearOperator, gmres


def svec(h):
    i, j = np.triu_indices(len(h))
    return h[i, j] * np.where(i == j, 1., np.sqrt(2.))


def smat(v, d):
    i, j = np.triu_indices(d)
    h = np.zeros((d, d))
    h[i, j] = v / np.where(i == j, 1., np.sqrt(2.))
    h[j, i] = h[i, j]
    return h


def solve(z, next_z, costs, rtol=1e-8, maxiter=10, restart=40):
    start = time.monotonic()
    count, d = z.shape
    p = d * (d + 1) // 2
    if count <= p + 1:
        return None, dict(converged=False, reason='underidentified_full_critic',
                          samples=count, coefficients=p, iterations=0,
                          coordinates='original', whitening=False)
    a, b = z, next_z
    mean = a.T @ a / count
    mean_cost = float(np.mean(costs))
    rhs_matrix = np.zeros((d, d))
    for lo in range(0, count, 4096):
        aa = a[lo:lo+4096]
        rhs_matrix += aa.T @ ((costs[lo:lo+4096] - mean_cost)[:, None] * aa)
    rhs = svec(rhs_matrix / count)

    def apply(v):
        h = smat(v, d)
        result, sum_delta = np.zeros((d, d)), 0.
        for lo in range(0, count, 4096):
            aa, bb = a[lo:lo+4096], b[lo:lo+4096]
            delta = np.einsum('ij,ij->i', aa @ h, aa)
            delta -= np.einsum('ij,ij->i', bb @ h, bb)
            result += aa.T @ (delta[:, None] * aa)
            sum_delta += float(np.sum(delta))
        return svec((result - mean * sum_delta) / count)

    operator = LinearOperator((p, p), matvec=apply, dtype=np.float64)
    residual_history = []
    estimate, info = gmres(operator, rhs, rtol=rtol, atol=0.,
        restart=restart, maxiter=maxiter, callback=residual_history.append,
        callback_type='pr_norm')
    residual = float(np.linalg.norm(apply(estimate)-rhs) / max(np.linalg.norm(rhs), 1e-30))
    diagnostics = dict(converged=bool(info == 0 and residual <= 2*rtol),
        solver_info=int(info), relative_residual=residual, coefficients=p,
        samples=count, iterations=len(residual_history),
        seconds=time.monotonic()-start, coordinates='original', whitening=False,
        residual_history=[float(x) for x in residual_history])
    return smat(estimate, d), diagnostics


def verify():
    # Independent explicit normal-equation check, including average-cost centering.
    rng = np.random.default_rng(92)
    z, nxt = rng.normal(size=(900, 8)), rng.normal(size=(900, 8)) * .2
    costs = rng.normal(size=900)
    estimate, diag = solve(z, nxt, costs)
    feature = lambda x: np.array([svec(np.outer(row, row)) for row in x])
    phi, psi = feature(z), feature(nxt)
    center = phi-phi.mean(axis=0)
    explicit = np.linalg.solve(center.T @ (phi-psi), center.T @ costs)
    assert diag['converged']
    assert np.allclose(svec(estimate), explicit, rtol=1e-7, atol=1e-9)
    # Noise-free Bellman data must recover a complete, dense critic exactly.
    h = rng.normal(size=(8, 8)); h = (h+h.T)/2
    y = np.einsum('ij,ij->i', z @ h, z) - np.einsum('ij,ij->i', nxt @ h, nxt) + 3.7
    recovered, diag = solve(z, nxt, y)
    assert diag['converged'] and np.allclose(recovered, h, rtol=1e-7, atol=1e-7)
    # Non-isotropic, correlated coordinates exercise the raw empirical operator.
    transform = np.diag(np.linspace(.7, 1.5, 8))
    transform[0, 1], transform[2, 5] = .3, -.2
    raw, raw_next = z @ transform, nxt @ transform
    raw_before, next_before = raw.copy(), raw_next.copy()
    estimate, diag = solve(raw, raw_next, costs)
    phi, psi = feature(raw), feature(raw_next)
    center = phi - phi.mean(axis=0)
    explicit = np.linalg.solve(center.T @ (phi-psi), center.T @ costs)
    assert diag['converged'] and diag['coordinates'] == 'original'
    assert diag['whitening'] is False and 'whitening_condition' not in diag
    assert np.allclose(svec(estimate), explicit, rtol=1e-6, atol=1e-8)
    assert np.array_equal(raw, raw_before) and np.array_equal(raw_next, next_before)
    y = (np.einsum('ij,ij->i', raw @ h, raw)
         - np.einsum('ij,ij->i', raw_next @ h, raw_next) + 3.7)
    recovered, diag = solve(raw, raw_next, y)
    assert diag['converged'] and np.allclose(recovered, h, rtol=1e-6, atol=1e-6)
    _, failed = solve(raw, raw_next, costs, maxiter=1, restart=1)
    assert not failed['converged'] and failed['relative_residual'] > 2e-8
    absent, underidentified = solve(raw[:37], raw_next[:37], costs[:37])
    assert absent is None and underidentified['reason'] == 'underidentified_full_critic'
    return dict(explicit_match=True, dense_bellman_recovery=True,
                original_coordinates_explicit_match=True,
                original_coordinates_dense_recovery=True, inputs_unchanged=True,
                nonconvergence_retained=True, underidentified_retained=True,
                coordinates='original', whitening=False)
