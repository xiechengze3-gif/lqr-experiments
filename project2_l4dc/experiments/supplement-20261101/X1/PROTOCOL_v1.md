# X1 PROTOCOL v1 — unstable independent plant and redundant inputs

Date namespace: 20261101. Formal state: **NOT ACCEPTED; submission gate CLOSED**.
Configuration is `configs/X1_v1.json`. `release-manifest-X1-v1.json` records the
exact engine/config/slurm hashes, frozen before this protocol is announced.

## Systems, independence and construction

The state dimension is n=12, exact rank r=2; m=2/4/6/9/12.
Pilot systems are 9001/9002; pilot CE sampling seeds 7001/7002 and actor seed7001.
Formal systems are 101–108 and sampling seeds1001–1004: 8 physically different
systems x4 sampling seeds per cell. No seed replacement or conditioning on cost.

A is generated from its own random source as Q diag(1.05,lambda2,...,lambda12) Q^T,
with an independent Haar Q and individually sampled lambda in [.15,.60]. These
systems have different eigenvalues, not just rotations of one plant. Independent
random streams generate U, each action Haar V_m, and h. B_m=U_r V_{r,m}^T.
Q=R=W=I. K_eff is an explicit Schur-mode pole correction that changes the single
unstable mode from1.05 to.65 and preserves the already stable modes. Its function
accepts A/B and the unstable eigenvector, but **no costs, cost evaluator, K*, P***.
K0_m=V_{r,m} K_eff + alpha*w_m*h^T, with alpha=0 or.25, norm(h)=norm(w)=1.

**Required correction to the task's invariant claim:** m=r has no null space.
For alpha=.25, common P0 and J0 can hold across m>r, but cannot also hold at m=r:
F0 is unchanged while K0^T K0 gains .25^2 h h^T. Accordingly:

- The zero-null control uses all five m and verifies common P0/J0/J*/sensitivity.
- The .25-null family verifies these invariants across the four m>r values.
- Its m=r point is the same zero-null baseline, explicitly labeled as an exception,
  never used to claim all-five-m matched initial cost. It may be reused after exact
  configuration/system/seed identity verification, not counted as new replication.
- This correction requires Claude acceptance before formal learning.

Diagnostics report rho(A), rho(F0), norm(P0), initial gap and two **action-space**
overlaps: ||Pi_R K0||_F²/||K0||_F² and the normalized projector overlap of range(K0)
with range(V_r). “row space of K0” lives in the wrong ambient space; range(K0)
means the row space of K0^T. These quantities never enter learner selection.

## Learners and transitions

CE uses one uninterrupted trajectory with u=-K0*x+xi, nu=1, including all512 burn
transitions. Regression prefixes N=4096/8192; primitive totals are N+512. Dense,
rank2 and the explicitly labeled true-action-space diagnostic share the **same**
OLS fit at each prefix. Oracle Bhat*Pi_R never feeds a practical learner.

NPG uses K <- K-eta*(R*K+T_r(Zhat)). Zhat is the exact adjacent-return, block-start
regression Stein estimator from paper Section4. All burn-in blocks use the same
pulse exploration as evaluation; baseline block is counted. PI uses PSD clip G,
joint SVD of [G+,Z], two-sided compression of G, then full greedy (no damping).
nu=1, H=32, burn=16 pulse blocks per stage, plus one baseline block.

The predeclared calibration ladder is base-blocks2048/8192/32768 with
eta.02/.01/.002. NPG has64 updates with ceil(base*2^(t/16)) blocks, t=0..63.
PI has8 updates; its block schedule is scaled to the same total primitive
transitions as that NPG candidate, including unequal numbers of burn/baseline
blocks. Both arms of each algorithm have exactly the same schedule and eta.

Select the **first** calibration whose dense NPG and dense PI remain stable on
all pilot systems/m values and whose dense endpoint relative-gap median is<=.95.
Do not select on truncated performance. If none qualifies, report the failure
and a new protocol rather than silently increasing resources or tuning on formal.
Formal parameters are the chosen ladder entry, published with pilot report;
their resolved configuration and code hash must be accepted before formal runs.
This schedule has the geometric precision-envelope shape; no numerical claim
that unknown theorem constants or all-prefix matrix conditions are certified.

Independent innovations are paired between dense/truncated arms, with continuous
state within each arm; after policies diverge, observations are not shared.

Failure handling for exact transition parity: after recording the first unstable
output, all later learned outputs in that arm are permanently failed (+infinity).
The remaining fixed data budget is collected under the supplied K0 solely as
discarded **padding**, without state resets, recovery or further policy learning.
Padding is counted and separately reported. It cannot turn a failed arm into a
success. This allows equal actual budgets even after a failure. Hard numerical
sampling failures are separately recorded with consumed-transition counters;
they are not auto-replayed. This disclosed rule also needs review acceptance.

## Statistics and reporting

Report absolute/relative gap and true redundant cost, median/IQR with failures
as infinity, full stable denominators32 per formal cell, and per-system paired
dense/truncated ratios. Bootstrap independent systems (8 clusters, all4 sampling
seeds stay together), 2000 resamples with fixed seed2026110199. Failed-pair ratios
are undefined and never replace full-denominator success statistics. Plot N*D at
both regression prefixes; no budget-to-epsilon claim from this two-point X1 grid.
All cases/negative results are retained. Reused m=r baseline counts only once.

## Resource envelope and immutable outputs

200 SU is the total **all-new-job** cap authorized directly by the user. Initial
X1 invariant/CE/actor pilot requests are 5/10/30 single-core minutes (0.75 SU total),
2GiB each, billing=1 required. Further ladder candidates are capped at60 minutes
each and are allowed only if cumulative requested bounds remain<=200 SU.
No formal array is submitted without complete same-dimension pilot timings,
measured memory, an upper-bound plan (30% margin plus startup), and explicit ACCEPTED.
Tentative formal budget envelopes: X1<=65 SU, X2<=65 SU, X3<=45 SU,
all pilots/report/reserve<=25 SU. Unused envelopes do not authorize unbounded jobs.
The optional n48/n32 cells and X4 are included only with measured support.

New local outputs: `experiments/supplement-20261101/X1/`; remote results:
`/scratch/user/changze/lqr_experiments/results/supplement-20261101/X1/`.
Only new dated releases, caches and temp are used. No earlier result, frozen
release, old documentation, paper TeX, Git remote or Overleaf is modified.
