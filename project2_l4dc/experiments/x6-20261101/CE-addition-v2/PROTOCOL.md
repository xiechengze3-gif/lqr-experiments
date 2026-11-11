# X6a saved-data CE addition —22:55/23:00 authorization

New REPORT only,0new transitions. Execute after the accepted S/n36 A2 extension
finishes, as23:00 requests. Original X6a data and estimation report stay immutable.

Use only the32 formal system/seed bundles from the frozen X6a registry: S IDs
301-308, U401-408,4seeds each, n24/36/48/72, N2048/8192/32768/131072/524288.
Both arms use the identical stored CE OLS(Ahat,Bhat) and known Q=R=I.
Dense calls frozen ce_learner with full retained rank n; truncation uses rank2.
No oracle, adaptive rank, data regeneration, retuning or new learning trajectory.

Evaluate each resulting gain by frozen assess on its saved true model, preserving
all32 denominators. DARE/solver failures and true instabilities have infinite
absolute/relative gap. Save gains, input hashes and failure reasons. On stable
gains check direct Lyapunov cost minus Jstar against the quadratic gap identity
to normalized tolerance1e-7; a failed identity aborts rather than being hidden.

For each(family,n,N), report both-arm stable/full counts and failure-inclusive
absolute/relative gap medians/IQR. Compute two paired ratios: both-stable pairs,
and the failure-inclusive version that keeps one-arm failures (ratios infinity
or0), dropping only jointly failed/infinite pairs and explicitly counting them.
For the measure-zero both-optimal0/0 case define ratio1, never silently drop it.
Keep separate dense-only/truncated-only/joint failures and valid/full pair counts.

95% bootstrap intervals use5000 resamples of the8 independent systems, preserving
all4 seeds within each sampled cluster. Invalid all-empty both-stable resamples
are counted and reported. Use extended-real quantiles that do not produce NaN
from Inf-Inf interpolation. Seed tags fixed as rng(620,family-code,n,N,kind).

Report operator norm P0 and vstar=||Pstar(A-BKstar)||F^2 median/IQR over the
8 distinct systems per(family,n), for S and U. These are evaluation metadata.
Ratios/gaps are across the full32 paired paths or the explicitly named subset.
No estimator/error calibration rule is changed by these saved-data CE outcomes.

Request1CPU/2GiB/30min=.5SU, within the second<=1SU REPORT authorization,
threads1 and existing Python3.11. Timing basis: the original resource/model
setup at n72 was about.1s including DARE;2560 gain solves plus saved-file reads,
Lyapunov checks and5000x8-system bootstrap per cell fit the generous30min bound.
No automatic retry. Reserve this request before sbatch in the shared400SU ledger.

Output results/x6-20261101/X6a/CE-addition-v1; archive raw gains, observations,
full summary/certificate CSVs, code/config/approval hashes and accounting.
Produce CSV-only figures after transfer. Plot paired CE gap ratio vs n/r with
system95% intervals and per-N arm failures; keep negative/mixed U outcomes.
