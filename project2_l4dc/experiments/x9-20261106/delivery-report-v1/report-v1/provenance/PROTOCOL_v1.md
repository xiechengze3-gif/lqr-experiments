# X9 PROTOCOL v1

Authority: X9 GO (22:35 CDT 11/05), author-approved, read before publication. Cap 50 requested SU: PILOT <=1, FORMAL proposed 46.9333333, REPORT <=2. No automatic retry, no outcome-dependent cut, no changes to old records/releases/docs or paper tex. X8 remains a draft. This scan is empirical and outside the certified conditions of Theorem 3; it is not a verification of that theorem.

## Frozen science

Family S, n=m=24, unchanged X6b A (independent A/B streams), Q=R=W=I, K0=0, ||P0||<=1.5625, p0 class bound 2, eta=.2, nu=1, H=16. Every stage includes 16 pulse-protocol burn blocks and one baseline block. NPG has 16 updates, PI has 8 full greedy updates. No LSTD/critic/ridge/whitening/damping/safety/recovery modification. Formal systems 301–308 × seeds 1701–1704, paired namespaces exactly `rng(20 if NPG else 21,24,24,system,seed,stage)`, with no arm/alpha tag. All rungs restart their policy at K0; states are continuous within each path.

Pre-registered alpha grid `{0,.05,.1,.2,.4}`, tau2_sq=22 alpha² `{0,.055,.22,.88,3.52}`. The .4 endpoint is a large-tail control. Retained order is k=2 for both truncated learners; physical rank is 24 for alpha>0. For alpha>0 use B=B_X6b+alpha*(U_tail@V_tail.T), regenerating full U,V from the frozen original streams. Keep original binary A/B0/K0/P0/cost matrices. Compute each positive-alpha Kstar/Pstar/Jstar and initial gap for evaluation only. No truth enters an update or order choice. Report all registered cells even if benefits do not disappear or failures occur.

NPG update and Stein collector are byte-for-byte original. PI is PSD clip Ghat, joint leading-two left subspace of [Gplus,Zhat], two-sided G compression, matching Z projection, full solve with R+G_used. The actor checkpoint wrapper differs from X6b only in the allowed output root. Source identity and the single-string change are checked before freezing; numerical gain/collector/RNG/count equivalence is checked on compute in the resource pilot.

N_cal=524288; all four integer schedules are copied from the frozen X6b formal config, without rerounding. The four rungs are 1/64,1/16,1/4,1. Per-arm primitive counts are 2964976,11846384,47372272,189475712 for either algorithm. Both arms consume all burn/baseline/padding transitions. Instability is an absorbing failure, later budget is consumed under K0 only as padding; no recovery, selection of an earlier iterate or deletion. A hard numerical/infrastructure failure leaves complete-stage checkpoints and a failure receipt; no automatic resubmission or invented partial transition count.

## Exact-rank reuse

Alpha=0 is reused in full from X6b n24: 256 paired paths /512 endpoints, all rungs and all failures. No observations or learner states are transplanted into alpha>0. Baseline source/config/model/receipt hashes and the saved summary/endpoints are bound into the protocol; existing originals remain untouched. Copying the frozen CSVs/model inputs into this new release does not create a new independent replication. Baseline bootstrap summaries remain the saved ones. Plot/table provenance identifies this cell as reused.

## Resource-only pilot, authorized after this protocol by X9 GO

Exactly four 1-CPU/2-GiB/15-minute tasks, array0–3%4 (upper1 SU), on disjoint pilot systems/seeds:

| index | measured alpha | algorithm | pilot system | seed | prepare formal models for alpha |
|---:|---:|---|---:|---:|---:|
|0|.05|NPG|9601|1901|.05|
|1|.05|PI|9601|1901|.1|
|2|.4|NPG|9602|1902|.2|
|3|.4|PI|9602|1902|.4|

Each task first prepares the eight deterministic formal model inputs for its assigned alpha (zero formal observation transitions); no formal learning trajectory is collected. These evaluation-only truth solves do not calibrate parameters or select models. Each task compares the original engine actor_run against the new checkpoint wrapper on its pilot system, at alpha=0 and its measured positive alpha, two stages [256,512], both arms. Require bitwise gains, collector outputs, final collector RNG states and primitive counts; do not print gap, stability, selected ranks or per-arm performance. Short equivalence work consumes 102656 transitions per task, fully counted, in addition to the timing work.

Then measure the four complete fixed-rung paths for that algorithm (both arms, exactly as formal), recording runtime, peak RSS, transition counts and artifact hashes only. Learner/failure control may internally evaluate stability exactly as the frozen algorithm; no performance is read out or used for planning/selection. Pilot parameters are never tuned from results. Timing work is 503318688 primitive transitions per task; total pilot including reference/equivalence work is 2013685376 transitions. The job wall limits impose a hard requested upper bound of 1 SU; no retries.

## Formal resource decision and gates

