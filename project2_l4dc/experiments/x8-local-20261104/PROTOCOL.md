# X8 protocol (fixed before the runs, 2026-11-04)

Purpose: two CE experiments for the redesigned Figure 1.
(b) rank sweep: does the sample cost of truncated CE grow linearly in rank B while dense CE does not change?
(c) spectrum sweep: for full-rank B, does the sample cost of truncated CE follow the effective actuation rank?

Common setting (identical to Section 6 of the paper):
- n = m = 48. A = Q_A diag(lambda) Q_A^T, Q_A Haar orthogonal, lambda_i ~ U[0.15, 0.6].
- B = U diag(sigma) V^T, U, V Haar orthogonal (independent of A).
- Q = R = W = I, K0 = 0, x0 = 0, exploration u_t = xi_t ~ N(0, I_m) (nu^2 = 1), w_t ~ N(0, I_n).
- 512 burn-in transitions, then N regression transitions; least squares of x_{t+1} on [x_t; u_t].
- N grid: 2^9, ..., 2^18 (nested prefixes of one trajectory per run).
- 8 systems x 4 seeds = 32 runs per configuration. System seeds 0..7, noise seeds 0..3 (fixed).
- Dense CE: LQR(A_hat, B_hat). Truncated CE: LQR(A_hat, T_k(B_hat)).
- Gap g(K) = J(K) - J(K*), J(K) = tr(W P_K); unstable output -> +inf. Relative gap g(K)/g(K0).
- Sample cost: regression transitions N_req at which the median relative gap over the 32 runs
  reaches a target eps_rel in {0.05, 0.02}, by log-log interpolation of the median curve on the grid.
  Not reached on the grid -> reported as censored (> 2^18).

(b) sigma = r ones, r in {1, 2, 4, 8, 16, 32, 48}. Truncated order k = r.
(c) sigma_j = rho^(j-1), rho in {0.3, 0.5, 0.7, 0.8, 0.9, 0.95}. Truncated order k = max{k_eps(B), 1}
    with k_eps(B) = min{k : tau_k^2 <= eps_abs}, where eps_abs = eps_rel * median_s g_s(K0)
    over the 8 systems of that configuration (one k per configuration and target).
    The gap is recorded for every fixed k in {1,...,47} and dense, so that k_eps can be read off post hoc.
Reported: median curves, N_req per configuration/method/target, the k used, failures.
