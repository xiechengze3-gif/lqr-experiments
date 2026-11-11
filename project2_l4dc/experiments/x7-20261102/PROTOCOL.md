# X7 PROTOCOL v1 â€” effective-rank CE at fixed certificates

Prepared in response to X7 GO(author-approved16:55,2026-11-02).
No X7 trajectory,model solve,resource job or formal job has run. This document
requests PROTOCOL acceptance; resource PILOT starts only after that acceptance.
FORMAL waits for the measured PILOT report and a new explicit acceptance.
The X1/X2 timeout exception does not apply. No paper TeX or old result is changed.

## Question and interpretation fixed before observation

Test the fixed-order variance/tail tradeoff for full-rank actuation and compare
data-only adaptive thresholds. A growing best fixed order,large truncation gain,
or slope-1 is a hypothesis,not a required outcome. All registered cells,failures,
rank0 adaptive outputs,censored/infinite ratios and negative results remain.
The uncalibrated shape k*d/N+tau_k^2 is a diagnostic,not a numerical risk bound.
The paper's c_eff is not numerically identified,so tail tolerances are not
silently called certified numerical k_epsilon.

## Models,streams and certificates

CE only;n=m24/48. Q=R=W=I,K0=0,nu1. Exactly the X6 S generator:
e.rng(1,n,system) draws Haar rotation then lambda_i~U(.15,.60);
A=rotation*diag(lambda)*rotation^T. Independent e.rng(2,n,system) and
e.rng(3,n,n,system) draw Haar U/V. B=U diag(sigma) V^T with
geometric sigma_j=.7^(j-1) or polynomial sigma_j=1/j,j1..n.
All directions are nonzero;||B||=1 and ||P_K0||<=1/(1-.6^2)=1.5625.
No rejection,seed replacement,orientation selection or gap-based tuning.
A/U/V and exogenous streams are paired across spectra at the same n/id,
but B and the control problem differ; no cross-spectrum ratio is a gain.

Formal systems501â€“508Ã—sampling seeds1801â€“1804=32 paths per(n,spectrum).
Pilots9501/9502Ã—8101/8102 are disjoint. Frozen RNG root2026110101 matches
the existing engine; CE innovations use e.rng(10,n,n,system,trial).
The generator's true matrices/optimal policy/costs are simulator/evaluation
metadata only. Observation-only CE receives theta,known Q/R,n and a rank.

Resource PILOT generates every formal model once(no formal observations)
and freezes its NPZ hash registry. All32 formal models are retained. Reports
include rho(A),P0_op,J0,Jstar,initial gap,v_star,||B|| and smallest singular
value for every model. The normalized K0 overlap is undefined for zero K0;
it is not fabricated as0. Save tau_k^2=sum_{j>k}sigma_j^2 and
beta_k=sigma_{k+1},including k0..n and the zero tail at k=n.

## One trajectory,one shared fit per prefix

Exactly the frozen ce_run CE exploration/OLS:
u=-K0*x+xi,xi~N(0,I),including512 burn transitions; x starts0.
Unwhitened joint OLS theta=solve(Gram,Cross^T)^T,no ridge or coordinate
whitening. Continuous state and RNG;512-transition chunks,with stops at every
registered prefix and its exact half. No restart/resampling at a larger budget.
Every arm at that prefix uses the identical full-prefix Ahat/Bhat.

N=4dÃ—{1,4,16,64,256,1024},d=n+m:

|n|regression prefixes N|largest actual M=N+512|
|---|---|---:|
|24|192,768,3072,12288,49152,196608|197120|
|48|384,1536,6144,24576,98304,393216|393728|

Report both N and M. Physical formal sampling is128 continuous trajectories,
37,814,272 transitions including each burn once. There are768 full-prefix OLS
fits plus their two half solutions. Do not sum reused prefixes or arms as
additional sampled transitions. Simulator Lyapunov/DARE evaluation uses no
additional trajectory transitions.

For all arms K=LQR(Ahat,T_k(Bhat)); Ahat remains unchanged:
- Dense:k=n.
- Fixed orders:k1,2,3,4,6,8,12,16 at n24; additionally24,32 at n48.
  k>=n is represented only by dense; no duplicated fixed arm.
- adaptive_paper:retain estimated singular values STRICTLY greater than
  2.569*sqrt((d+log(1/.05))/N).
