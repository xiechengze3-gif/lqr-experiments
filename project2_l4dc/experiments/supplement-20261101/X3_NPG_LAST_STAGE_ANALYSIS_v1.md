# X3 NPG last-stage analysis, Review 04:35

This is saved-policy post-processing requested by Claude, not a new learning experiment.
The formal release, RNG streams, eta, T, H, ranks, budgets and all seeds stay frozen.
Use the complete 288 multi-run receipts and all 1,440 planned endpoints, not an
interim subset. Analyze all three spectra and budget multipliers 1,4,16; the
two-level spectrum is the requested mechanism panel. No top-2 redundant-cost
identity is asserted for full-rank B.

For the last update from K_63 to K_64, recover the matrix actually used as

    S_k = (K_63 - K_64)/eta - R K_63 = T_k(Zhat_63).

R=I in this experiment. The full raw Zhat was not separately saved. For each
arm, S_k is recoverable from its two saved gains, to floating-point update error;
the untruncated raw Zhat of a truncated arm is not recoverable and is not claimed.
Evaluate the target at that arm's actual behavior policy:

    F_K = A-BK, P_K = Lyapunov(F_K^T, I+K^T K), Z_K = -B^T P_K F_K.

Report ||S_k-Z_K||_F, its square and relative norm, true rank-k approximation
error ||T_k(Z_K)-Z_K||_F, rank residual of S_k, stability and endpoint absolute
and initial-gap-relative gaps, per output and median/IQR over all 32 repeats.
Missing last updates have an explicit missing/error count; failed endpoint gaps
remain +infinity in full-denominator endpoint summaries. No imputation of a
missing estimator as a measured Frobenius error. The last-estimator summaries
are explicitly conditional on availability, with valid/full counts.

As a secondary diagnostic, recover the dense arm's raw last Zhat once and apply
each of the five fixed ranks offline at the same dense K_63. This gives a
common-policy, common-estimate comparison. It does not produce alternative
policies or training trajectories. Do not attach the own-arm endpoint gap to a
counterfactual common-fit update. Keep both analysis branches labeled.

Use system-cluster bootstrap 2,000 draws, seed 2026110601, for paired dense/rank
last-error ratios on finite pairs, eight systems with all four trials retained.
Endpoint gap ratios and failure-inclusive summaries remain those of the frozen
primary actor report. No best-iterate or post-hoc budget selection. No theorem
small-error condition is certified merely from a Frobenius error or final gap.

Checks before reporting: frozen config/source and raw archive hashes; complete
coverage; gain-update algebra on a deterministic synthetic matrix; true Z sign
against the frozen population-reference convention; target-rank tail identities;
roundoff-scaled rank residuals and update reconstruction residuals. Scientific
calculations run on a bounded Slurm REPORT job, one CPU, 2 GiB, 15 min total for
the combined X3 endpoint, envelope and mechanism reports (0.25 SU upper).
