# 100d fixed-ambient rank sweep: supplemental LSTD PI

Requested on2026-10-17 after the completed NPG/CE campaign. Add independent dense
and rank-aware truncated full quadratic LSTD policy iteration on the EXACT same
five system artifacts, initial policy and absolute targets. Existing NPG/CE runs
and their archives remain unchanged and are reused only through verified reports.

PI definition follows the repository's established user correction: full average-
cost off-policy LSTD in original(x,u) coordinates, no whitening, regularization or
rank restriction on the critic. n=m=100 gives20,100 coefficients. Use the existing
full_lstd_precision.solve, rtol1e-6, uniform attempts(restart100,max20cycles), then
(restart200,max20cycles) on the identical empirical equation. Failed solves stay
in the denominator; no true critic fallback. Extract G=Huu-R,C=Hux. Dense applies
PSD clipping to G; truncated jointly projects[G,C] to its empirical rank-r left
singular space and applies the same PSD operation. Greedy update is(R+G)^-1 C.
Full rank uses the identical dense arithmetic with no SVD, and shares computation.
No true subspace or evaluation cost selects an update.

Exploration sigma2, per-update nominal burn256, continuous trajectory, full data
of the current behavior policy for each complete critic solve. Separate pulse/
process-noise SeedSequence streams exclude rank and method, with common route2.
Dense/truncated share the actual complete first critic; after forking they use
the same exogenous innovations. All observations and burn-in are charged to each
algorithm, with shared physical simulator work accounted separately. Success
requires a stable whole PI path and final gap<=epsilon. Absorbing instability and
numerical failures remain failures at every larger assigned budget.

Pilot seeds0..4, confirmation100..129 (30 per cell). Pilot never enters formal
success denominators. Benchmark/recovery-test seeds9003/9004/9005 are excluded.
epsilon=.09836178768297843, sensitivity=.049180893841489215. Nhat is first tested
cumulative budget with>=27/30 successes; Wilson95% intervals and seed-curve
bootstrap retain censored runs. Budget and PI update count grow together along
the frozen schedule; this is not an isolated fixed-iteration batch-size effect.

Initial proposed pilot: four batches65536/262144/1048576/2097152 transitions,
each plus256 burn, max3,474,432. This uniform protocol is screened on5 seeds before
fresh confirmation; any uniform extension selected from pilot is separately
documented, source/config-prefix checked, and reuses exact K/x/critic/counter
checkpoints. No per-rank tuning. The final schedule and maximum are recorded in
the frozen JSON, with no post-confirmation change.

Compute is separately accounted for this newly requested PI supplement; prior
NPG/CE occupied112.978889 Slurm core-hours under its140 cap. The INITIAL PI planning
ceiling was125 additional allocated/billing-equivalent core-hours:175 paired groups with
one CPU,7GB,40min per group reserve at most116.667 core-hours; excluded-seed preflight,
maximum-batch benchmark, numerical/recovery verification and reports have bounded
allocations inside the remainder. No automatic retries. Before formal submission
use actual pilot and maximum-batch runtime/RSS to ensure remaining resources fit
the ceiling. Memory-equivalent billing is checked from actual Slurm allocations.
Other user's jobs and existing unrelated jobs are untouched.

Operational revision2026-10-18: actual concurrent maximum-batch solves took about
10-12minutes versus roughly7minutes in the isolated benchmark;40minutes proved
too tight for both branches. Preserve the numerical manifest and every source
hash. A separate resource plan raises the agent's planning ceiling to140 core-hours
(no user-specified125-hour limit), with120 nonfullrank formal groups at50minutes,
30 shared fullrank groups at30minutes: at most115 formal allocated core-hours.
Maximum combined concurrency stays30 (24+6). A single15minute checkpoint resume
is allowed for each actually unfinished pilot group. Guards require prior actual
occupancy plus all remaining upper allocations and2hours archive allowance<=140.
These are compute scheduling changes, not rank-specific learner hyperparameters.
Original pilot timeouts and any wasted solver CPU remain in accounting. Observed
data, fitted critics and complete policy stages are reused; no seed is replaced.
The frozen configuration retains its initial125/40 planning fields; the separate
configs/rank_sweep100_pi_resources_20261018.json records their operational override.

