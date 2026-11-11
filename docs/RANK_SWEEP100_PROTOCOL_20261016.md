# Fixed-ambient 100d rank sweep

Requested scope: n=m=100, Q=R=W=I, r=2/8/32/64/100. Interpret the
rank-r system formula as B=b U[:,:r] V[:,:r].T. One U/V instance is generated
from seed20261017 and saved as numeric artifacts; production loads those exact
artifacts instead of regenerating orthogonal bases across BLAS platforms.
b=1. F0 has a .75 eigenmode u1; its invariant complement is .45 times a random
orthogonal matrix plus a random perturbation with operator norm .12. Its actual
operator norm is .532739. A=F0+.45u1u1.T and K0=.45v1u1.T are common.
Every rank must pass the closed-loop, P0, numerical rank and Lyapunov checks.

The existing actuation_redundancy.collect and learner functions supply the
original-coordinate adjacent-return first-order Stein regression and the update
Kplus=K-eta(K+Zhat). Only Zhat is truncated; the known K term is retained.
CE reuses ce_chunk, full original-coordinate OLS, and dare. Truncated CE changes
only Bhat after the common full OLS fit. No true subspace, stability evaluation,
test cost or model reaches the learner. At r100 truncation bypasses SVD and uses
the same arithmetic as dense; all policies and states must be array-equal.

Pilot v1 (seeds0..4, separate output) uses eta=.15, sigma=1, H8, burn256,
8 updates each at8192/32768/131072 blocks. Its early controller failures are
retained. The revised common protocol, to be checked by another5-seed pilot,
uses eta=.05, sigma=2, H4, burn256, and8 updates each at16384/65536/262144/
1048576 blocks. These are GLOBAL choices; there is no per-rank tuning.
Both exact-gradient and finite-H population references must attain epsilon/10
within the common32 updates before the revised sampled experiment is accepted.
The finite-H check addresses finite-return bias, not just exact optimization.
The revised CE grid is frozen before its pilot and includes intermediate budgets
near the v1 attainment region, with all output policies re-evaluated on truth.

The common absolute epsilon is .1 times the minimum initial gap, determined
before sampling: .09836178768297843. The .05 sensitivity target is epsilon/2.
NPG final success at each budget requires a wholly stable learning path and
gap<=epsilon; failures remain failures at subsequent assigned budgets. CE final
success requires a stable true-system output and gap<=epsilon, independent of
earlier prefix failures. All burn-in and baseline blocks are counted. NPG uses
one continuing trajectory per arm, stage burn-in, no state resets, with a fixed
growing schedule shared across ranks. Stage checkpoints refine the geometrically
growing epoch endpoint budgets; the reported Nhat is a first-tested-grid value.
The sustained crossing is saved as a sensitivity statistic.

Pulse and process-noise streams use separate SeedSequence components and omit
rank and method. Dense/truncated share the exact first estimate, then the same
exogenous innovations on their distinct policies and states. Full-rank arms
share the complete computation. CE dense/truncated share every OLS estimate.
Sharing computations reduces physical simulator work, not the sample charge
of either algorithm. Both counts are logged.

After the revised pilot,30 fresh seeds100..129 form the confirmation sample.
No favourable seed selection, deletion of failures, or mixing of pilots into
confirmation denominators. Wilson95% intervals describe conditional seed success
for the one fixed system. Nhat is the first tested budget with point success>=.9;
this is not a lower-confidence-bound guarantee of90% population success.
Seed-cluster bootstrap threshold intervals retain censored draws. Gaps in plots
are conditional on stable observed seeds and accompanied by all-seed success and
failure plots. Cross-rank conclusions remain empirical because control ability
and exploration-state distributions also change with rank.

Execution: existing E: Python environment for v1 pilot; existing Grace environment
for revised pilot and confirmation, with one CPU/2GB and one BLAS thread per task.
No dependency installation. Grace account132685389143 FY2027 query showed8737.69
SU balance (Used & Pending11262.31; settled historical total10783.97), including
existing commitments. A10-minute one-core preflight is the only initial submission.
Revised pilot/confirmation require a measured compute-node runtime estimate.
Hard total cap140 SU:175 NPG paired tasks x45min=131.25 SU;175 CE paired tasks
x2min=5.833 SU; preflight/reporting leave the total below140. No automatic retries.
Maximum20 tasks per array; arrays are not a total-cost limit. Existing unrelated
jobs are untouched. Stage/OLS-prefix checkpoints support explicitly audited resume.
All configurable local and remote output/cache/temp paths are explicit in JSON
and the launcher; downloaded final artifacts are stored under E:/ChatGPT/Results.

