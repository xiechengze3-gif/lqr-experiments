# X7 CE effective-rank experiment

The registered CE experiment shows a sample-size-dependent tradeoff between estimation error and truncation bias. The geometric spectrum supports useful truncation throughout this grid. For the polynomial spectrum, dense CE becomes the best member of the registered fixed-order set at larger budgets. The paper threshold with the literal C5=2.569 is conservative and sometimes loses to dense. These negative comparisons are retained.

## Design and algorithm

This experiment is CE only. It does not run NPG, PI, LSTD, or a critic. The frozen CE collector uses one continuous trajectory under K0=0 with exploration variance nu=1, 512 burn-in transitions and nested regression prefixes. Unwhitened OLS estimates the full (A,B); all arms share that same fit at each prefix. Only Bhat is truncated before the CE Riccati solve. Ahat is unchanged. No failed solve is replaced by K0. A later prefix is evaluated even if an earlier prefix failed.

The stable S family is the same fixed-certificate family as X6: n=m in {24,48}, Q=R=W=I; A has an independent Haar rotation and eigenvalues uniform in [.15,.60], giving ||P_K0||<=1.5625. B has independent Haar left/right factors, norm 1, and is full rank: sigma_j=.7^(j-1) or 1/j. Formal system IDs 501–508 and sampling seeds 1801–1804 give 32 runs per (n,spectrum), with eight systems as the bootstrap clusters. Resource pilots 9501/9502 are excluded from all formal statistics.

For d=n+m, the six budgets are N=4d times {1,4,16,64,256,1024}. Thus n24 uses 192 through 196608 transitions and n48 uses 384 through 393216. Total trajectory length at a prefix is N+512. There are 128 physical formal trajectories, 768 shared fits and 10752 arm outputs; the physical formal sample count is 37814272, counting burn-in once per trajectory. Reused arms and prefixes are not counted as independent trajectories.

The fixed orders are {1,2,3,4,6,8,12,16} for n24 and additionally {24,32} for n48, plus dense k=n. Data-driven arms are: paper threshold 2.569*sqrt((d+log(1/.05))/N), split threshold ||Bhat_half1-Bhat_half2||op/2, and registered sensitivities with paper-form constants .5 and 1. Singular values must be strictly greater than the threshold. Order zero is allowed and reported. Sensitivities are not selected or retuned using performance.

## Results from the frozen CSVs

Every arm at every budget has 32/32 stable outputs: 0/10752 failed outputs overall. The failure-inclusive and both-stable paired ratios therefore coincide; each uses 32 eligible pairs, no both-failed exclusion and no empty bootstrap repetition. All 224 registered slope summaries have zero unidentified bootstrap repetitions.

The following ratios are medians of paired dense/arm gaps, with 95% pointwise system-bootstrap intervals. They are not ratios of group medians. The selected fixed orders are post hoc group diagnostics selected using the full-32 median absolute gap, including dense; their intervals do not correct for this selection.

| Spectrum | n | N in ascending order | Post hoc best fixed k |
| --- | --- | --- | --- |
| Geometric | 24 | 192,768,3072,12288,49152,196608 | 1,4,6,8,12,12 |
| Geometric | 48 | 384,1536,6144,24576,98304,393216 | 1,4,6,8,12,12 |
| Polynomial | 24 | 192,768,3072,12288,49152,196608 | 1,2,24,24,24,24 |
| Polynomial | 48 | 384,1536,6144,24576,98304,393216 | 1,3,6,48,48,48 |

For the geometric spectrum at N=768 (n24) and N=1536 (n48), k=4 gives paired ratios 2.066 [2.001,2.124] and 3.966 [3.894,4.018]. At the largest budgets, k=12 gives 1.101 [1.094,1.111] and 1.811 [1.786,1.853]. The lowest-budget ratios are larger (4.059 and 8.122 for k=1), but the corresponding relative-gap medians exceed 1: 1.089 and 1.039. Improvement over a poorly estimated dense controller at that budget does not imply improvement over K0.

For the polynomial spectrum, small fixed orders leave a substantial tail. Dense is post hoc best from N=3072 for n24 and from N=24576 for n48. At the largest N, relative-gap medians for k=16 versus dense are .02670 versus .003542 (n24), and for k=32 versus dense are .01844 versus .006656 (n48); exact values remain in summary.csv. These are useful counterexamples to a blanket recommendation to truncate at a fixed small order.

The literal paper threshold chooses k=0 in all 32 runs at the first budget of every cell. The resulting relative gap is approximately 1 because the rank-zero CE solution is K0=0; this is a valid threshold outcome, not a failure fallback. At the largest geometric budgets, paper-order medians are 10 while the post hoc best fixed order is 12. Its paired ratios are .7793 [.7193,.8580] for n24 and 1.488 [1.469,1.571] for n48. Split chooses median order 12 in both cases and gives 1.094 [1.077,1.111] and 1.801 [1.784,1.840]. Thus the adaptive paper rule is not uniformly better than dense, even with the faster-decaying spectrum.

