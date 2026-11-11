# X6b protocol v2 — four-rung paired NPG / PI, calibrated S family

Supersedes the unaccepted v1 proposal. X6a estimation REPORT was ACCEPTED23:00;
the authorized S/n36 extension and saved-data CE addition are now complete.
**No X6b numerical job has run.** Source, decision rules, seeds and this protocol
are frozen before the new numerical work. X6c is deferred by23:00.

## Fixed plants, bases and learner information

S only: n=m24/36/48/72,r2,Q=R=W=I; all A eigenvalues iid uniform [.15,.60],
independent Haar A rotation and B=U2V2^T; K0=0, known class certificate pbar2.
eta=1/(1+2*2)=0.2 for every dimension, arm and budget. H16,nu1,
16 pulse-protocol burn blocks +one baseline per update. Frozen collect and
actor_learner are the same as X6a/previous accepted algorithms.

| n | Pilot-only frozen base blocks | Source |
|---:|---:|---|
|24|524288|X6a pilot calibration|
|36|1048576|Authorized A2; pilot rho_op=.844001575|
|48|2097152|X6a pilot calibration|
|72|4194304|X6a pilot calibration|

No base is re-chosen from actor outcomes, formal plants, stability or truncation.
The original X6a n36 formal grid stays unchanged; A2 is a calibration annex.
Formal systems301-308 x fresh sampling seeds1701-1704; pilot systems9101/9102.
Resource seed9801 and equivalence seed9802 are disjoint from formal sampling.
The learners receive known Q/R, rank2, eta and observations only. True A/B,
subspaces, P/Kstar and gradients are simulator/evaluation or pilot-design data.

## Population R2 protocol-resolution proposal

Request explicit acceptance of **one zero-sample R2 design job** before the
resource-only PILOT:1CPU/2GiB/5min=1/12SU, no automatic retry. This is the
mandatory GO population rule, not a noisy actor calibration. The separation
from resource-only PILOT is proposed explicitly; do not infer an exception.

Using dense exact-model updates at eta0.2 on all8 S pilot plants (2systems x4n),
select the smallest common NPG T in{16,24,32,48,64} reaching relative gap<=.05
on all8. Select PI8 if all8 reach .05 at8, otherwise12 if all8 do at12. Require
coverage8 at each candidate T. If either has no qualifying T, stop and report;
no eta reduction, noisy/truncated success criterion or performance-based n drop.

Code `population_only.py` calls only the population routine; it does not collect
new observations, extend any calibration, run a noisy actor, or read formal
performance. Output X6b/population-v1,0new primitive transitions. It is not
authorized until Claude accepts this protocol-resolution placement/job.
After it completes, append resolved T/config/hash and the resource plan; await
explicit approval for PILOT unless the review provides an exact conditional go.

## Preregistered four-rung schedules and exact budget parity

Candidate rungs base_n x{1/64,1/16,1/4,1}, as22:55 requests. The first three
original rungs1/16,1/4,1 are mandatory for included dimensions. The new1/64 is
included if its measured cost fits; decide and freeze coverage before FORMAL.

For rung c: NPG blocks[t]=ceil(base_n*c*2^(t/16)),t=0,...,T-1.
For PI Tpi selected by population, use w[t]=2^(4t/Tpi),t=0,...,Tpi-1, the X1
geometric shape. Let L=sum(NPGblocks)+17*(T-Tpi). Allocate floor(L*w/sum(w)),
then remaining blocks to descending fractional remainders, ties by ascending t.
This gives equal primitive counts16*(sum(blocks)+17*updates) for NPG and PI,
and identical counts between each dense/truncated pair. All stage counts are
published as integers before FORMAL. Exact matrix evaluations add0transitions.

NPG update keeps RK and truncates Zhat only. PI v4 PSD-clips Ghat, takes the
joint top2 LEFT space of[G+,Zhat], compresses G+ on both sides/Zhat on the left,
then full greedy. No critic/LSTD variant, K clipping, line search, recovery,
oracle subspace, adaptive rank, iterate selection or changed nu/H/eta.

Per-stage seeds are frozen rng(20 or21,n,m,system,trial,stage), without arm,
so both arms get paired innovations and continuous own trajectories. No claim
of common actual data across different policies, algorithms or rungs.
Instability is absorbing failure recording; later budget is consumed under K0
and labeled padding, never recovery. Failed gaps remain+infinity. Preserve all
failed outputs, single/joint failures and full denominators.

## Resource-only PILOT: measure every rung before FORMAL

After R2 resolution, publish the exact resolved schedules and per-job plan.
`resource_actor.py` has two preregistered modes:

- Small separate-seed paired-path equivalence for NPG/PI against frozen
  actor_run: bitwise assessed gains, scalar results and exact counts including
  absorbing padding; print only PASS/compatibility, no performance statistics.