- adaptive_split:retain values STRICTLY greater than
  ||Bhat_first_half-Bhat_second_half||op/2; multiplier1,from exact sufficient
  statistic halves of the same trajectory; no extra data.
- sensitivity_C0p5 and sensitivity_C1p0:the same paper-form threshold with
  C=.5 or1.0,explicitly labeled "sensitivity,not selection". Never pick their
  constant based on gaps or promote the best as an adaptive selector.

C5 is exactly2.569 as the X7 GO specifies. The old X3 archive recorded the
unrounded calibration2.569143010355372; no new calibration is performed here.
This exact literal choice is exposed for review before any X7 run.
There are13 arms at n24,15 at n48,and10,752 formal policy-output rows.
Adaptive k=0 is allowed and explicitly counted. No fixed k0 diagnostic is added.

All DARE/learner failures and unstable policies are failed outputs,gap=+infinity
for primary summaries. No K0 fallback or earlier-policy replacement.
Data collection always uses the fixed safe K0; a failed CE output at one prefix
does not prevent the distinct larger-prefix CE fit from succeeding. This is
the frozen CE behavior,not actor-style absorbing padding.

## Frozen artifacts and equivalence

The original frozen_engine.py is copied byte-for-byte,including ce_chunk,
fit_model,ce_learner,assess and ce_run. New source wraps these functions to
save full/half OLS,Gram/Cross,full state/RNG,estimated singular values,
unique-rank policy matrices and per-arm records at every prefix.
NPZ/checkpoint/source/config/model hashes and exact counts form the audit chain.

At each of the four resource cases,one pilot path is independently executed
through the UNCHANGED original ce_run. Temporary pass-through capture wrappers
around fit_model/ce_chunk/rng record returns without changing them,and are
restored in finally. Compare all full/half fits,final state and RNG bitwise,
common output fields bitwise,and policies within relative1e-11.
No numerical equivalence run is performed locally. These reference paths are
extra pilot cost and are included in its allocation and sample accounting.

Completed-prefix checkpoints can be reused only after separate failure review,
same source/config/model/spec,and copying verified prefixes to a NEW output
directory. Old artifacts are never overwritten. No automatic retry/requeue.

## Analysis fixed before FORMAL

The saved-data audits run on Grace compute nodes. Per prefix verify model/
fit/policy archive SHA,all three OLS solves,rank/threshold selection,CE gains,
stable flags and true costs. Tolerances:fit/policy relative1e-11,numeric
thresholds1e-11,recorded cost/gap1e-9; cost identity tolerance1e-7.
Verify10752 rows,768 fit/policy NPZs,128 paths,32 models and physical counts.

For each(n,spectrum,N,arm),report FULL32 failure-inclusive absolute/relative
gap median/Q25/Q75,stable counts and chosen-order median/IQR,including failed
outputs in the order summaries. Quantiles use type7 linear interpolation;
positive-infinite mass is retained,never capped or replaced by a finite value.
Relative gap is g/g(K0) on the SAME model.

For every non-dense arm,including the two labeled sensitivities,report paired
g(dense)/g(arm) BEFORE aggregation under BOTH definitions:
both-stable conditional and failure-inclusive(one-sided failures0/inf,drop
only both-failed). Report full32,eligible pairs,both-failed,one-sided failures,
and empty conditional bootstrap draws. Both zero finite gaps give ratio1;
zero denominator alone gives infinity. Absolute and relative paired ratios
coincide because the same initial gap cancels; no cross-system ratio is used.

5000 system-cluster bootstrap draws sample8 systems with all4 seeds preserved.
Within each(n,spectrum),COMMON draws are used across budgets,arms,definitions,
and slopes. Report percentile pointwise95%CIs,not simultaneous coverage.
Empty conditional draws are excluded only from that conditional percentile
and counted. Infinite quantiles stay infinite.

Post-hoc best fixed order is the argmin of the FULL32 group median absolute
gap over registered fixed orders INCLUDING dense(k=n); ties choose smaller k.
Also report best truncated order k<n separately. If all candidates have
infinite median,the optimum is unidentified. This group envelope is labeled
POST HOC,not available to the learner; do not choose the per-run best policy.
Do not force the chosen order sequence to be monotone.

For each arm,metric(absolute and relative) and registered window(all six N,
last three N),fit OLS log(full32 median gap) vs log N. If any selected median
is infinite or nonpositive,the slope is NA,with affected budgets retained.
Use the same cluster bootstrap; report unidentified draw count and label its
finite-slope CI conditional. Compare descriptively to-1; no trimming,window
selection,forced power law or extrapolation.

