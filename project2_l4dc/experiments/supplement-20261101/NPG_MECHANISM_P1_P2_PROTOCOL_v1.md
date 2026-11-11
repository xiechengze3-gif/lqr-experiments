# Review04:05 NPG saved-policy mechanism follow-up (P1/P2)

Scope: REPORT follow-up explicitly requested by Claude04:05. No sampled learning
run is repeated, no observations are generated, and no frozen learning parameter
or result is changed. A bounded single-core2GiB,10min Slurm REPORT job (upper
.166667SU) performs offline matrix evaluations and deterministic model references.
All source/config/code hashes are frozen in its auxiliary manifest before execution.

## P1 exact decomposition and coordinates

Use all saved X1/X2 NPG iterates, not a selected stable subset: X1 55,872 and X2
30,848 rows (86,720 total), all previously verified stable. Matrices come from the
original candidate archives, not regenerated systems. Costs have Q=R=W=I.
Take V_r as an orthonormal basis of range(B^T), U as an orthonormal basis of
ker(B) in the input space (as defined in paper appendix G), Pi=V_r V_r^T.

For each K, evaluate Sigma_K, D=tr(Sigma_K K_null^T K_null), g(Pi K), D/g,
||U^T(K-Kstar)||F², ||V_r^T(K-Kstar)||F² and their total. Verify B Pi=B,
the unchanged closed loop, g(K)=D+g(Pi K), and the orthogonal Frobenius split;
also compare g and D against the previously saved evaluations. Record numerical
identity residuals. This uses the proved redundant-cost identity in appendix A;
the projection is evaluation only and is never given to the learner.

Report every iterate in a CSV, plus per-cell median/IQR summaries for fixed final
K_T and pre-update K_(T-1). To make "last-stage iterates" unambiguous, also supply
the final16 updates and final quarter of updates: take a median over each run's
fixed window first, then median/IQR across the32 runs. Exact stage endpoints and
all rows remain available. No best-iterate selection and no inflation of repeat
counts by pooling correlated iterates. Keep both X1 null variants and m=r baseline.

## P2 exact-gradient optimization reference

For each formal physical model, start at its saved K0 and run the **original** eta
and T with exact objective gradient RK-B^T P_K F_K. This is deterministic model
evaluation, not a sampled experiment or a new calibration. Use88 distinct physical
models (72 X1,16 X2); sampling seeds do not create extra population models. Check
duplicate saved matrices across sampling seeds to numerical tolerance and use
the fixed lowest sampling seed as the canonical model. At rank2 the exact Z has
rank<=2, so dense and true-rank-truncated population references coincide; check
the numerical truncation residual, without silently imposing a true subspace on
any learned policy. Save all reference iterates and final reference gain matrices.

Provide population relative gaps at the same t,T,eta, and per-source observed vs
population rows. Report unique8-model population medians/IQR beside32-run learned
medians/IQR. The signed learned-minus-population gap is a comparison, not a
nonnegative additive statistical-error decomposition. Differences may include
finite-H estimator bias, rank truncation effects, and sampling noise; eta/T are
not changed if a formal model converges slowly. Also report null/action policy
distance to the population reference to distinguish initialization residue and
sample-driven deviation. Verify the expected X1 population matching across m.

## Analysis and provenance

For fixed-endpoint dense/truncated comparisons of D and action-space gap, retain
finite/full32 pairs and whole-system bootstrap95% intervals,8 clusters with all4
seeds preserved,2000 draws, seed2026110501. Fractions use per-output D/g before
summary. Plot D/g and separate component gaps; never treat sum of component
medians as median total gap. Show population reference as a separate curve.

Inputs are the immutable primary formal configs, completion receipts and saved
policies. The sole new output root is `analysis-P1-P2-v1/`; no earlier report,
result or TeX is modified. New population-reference trajectories are explicitly
counted separately from zero sampled-learning trajectories and zero training
transitions. X3-NPG formal20359471 continues unchanged.
