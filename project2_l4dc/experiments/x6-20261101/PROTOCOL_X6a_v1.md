# X6a protocol v1 — fixed-gain, same-data estimation

Implements the author-approved X6 GO (19:05 CDT, amended 19:10), superseding X5/P3.
No learning, policy selection, epsilon-attainment or end-to-end gain claim is made here.
All new X6 jobs together have a separate **400 SU cumulative requested upper bound**.
The completed overnight X0-X4 study remains frozen (112.920278 elapsed SU).

## Gates and provenance

Every X6a/b/c PROTOCOL, resource-only PILOT, FORMAL and REPORT needs Claude's
explicit ACCEPTED before the next stage; no old timeout/conditional exception applies.
X6a has not started. Simulation, model solves and numerical checks run only on
Slurm compute nodes. No old results, historical docs, frozen releases or paper TeX
will be edited. New outputs, cache and temporary files use the X6 namespace.

`config-X6a-v1.json` is the resolved registry; `SHA256SUMS` freezes it, this protocol,
the collector and byte-for-byte `frozen_engine.py`. The engine's SHA256 is
`9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`.
Release and approval receipts must record all hashes and the latest task-file hash.

## Plants, systems and seeds

- n=m in {24,36,48,72}, r=2, Q=R=W=I, exact singular values (1,1,0,...).
- S: independent source streams for A and Haar U/V, all eigenvalues independently
  uniform [.15,.60], K0=0, P0 operator norm <=1.5625. A construction uses frozen
  stream 1 and n stable draws after the Haar draw; B uses streams 2/3 unchanged.
  Formal IDs 301-308; calibration IDs 9101-9102.
- U: frozen `plant(n,n,2,id,null_scale=0.)`, one unstable eigenvalue 1.05,
  stability-only K0; **no P0 or gap selection**. Proposed resolved formal IDs
  401-408, calibration IDs 9201-9202, same IDs at each n. This explicitly fills
  the unspecified X6a-U ID range and requires acceptance with this protocol.
- Formal sampling IDs 1601-1604; disjoint calibration sampling IDs 9601-9604.
  Resource sampling ID 9701; resource cells use only 9102 (S) or 9202 (U).
- S zero-gain normalized overlap is undefined, reported null with explanation.
  Store all other F5 plant certificates, P0, true targets and initial gap as
  evaluation metadata. Learner fitting/SVD never reads these targets or subspaces.

Each family/dimension has 8 genuinely different formal systems x4 seeds and
2 disjoint calibration systems x4 seeds. Paired arms are post-processing of the
same raw fit. S explicitly overrides the original unstable-A F5 requirement.
X6c's P0-selected pilot sequence may differ from 9201/9202; do not silently
transfer calibration from rejected pilots. Resolve that in X6c's own protocol.
Conditioning on P0 also changes unconditional A/B independence; disclose it.

## Data collection and counts

N={2048,8192,32768,131072,524288}. H=16 for S and32 for U, nu=1,
16 pulse-protocol burn blocks and one baseline block. Copy frozen `collect`
arithmetic, post-transition return convention, adjacent-return difference and
256-block chunk order exactly. Save each nested prefix of one continuous run;
the RNG, state and sufficient sums are never reset at a prefix. N is divisible
by256, so a fresh frozen collect at each prefix must be bitwise identical.
One Stein prefix consumes (N+17)H primitive transitions. The same raw Ghat/Zhat
supports both NPG/PI evaluations and both raw/compressed arms.

CE is a separate trajectory using frozen `ce_chunk`: u=-K0x+xi including512
burn transitions, 512-transition chunks (the actual frozen engine setting),
and the same half-prefix stops as ce_run. Shared OLS fit (Ahat,Bhat) supplies
Bhat and T2(Bhat). N denotes post-burn transitions, actual count N+512.
Equal numerical N across Stein and CE is **not** equal cross-algorithm cost;
only within-algorithm paired errors are compared. Evaluation uses exact matrix
operations and consumes zero simulated evaluation transitions.

Archive per-prefix sufficient sums, raw estimates, final x, previous return,
RNG state, checksums and counts; archive each true model separately. No
full-noise trajectory archive is necessary. A completed prefix is not an
automatic resume authorization; no silent retry or resampling.

## Evaluation fixed before data

Targets: P=P_K0, F=A-BK0, Z=-B^T P F, G=B^T P B; CE target B.
NPG dense=Zhat, truncated=T2(Zhat). PI dense=[G+,Zhat], with G+ from PSD
clipping exactly as actor_learner; take top2 **left** singular vectors Uhat of
that joint matrix, then compressed=[Pi G+ Pi,Pi Zhat], Pi=Uhat Uhat^T.
This is joint compression, not simply T2 of the concatenation. Also retain raw
[Ghat,Zhat] diagnostics to separate PSD clipping from joint compression.