The polynomial high-budget limitation is stronger. At the largest N, the paper-order medians are 22 and 25, below dense orders 24 and 48. Paired ratios are .4903 [.4551,.5587] and .2476 [.2453,.2556]; split gives 1 [1,1] and .6974 [.6595,.7113]. The latter losses are consistent with retained truncation bias and conservative order selection. The saved sensitivity curves show the consequences of other registered constants, but they do not authorize choosing a new constant after seeing these outcomes.

## Rates and interpretation

The registered last-three-budget slopes of log median relative gap versus log N are:

| n, spectrum | Dense | k=1 | k=12 | Paper | Split |
| --- | --- | --- | --- | --- | --- |
| 24, geometric | -.9921 | -.00220 | -.9735 | -.8735 | -.9157 |
| 48, geometric | -1.0073 | -.00280 | -1.0163 | -.9189 | -.9073 |
| 24, polynomial | -.9988 | -.00287 | -.2459 | -1.1052 | -1.1605 |
| 48, polynomial | -1.0037 | -.00340 | -.2091 | -.6835 | -.9037 |

All six-budget slopes, absolute-gap slopes and all bootstrap intervals are supplied in log_slopes.csv and RESULT_TABLES.md. A three-point slope is a descriptive fit over its declared window, not an asymptotic rate proof. Dense is close to 1/N here; small fixed orders flatten as tail bias dominates. Changing adaptive orders can produce a slope steeper or shallower than -1 over this grid. We do not fit a 1/N line after deleting inconvenient points.

This pattern is consistent with a variance–tail tradeoff such as k*d/N plus tau_k^2 as an unscaled shape proxy. It does not identify its system-dependent constants, certify a numerical k_epsilon, or validate that proxy as a calibrated gap predictor. spectral_tails.csv supplies tau_k^2 and beta_k for every k=0..n. No budget-to-epsilon attainment claim is made from the factor-four X7 grid.

The observed losses do not establish a theorem contradiction. X7 is a finite-budget CE comparison on full-rank systems. An error upper bound involving estimation and approximation terms does not promise that every truncated or thresholded arm beats dense at every N, or that every fixed-order arm has vanishing bias. C5=2.569 is the literal accepted experimental constant; this experiment does not certify that it satisfies every system-dependent sufficient constant in the paper. X7 also does not test the NPG all-iterate statement of Theorem 3. Any manuscript use should preserve these distinctions rather than claim a verified theoretical constant or universal adaptive improvement.

## What belongs in the paper

The fixed-order surface, growing post hoc order and eventual return to dense for the polynomial spectrum are suitable evidence for the effective-rank mechanism. Show both spectra and distinguish the group-level post hoc diagnostic from an implementable learner. Use the adaptive curves with their losses and chosen orders disclosed. The first-budget paper-rule advantage over dense is entirely compatible with choosing zero control and should not headline a successful-learning claim.

The X6b fixed-certificate NPG/PI experiment remains the appropriate actor comparison; X7 does not replace it. Earlier algorithm variants, unmatched certificates or failed undersized schedules should not be mixed into this CE grid or used to claim the exact theorem's guarantees. No paper tex or old result was changed.

## Reproducibility and cost

All scientific simulation, OLS/gain/cost audits and 5000 common-draw system-cluster bootstraps ran on Grace compute nodes. Local processing only verified hashes/coverage, copied exact CSV bytes, formatted saved values and drew figures. All 768 fit/policy archives passed content and hash audits; maximum OLS and policy relative error was zero, and maximum cost-identity error was 1.1364e-13. The sealed deliveries contain 2049 formal/provenance files and 77 report/metadata files; all 2126 members were hash-verified before extraction.

Jobs: resource 20375552 (4 tasks); formal 20375602 (32); diagnostics 20375654/56/58/65 (one each); summary 20375691 (one). All completed, no retry, requeue or scope change. Requested upper bound is 4.6 SU out of the independent X7 cap 15 SU. Completed Slurm elapsed billing is .372777778 SU. At 23:53:43 UTC, AMS had settled .336666667 SU using walltime times slots; this overlaps Slurm and must not be added. The full accounting snapshot is accounting-20261102T235343.json. Rounded per-job display totals are not substituted for unrounded costs. Archive metadata is a snapshot taken during packing; the later accounting file is authoritative for completed-state billing.

CSV entry points are directly in this folder: summary.csv, paired_ratios.csv, paired_records.csv, all_records.csv, adaptive_orders.csv, posthoc_best_fixed.csv, log_slopes.csv, model_certificates.csv, spectral_tails.csv. PER_ARM_TABLE.md lists every cell's absolute/relative medians, IQR and stability. RESULT_TABLES.md provides compact comparisons, orders and every slope. plot_saved_ce.py draws five PNG/SVG figure pairs without any model calculation. All five PNGs were visually inspected for clipping, labels, legends, failure disclosure and preservation of unfavorable results.