Twelve arrays, 32 tasks each, new four-alpha observations only: per alpha low-three rungs/both algorithms at8 min, full NPG at7 min, full PI at7 min; all1CPU/2GiB. Total384 allocations, 1024 paired paths /2048 arm paths, 128849584128 transitions, proposed46.9333333 SU. Enforce global concurrency <=8 by sequential arrays (afterok dependency or submit the next only after complete successful accounting/coverage); not eight simultaneously in each array.

Use pilot maximum full-path seconds across the two measured tails for each algorithm. For low-three, use the sum of each algorithm's maximum sum-of-three times across those tails. Require `1.20*predicted_group_seconds+30 <= requested_group_limit_seconds`, and measured peak RSS <=80% of2GiB. The30s guard covers loading/launch/model metadata, in addition to20% measured-body headroom. Do not reduce scientific scope or retune after a failed resource check. If the limits or50-SU cap cannot be met, report and stop for a resource decision.

After PILOT, post checks, exact timings/RSS, model/source hashes, current requested/settled spend and the measured formal plan. **Wait for Claude's PILOT ACCEPTED before FORMAL**; do not infer approval from GO alone. Re-read the review log before every advancement. Before every submission check myproject, own queue/accounting, prospective billing and the X9-only ledger. A durable reservation/receipt precedes sbatch; an uncertain response is reconciled before any further mutation. Do not affect unrelated jobs.

REPORT reserve2 SU, saved-data-only analysis/plots/hash packaging. Source/config equivalence and matched path coverage must pass before reporting. Local arithmetic/AST/source-byte checks use no simulation. Numerical work runs only on Grace Slurm compute nodes; login work is metadata/submission/files only. Explicit scratch TMPDIR/cache/Numba/Matplotlib directories under the new X9 namespace, one BLAS/OpenMP/Numba thread; no installations. Local results/packages under this E-drive experiment folder.

## Frozen report and interpretation

Per alpha × algorithm × rung × arm, report failure-inclusive absolute/relative gap median and IQR, stable count/full32, exact primitive counts and padding, every first-failure stage and every failed endpoint. Failures enter gap summaries as+inf. Report both-stable and failure-inclusive matched dense/truncated ratio medians with5000 system-cluster paired bootstrap resamples (8 systems, all4 seeds together); exactly reuse X6b bootstrap RNG/tag and use common draws across alpha/rungs/ratio kinds per algorithm. Preserve invalid/undefined resample counts, infinities, both-failed ratios and full denominators. No ratio of group medians is called a paired gain.

Export `summary.csv` with exactly the original X6b-report-v1/summary.csv columns plus alpha and tau2_sq. Alpha=0 rows are saved baseline rows with only the two new descriptors added. For positive alpha, exact-nullspace D/action decomposition fields and structural_factor are N/A (eligible0), and redundant-cost share is N/A. Do not put complement-action energy in main tables. Export tidy endpoint and new-stage/pair CSVs plus an explicit failure CSV; no failed rows omitted.

Export `transitions_saved_derived.csv`: for each alpha/algorithm, target the full-rung dense failure-inclusive median absolute gap; find where the truncated failure-inclusive median curve first reaches that target using the *same cross arithmetic* as current `figs/make_figs.py` behind `figs/data/X6b_transitions_saved_derived.csv`. Use primitive transitions on the horizontal axis, no monotone smoothing or extrapolation. If already reached at the first rung, encode the observed bound and left_censored=true; if never reached, retain missing estimate/right censoring. Preserve nonfinite targets and a crossing without a finite interpolation bracket as unidentified/unbracketed, not a fabricated finite estimate. Include the saving factor full_rung_transitions/matching_transitions and censor flags. This is a descriptive post hoc median-curve interpolation on a factor4 ladder, not epsilon sample complexity, a 29/32 success claim or theorem validation.

If truncation loses or fails as the tail grows, retain it. Fixed k2, the inherited empirical finite-sample schedule and especially alpha.4 are outside conditions numerically certified for Theorem3. The theorem's approximation term and statistical/small-tail requirements must accompany interpretation; no same-epsilon guarantee is implied. PNG/SVG and all figure CSVs are delivered in this new folder, with source/config/result manifests and accounting. Do not edit the paper.


## Frozen hashes

Config SHA256: ff3f89cbae75e35c3f079e30d69f7bd1b4af63bf661528d65247563ee05c0196

- frozen_engine.py: 9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989
- estimation.py: f587bd48993288dbf9160dd4cc1e62542f15ee5794bda37590ec48dc672c9c59
- actor_paths.py: 905ebe819c50c860249dc11836eb9f356b97b6ea8d4ebe22e34d5a0e4f7deb3b
- x9_core.py: e62b82f5617179791e362189ab5900b3c29dbf7ad2d2785813376fc02884c050
- analyze_x9.py: 7eafc31a73ab8e3f8924561d4892682e8bf73f57b06b5c321018494792a773bd

Source AST, byte-identity and scalar count checks PASS; numerical equivalence/RSS/timing PENDING compute pilot.
Prepared before any X9 numerical work. X9 requested 0/50 SU, settled 0 SU.
