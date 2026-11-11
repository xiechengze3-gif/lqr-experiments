"""X8: CE rank sweep (b) and spectrum sweep (c). See PROTOCOL.md. Writes raw per-run gaps to CSV."""
import sys, json, time
import numpy as np
from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov
from scipy.stats import ortho_group

n = m = 48
BURN = 512
NGRID = [2 ** p for p in range(9, 19)]
SYS, SEEDS = range(8), range(4)


def haar(d, rng):
    return ortho_group.rvs(d, random_state=rng)


def make_A(sys_seed):
    rng = np.random.default_rng(10_000 + sys_seed)
    Q = haar(n, rng)
    lam = rng.uniform(0.15, 0.6, n)
    return Q @ np.diag(lam) @ Q.T


def make_B(sigma, sys_seed):
    rng = np.random.default_rng(20_000 + sys_seed)
    U = haar(n, rng); V = haar(m, rng)
    s = np.zeros(min(n, m)); s[:len(sigma)] = sigma
    return U[:, :len(s)] @ np.diag(s) @ V[:, :len(s)].T


def cost(A, B, K):
    F = A - B @ K
    if np.max(np.abs(np.linalg.eigvals(F))) >= 1 - 1e-12:
        return np.inf
    P = solve_discrete_lyapunov(F.T, np.eye(n) + K.T @ K)
    return float(np.trace(P))


def lqr(A, B):
    P = solve_discrete_are(A, B, np.eye(n), np.eye(m))
    return np.linalg.solve(np.eye(m) + B.T @ P @ B, B.T @ P @ A)


def trunc(M, k):
    U, s, Vt = np.linalg.svd(M, full_matrices=False)
    s = s.copy(); s[k:] = 0
    return (U * s) @ Vt


def run(A, B, noise_seed, orders):
    """One trajectory; returns {N: {order: gap}} where order 'dense' or int k."""
    rng = np.random.default_rng(30_000 + noise_seed)
    Kstar = lqr(A, B); Jstar = cost(A, B, Kstar); g0 = cost(A, B, np.zeros((m, n))) - Jstar
    x = np.zeros(n)
    G = np.zeros((n + m, n + m)); H = np.zeros((n + m, n))
    out = {}; t_end = BURN + NGRID[-1]; marks = set(BURN + N for N in NGRID)
    xi_all = rng.standard_normal((t_end, m)); w_all = rng.standard_normal((t_end, n))
    for t in range(t_end):
        u = xi_all[t]; xn = A @ x + B @ u + w_all[t]
        if t >= BURN:
            z = np.concatenate([x, u]); G += np.outer(z, z); H += np.outer(z, xn)
        x = xn
        if t + 1 in marks:
            N = t + 1 - BURN
            Th = np.linalg.solve(G, H).T
            Ah, Bh = Th[:, :n], Th[:, n:]
            res = {}
            for o in orders:
                Bo = Bh if o == 'dense' else trunc(Bh, o)
                try:
                    K = lqr(Ah, Bo); res[str(o)] = (cost(A, B, K) - Jstar) / g0
                except Exception:
                    res[str(o)] = np.inf
            out[N] = res
    return out, g0


def main(which):
    rows = []
    if which == 'b':
        configs = [(f'r{r}', np.ones(r), [r, 'dense']) for r in [1, 2, 4, 8, 16, 32, 48]]
    else:
        ks = list(range(1, 48))
        configs = [(f'rho{rho}', rho ** np.arange(min(n, m)), ks + ['dense']) for rho in [0.3, 0.5, 0.7, 0.8, 0.9, 0.95]]
    t0 = time.time()
    for name, sigma, orders in configs:
        for s in SYS:
            A = make_A(s); B = make_B(sigma, s)
            for e in SEEDS:
                res, g0 = run(A, B, 100 * s + e, orders)
                for N, d in res.items():
                    for o, g in d.items():
                        rows.append((name, s, e, N, o, g, g0))
            print(name, s, f'{time.time()-t0:.0f}s', flush=True)
    import csv
    with open(f'x8_{which}_raw.csv', 'w', newline='') as f:
        wr = csv.writer(f); wr.writerow(['config', 'system', 'seed', 'N', 'order', 'rel_gap', 'g0'])
        wr.writerows(rows)


if __name__ == '__main__':
    main(sys.argv[1])