The factor4 grid is NOT a sqrt2 attainment grid,so this study makes no
budget-to-epsilon claim. Threshold-versus-true-spectrum diagnostics are
evaluation only and are never used to select a learner rank/constant.

## Resource gates and hard budget

X7 has an independent15SU requested-upper cap; X6's final cap/accounting
is unaffected. X7 currently0 requested/0 settled SU,no submitted job.
No model/numerical run until PROTOCOL is explicitly ACCEPTED.

|stage|planned allocation|requested upper SU|
|---|---|---:|
|Resource PILOT|4 case tasks,each4 pilot paths+1 ce_run reference;1CPU/2GiB/15min|1|
|FORMAL ceiling|32 system/seed bundles,each all4 cases;1CPU/2GiB,at most20min|10.666667|
|REPORT reserve|4 case auditsÃ—20min +1 summaryÃ—40min;all1CPU/2GiB|2|
|Total conservative envelope,UNMEASURED|no retry allowance used|13.666667/15|

Resource readout includes only runtime,RSS,hash/count/equivalence proofs.
Real fits/policies are computed to time the actual workload,but their gaps,
stability and adaptive orders are not inspected or used for calibration.
The resource pilot also prepares all32 deterministic formal models without
formal observations; this is not formal performance selection.

After all four pilots finish,formal bundle time is
ceil((1.3*sum_case(max measured full-path seconds))+60)/60) integer minutes.
Include peak cold-start/compile time as measured; validate worst n48 and all
arms. Request2GiB only if max process RSS has>=20% headroom; otherwise report
resource/cost revision before formal. A required bundle limit>20min or total
request>15SU stops submission for review; no post-outcome pruning or grid cut.
The measured plan and resolved model/config hashes wait for explicit FORMAL
acceptance. REPORT follows only complete coverage and its corresponding gate.

Before each submission,verify current account/balance,own-study jobs,requested
and settled cost separately;never add overlapping Slurm/AMS views. Initial
effective billing resources will be checked against actual Grace TRES.
All thread counts1. Existing Python3.11/Numba environment,explicit X7 remote
TMPDIR/XDG/Numba/MPL caches. Local configurable temp/cache on E only;
no dependency install. Last local E free76.5GB;recheck before large output.

Only new x7-20261102 result/release directories; no old X6/source result edits,
paper TeX,git push,Overleaf,SSH/PuTTY/VPN restart or main-window termination.
Use protected normal-Windows Grace checks/Invoke when remote work becomes
authorized. A lost submission response requires receipt reconciliation first.

## Delivery

Scientific sources,config,protocol and SHA manifest are frozen before the
pilot. Pilot numerical equivalence is PENDING and will not be implied by local
AST checks. Resolved formal config adds only measured resources and the model
hash registry; learning/data/analysis settings remain unchanged.

All summary CSVs are copied directly to experiments/x7-20261102/:
summary,paired_ratios,adaptive_orders,posthoc_best_fixed,log_slopes,
model_certificates,spectral_tails,all_records,paired_records,with source/hash
verification. PNG/SVG figures and CSV-only plotting script accompany them;
complete-grid failures remain visible. Raw/checkpoints may be deeper.
Every stage appends CODEX_REPLY.md and ends STATUS:<stage> DONE X7.
Continue foreground review monitoring rather than ending the chat.


## Frozen source/config hashes

Config SHA256: e35d5a95d9be205a2de3a3bdf8be12f15b25ce5599a2c93ad6b64b93d572165f

|source|SHA256|
|---|---|
|frozen_engine.py|9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989|
|ce_fullrank.py|8354be2fa64874c811dffe1aa3c367f78e125389d53f357c59a453b734af5fc4|
|analyze_ce.py|5f195e95ae91c5b5d9a8580e7f067783572f2376f368179abb7c2feda9525763|
|x7_driver.py|0a284a28e13b67ee48eaaf82af209afbdcaa6cd1666c6a6916666ddfeb033cbb|

Local checks:AST parse and scalar grid/count/resource arithmetic only,PASS.
Numerical equivalence/timing/RSS are PENDING the approved compute-node PILOT.
Author GO snapshot SHA: 6542a46618bc7f2ba22bc985ca7ec8944266eea3e2b4ad70e09377457b16e58d;preparation spent0SU.