For NPG and PI report relative Frobenius error, paired dense/compressed error
ratio, rho_op=dense operator error / second singular value of the true target,
largest sine of principal angles between estimated and true top2 **left**
subspaces, and projection <estimate,target>/||target||F^2 for both arms.
Report raw-joint PI rho_op alongside PSD-clipped-joint rho_op. CE reports
relative Frobenius B errors and their paired ratio. No row-space/right-vector
angle is substituted for the requested left-subspace angle.

Retain all32 observations per cell. First median/IQR over4 seeds per system,
then median/IQR over8 system medians. Aggregate paired ratios in that order,
never divide marginal medians. Retain per-system IQRs in CSV. Projection:
within-system seed mean/SE, then grand mean and sample SE over8 independent
system means; do not treat32 samples as32 independent systems. State weak
precision of SEs with4 seeds and2 calibration systems.

Calibrate only on the disjoint calibration systems: compute seed medians then
median over the2 system medians at each N. Report the smallest grid N with
median rho_op<=1, separately for NPG raw Zhat, PI raw joint and PI PSD-clipped
joint; show each pilot's curve as well. Future common-base decisions remain
for X6b/c protocol approval. No gap, stability or truncated-arm statistic
enters this rule. If no N qualifies, report right-censored >524288; do not
extend the grid or choose a base silently. rho_op<=1 is an empirical
signal/noise criterion, **not certification of all theorem constants**.

Fitting/evaluation failures are retained with full denominators and infinite
error; record the reason. Fixed K0 is never updated, so there is no learned
policy instability or stability-based exclusion in X6a. Singular true sigma2,
if encountered, is reported as a non-identifiable diagnostic rather than
silently changing the rank. No formal system is dropped for a large P0.

## Resource-only PILOT and cost

Historical measured source: supplement-20261101/budget/NPG_resource_pilot_v1.json,
Slurm20359304, same frozen collect at H32: n24/N131072=2.321298s,
n48/N524288=20.013511s, peak134404KiB. These do not measure X6's n36/n72,
CE collection, file I/O, setup or compilation. Scaling n24 linearly to N524288
gives9.2852s; a conservative n48 cubic n72 extrapolation gives67.5456s;
these two numbers are estimates, not measurements of new cells.

After PROTOCOL ACCEPTED, resource PILOT has8 tasks, one per (S/U,n), through
the largest prefix. Save timing/counts/RSS only, no scientific errors, gaps,
truncated estimates or calibration readouts. Task0 additionally checks
bitwise equality of prefix x/G/Z/RNG against frozen collect at256/1024 blocks
for both H, and CE chunk/OLS equivalence against an independent scalar-time
reference of ce_run's observation branch at2048/8192 transitions (state and
OLS relative/absolute tolerance1e-11, RNG state bitwise). No parameter selection
comes from those tests. Measure setup/compilation and each prefix separately.
Request1 CPU,2GiB,15min per task: **2 SU requested upper**. No automatic retry.
Include one full-size artifact-writing measurement if timing I/O is necessary;
only raw estimates may be archived, never inspect its scientific accuracy.

FORMAL proposal:40 tasks =32 formal(system-index xseed) +8 calibration
(system-index xseed); each task covers8 (family,n) cells. Thus320 paths
and1600 prefixes per collection type. Same-prefix processing avoids5
independent simulations per path. Concurrent task cap32. Provisional ceiling
30min/task x40 =**20 SU**; replace it with a measured per-bundle limit
ceil_minutes(1.3*sum(per-cell max timings plus I/O)+60s) before FORMAL,
with all full counts preserved and explicit PILOT ACCEPTED. Reserve <=1 SU
for separate numerical REPORT; refine before submitting it. X6a provisional
requested ceiling **23 SU**, leaving377 SU of the400 for X6b/c. These are
ceilings, not actual usage or a guarantee that X6b/c fit.

Only if a measured cost cannot fit may the largest N at n72 be removed,
with a revised registry/hash and explicit acceptance; otherwise keep it.
No reduction by gap, truncation result, P0, systems or seeds is allowed.

## Outputs and frozen analysis

Raw estimates and receipts under results/x6-20261101/X6a; resource-only
receipts in its resource subdirectory. New code/configs/protocols locally
under experiments/x6-20261101. Set remote TMPDIR/XDG_CACHE_HOME/NUMBA_CACHE_DIR/
MPLCONFIGDIR explicitly to x6-20261101 tmp/cache; clamp BLAS/OMP threads1.
Use existing Python3.11, no installation. Account132685389143 FY2027.

REPORT deliverables: raw/aggregated/calibration CSV, PNG+SVG curves of errors,
paired ratios, rho_op, left angles and projection with uncertainty, portable
CSV-only plotting script, checksum/coverage verification, exact configs/code
and Slurm accounting. Retain negative results, censoring and all denominators.
X6a explains an estimator mechanism; a better estimation ratio alone does
not establish a terminal-cost gain or budget-to-epsilon guarantee.