Final scheduling choice before ANY fresh confirmation: replace the unsubmitted
per-rank50/25-minute draft with30 identical seed bundles. Each real1CPU/7GB Slurm
task invokes the original frozen pair task in a fresh Python process for each
of its five ranks, sequentially, using exactly the same task indices0..149 and
the same seed streams. A completed pair is skipped without new samples on recovery.
Each bundle has228minutes in medium (current actual limit24h), maximum30 concurrent
bundles, total upper allocation114 core-hours. This pools time across ranks and
avoids rank-specific compute cutoffs. No numerical source, scientific manifest,
learner parameter, sample count, iteration or target is changed. The separate
batch wrapper and final resource plan have their own SHA256 checks at submission.

Initial40minute pilot:6 valid complete outputs,19 resource timeouts. First15minute
checkpoint recovery:8 additional valid outputs; its Slurm states were6 COMPLETED
and13 TIMEOUT (two TIMEOUT tasks had already committed valid complete outputs).
Only the11 actually missing groups receive one final20minute recovery, concurrency8.
All original Slurm states and spent CPU remain retained; no seed replacement.
The cost gate is re-evaluated with actual occupancy before formal submission.

Transition audit scope: distinguish durably committed unique observations from
possible duplicated simulator execution at an interrupted, uncommitted chunk.
The actual fresh confirmation has no interruption so far and its budget grid
counts every observation and burn exactly. Pilot journals were not snapshotted
at every timeout before final cleanup; conservatively bound each TIMEOUT lacking
a complete committed raw output by at most one64k chunk (burn is shorter and
committed separately). TIMEOUT tasks that had already committed complete outputs
have no such extra bound. Preserve this uncertainty in campaign physical totals,
without changing the unique training-data counts or fabricating an exact replay
counter. The upper bound does not assert that every possible replay occurred.

The initial100-core-hour draft was revised BEFORE pilot/confirmation submission
after the maximum-batch runtime measurement. At most30 formal tasks run together
to bound scratch temporary storage (roughly200GB at the largest batch), not to
claim that lower concurrency reduces total compute.

Numerical work runs on Grace compute nodes, in an isolated release with existing
dependencies. First preflight: job20184017, one CPU/4GB/max30min. Maximum-batch
test: job20184060, one CPU/7GB/max30min, real N=2,097,152 at ranks2/100. Site's
actual default partition is short. An invalid cpu partition and one CRLF shell
script were rejected BEFORE jobs existed; no numerical sample was lost. Original
invalid shell text/hash is preserved for provenance; numeric sources unchanged.

Maximum-batch job20184060 completed rank2 atN2,097,152 in419.75seconds (42 Krylov
iterations, residual9.84e-7; dense/truncated gap.265136/.026355), then was OOM-killed
while entering the next case. Preserve the completed row and failure. Wrapper
adds explicit gc.collect after each solve, and production uses disk-backed data
and cleanup after every durable update checkpoint. The failed benchmark's exact
simulator work is bounded between2,097,408 and4,194,816 transitions because its
second case did not have a collection journal. Do not invent an exact counter.
Production chunk journals retain actual observed-data progress on interruption.

Production data use original-coordinate NPY memory maps with per-chunk journals,
fitted-critic checkpoints and atomic whole-update checkpoints. A completed fit
can resume without re-sampling or solving again. Temporary observation files are
removed only after a durable fitted-critic checkpoint, with resolved paths confined to
that task's configured scratch temporary root. Full estimated critic matrices,
policies, raw outcome records, solver diagnostics and frozen sources are retained.
Small pending fitted-critic files are removed only after the whole-update checkpoint.
Verify a chunk interruption, a fitted-critic interruption and an update-checkpoint
interruption before production. Exact PI oracle uses no learning samples.

Before any pilot ran, enlarged data I/O chunks8192->65536 to reduce repeated
Lustre checkpoint flush overhead. Original-state/action sample order is checked
against the original collector (including16,384 observations with different
chunking); target actions/costs must agree within2e-13. Estimator, actor and
learning task function ASTs are identical. Old unstarted pilot20184142 retired
while all25 cells were pending. Original verification20184129 remains preserved.
New verification20184203 checks actual maximumN2,097,152 followed byN65,536 to
exercise cleanup, plus all numerical/recovery checks. The older two-maximum-batch
diagnostic was stopped after the replacement passed: its first complete update,
partial second-stage work and collection/fit journals remain preserved and counted.
The dependent pilot uses the new frozen
v2 release. No pilot or confirmation observations were mixed across I/O versions.

Local output E:/ChatGPT/Results/LQR_experiments/rank-sweep100-pi-v2-20261017;
local caches/temp explicitly E:/ChatGPT/Cache and E:/ChatGPT/Temp project subdirs.
Remote scratch output/cache/temp are explicit in the frozen JSON and launcher.