- For every(n,rung,algorithm), time the largest stage at pilot K0 with the
  unchanged collector, then both learner updates and artifact writes. No gap,
  precision, subspace or projection readout and no performance-based choice.
  One collector serves this timing benchmark's two updates; the FORMAL forecast
  explicitly uses **two collectors +two updates/writes** for each paired path.

Each dimension job first records a separate256-block warmup (seed9803,4368
transitions) to separate compilation/cache loading from per-rung collector rates.
Warmup time and primitive cost are reported, never erased or used as performance.

There are4 dimension jobs, each covering all4rungs x2algorithms, plus one
equivalence job. Existing measured timing spans all4n through4m blocks;
chunk memory is bounded independent of stage length. If T=16/PI8, provisional
walls n24/36/48/72=10/15/25/60min plus5min equivalence total1.916667SU.
These are ceilings/estimates, not measurements of the new learning workload.
If T differs, recompute stage maxima/cost before submission. Provisional PILOT
cap4SU; exceeding it requires reporting/review first.1CPU/2GiB,threads1.

Only explicit PILOT ACCEPTED plus a whole-grid measured SU plan permits noisy
FORMAL. Per-rung forecasts sum every integer batch, update, serialization and
evaluation overhead, with measured margin. Walltime, memory, queue and source
hashes are recorded. Concurrency is not a budget limit.

## Formal scope, requested cap and checkpoints

Each included(n,rung,algorithm):8systems x4seeds,32paired paths/64arms.
Priority n24,36,48,72; optional48/72 may be deferred only for measured cost.
Budget allocation first preserves the original3rungs for mandatory24/36,
then optional48,then72 if affordable; add1/64 across included dimensions if
its measured incremental cost fits. Freeze coverage before any formal output.
Do not cut systems/seeds/T/mandatory rungs or drop a negative result.

Shared cumulative requested cap400SU includes all prior17SU, R2, resource
PILOT, every formal/report job and any separately accepted continuation. Actual
elapsed/settled views are separate and overlap. No full array request before
the measured plan fits the remaining allowance. Long paired cells may use
medium partition; resource requests are per(n,rung,algorithm), not one giant
maximum applied everywhere. No automatic retry or unbounded continuation.

`actor_paths.py` preserves raw G/Z and pre/post-update K,x at every stage plus
complete-stage checkpoints, dead flags, padding, counts, RNG and source/config
metadata. It calls frozen collector/update; the resource equivalence checks this
against actor_run. Partial/hard-failure attempts remain visible. Any checkpoint
continuation gets its own concrete cost/review receipt and new immutable attempt;
no old result/release is overwritten and no main SSH/PuTTY connection is restarted.

## Reporting, failures, bootstrap and observed-rung attainment

Primary absolute/relative endpoint and stage gaps: median/IQR over the full32
paths, unstable/failed=+infinity; per-arm stable/full and first-failure stage.
Also retain per-system seed summaries. No stable-only primary median.

At every rung report paired ratios on both-stable pairs and the failure-inclusive
version. The latter keeps one-arm failures (ratioinf or0), drops only jointly
failed pairs and counts them; both-zero optimal gaps would have ratio1.
Both-stable finite/full, dense-only/trunc-only/joint failure counts are explicit.
95% percentile bootstrap resamples8systems with all4seeds in each,5000 draws.
Use common cluster draws across rungs/arms/ratio definitions for a given n/algorithm.
Empty both-stable resamples are counted; extended-real quantiles handle infinity.

For relative epsilon0.1 and0.05, select the smallest **observed registered rung**
with>=29/32 endpoint gaps attaining epsilon, separately per arm. Unstable/failed
never attains. Report the exact primitive budget including burn/baseline;
if none qualifies, right-censor above the largest observed budget. No interpolation,
isotonic fitting, extra rung, stopping on success or claim of the exact minimum
sample budget. The22:55 request intentionally uses this coarse observed ladder,
not the earlier F8 sqrt2-grid budget-resolution claim. Bootstrap with the same
system draws, reevaluating29/32 at every rung; retain censored mass/infinite
upper limits rather than discarding nonattaining resamples.

Endpoint redundant D and action-space gap g(Pi_R K), D/g and true V_r action
error are simulator-only diagnostics. Check the same-closed-loop gap decomposition
from saved policies. Along-path rho_op/projection uses **own pre-update K** and
saved G/Z; retain raw/clipped/compressed PI separately. These diagnostics, true
subspaces and Kstar never enter learners. Padding stages are labeled, not plotted
as successful updates. Structural factor(n-2)/4 is shown beside paired ratio vs n
for each rung; unknown constants/trends do not become an exact fitted law.

Report every registered negative cell/censored threshold/failure. Empirical
rho_op<=1 is not all theorem small-error/horizon/path conditions; no claim of
epsilon attainment precedes the actual29/32 result. X6a estimator gains alone
are not terminal-cost gains. All numerical work stays on Slurm compute nodes;
local post-processing is saved CSV/scalar plotting only. New data/cache/tmp use
the X6 namespace; no old docs/results/releases or paper TeX are edited.