## Final uniform budget extension

The revised32-update pilot remains a preserved prefix. Its completed full-rank
seeds had gap about.5 at44,572,800 transitions. Before confirmation NPG sampling,
append8 updates with4,194,304 blocks each, with unchanged eta=.05, sigma=2, H4,
burn256, RNG streams, states and learner code for EVERY rank. The final protocol
has40 updates and178,792,608 maximum transitions per algorithm. This is a compute-
bounded maximum, not a presumption that every method must attain. The working
draft containing an additional8M-block stage was removed BEFORE any verification
or sampling of that draft; its timing estimate did not fit the140 SU cap safely.

Final config: configs/rank_sweep100_final_20261016.json. Final release/results use
rank-sweep100-final-20261016, preserving both earlier pilot directories. Migration
requires identical numerical source hashes, all shared scientific/sampling fields,
and an exact schedule prefix. It copies exact K/x/failed/rows/physical-count states
for the25 pilot NPG checkpoints, and reuses175 completed CE paired datasets whose
CE protocol is unchanged. Source identities and file hashes remain in the reuse
receipt and reused CE JSONs; no result is silently relabelled.

Final NPG tasks reserve at most44min each, one CPU/2GB. The175-task upper bound is
128.333 SU; the measured earlier NPG pilot plus CE and preflight/reporting keep
the full campaign below140 SU. No automatic retries. Up to60 one-core tasks may
run simultaneously in the final array; concurrency changes elapsed time, not the
estimated total cost. The extended5-seed pilot precedes the30-seed confirmation.

## Confirmation budget search (before fresh NPG seeds)

The40-update full-rank pilot remained above target (first completed seed gap
.1318328134). The still-unstarted NPG confirmation array20175217 was held while
the common maximum was reviewed; no fresh confirmation NPG data had been sampled.
Append4 more updates at the SAME4,194,304-block batch to every rank, with all
numerical sources, model artifacts, eta, H, sigma and exogenous streams unchanged.
The confirmation config is configs/rank_sweep100_confirm_20261016.json:44 updates,
maximum245,902,512 primitive transitions, exact prefix reuse of the40-update pilot,
and unchanged reuse of all175 CE datasets. Earlier pilot directories stay intact.

Before submitting fresh NPG seeds, measure all prior job core-hours and require
prior_cost +120.6667 +2 <=140 SU-equivalent core-hours. The remaining resource
upper bound is120 non-full-rank confirmation tasks x50min,30 full-rank tasks x30min,
20 resumed pilot tasks x15min and5 resumed full-rank pilot tasks x8min. All use one
CPU/2GB. These walltimes bound compute resources only; every rank uses identical
44-update sampling/learning hyperparameters. Formal tasks use two60-task arrays
for non-full ranks and one30-task array for full rank (150 total); each array
stays within the60-task configured per-array limit. This changes elapsed time,
not the total resource upper bound. No automatic retries. The resumed5-seed pilot
finishes before30 fresh seeds100..129 start. Unattained cells remain censored.

## Completed execution and offline review

All5 pilot and30 fresh confirmation seeds completed the frozen44-update protocol;
no infrastructure sampling restart or seed replacement occurred. Read the final
results in RANK_SWEEP100_FINDINGS_20261017.md and the result directory's completion.json.
Local saved-policy audit passed all19,600 policy checkpoints in350 paired tasks,
with70 full-rank exact-equality checks and175 first-estimate pairing checks.
Plot generation and the complete saved-policy audit use explicit E: cache/temp
directories and add no learning transitions. The complete remote archive is
SHA256-verified; local derived reports are accompanied by their own file hashes.

A separately labelled POST-HOC diagnostic continues each of the300 fresh-seed
NPG endpoints with16 true-gradient updates at the SAME eta=.05. It tests whether
the noisy endpoints are locally easy to improve; it does not alter formal Nhat,
charge samples, extend the sampled learning algorithm, or retune its parameters.
Offline true-subspace loss decomposition is likewise evaluator-only. Both are
saved alongside, and distinguished from, the pre-sampling K0 oracle checks.

Own Slurm jobs occupied112.978889 allocated core-hours (reported TotalCPU110.535817),
below the140 cap. These are measured Slurm counters, not a claim of completed AMS
settlement. Full campaign unique physical transitions, including failed exploratory
pilot and diagnostic sampling, are77,540,581,732; no shared prefix is double-counted.
