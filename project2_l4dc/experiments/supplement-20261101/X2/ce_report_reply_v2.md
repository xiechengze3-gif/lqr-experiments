Scope: **X2 CE REPORT** (NPG has separate running/pilot stages). Complete independently checked report and figure files are local.

9408 outputs, 1100 failures retained. Independently rechecked9408 saved candidate policies, including unstable candidates; max normalized discrepancy between two gap identities3.9274e-11<1e-8. Stability/radius agrees exactly.

At largest tested regression N per case, medians [IQR]; failures contribute+infinity:

| n | r / spectrum | N | Method | Absolute gap | Relative gap | Stable |
|---:|---|---:|---|---|---|---:|
| 12 | 2 | 24576 | dense | 0.0369062 [0.0120209, 0.171817] | 0.0381233 [0.0319258, 0.0500351] | 32/32 |
| 12 | 2 | 24576 | truncated | 0.00603543 [0.00216635, 0.0176717] | 0.0075732 [0.00554568, 0.0105906] | 32/32 |
| 24 | 1 | 49152 | dense | 0.616245 [0.150172, 50.9124] | 0.0860526 [0.0564273, 0.397941] | 28/32 |
| 24 | 1 | 49152 | truncated | 0.0410306 [0.00555143, 7.95529] | 0.00971386 [0.00201497, 0.0686347] | 30/32 |
| 24 | 2 | 49152 | dense | 0.28594 [0.0628299, 1.26305] | 0.0583683 [0.0467386, 0.0935913] | 31/32 |
| 24 | 2 | 49152 | truncated | 0.0305929 [0.00764291, 0.0739472] | 0.00671687 [0.00315225, 0.012613] | 31/32 |
| 24 | 4 | 49152 | dense | 0.0416525 [0.0174817, 0.0926234] | 0.0354796 [0.0266346, 0.0478813] | 32/32 |
| 24 | 4 | 49152 | truncated | 0.00733312 [0.00458971, 0.0152197] | 0.00598198 [0.00519252, 0.00745457] | 32/32 |
| 24 | 8 | 49152 | dense | 0.0143467 [0.0102064, 0.0194857] | 0.0114477 [0.00990623, 0.0136245] | 32/32 |
| 24 | 8 | 49152 | truncated | 0.00551739 [0.0049126, 0.00701064] | 0.00495229 [0.00392117, 0.0057705] | 32/32 |
| 48 | 2 | 98304 | dense | 0.412774 [0.171524, 12.4922] | 0.0761621 [0.0498268, 0.202201] | 31/32 |
| 48 | 2 | 98304 | truncated | 0.0316555 [0.00902122, 0.534851] | 0.00699863 [0.00288392, 0.0157687] | 32/32 |
| 96 | 2 | 196608 | dense | 3.3073 [0.958608, 19.2142] | 0.131213 [0.083054, 0.294556] | 28/32 |
| 96 | 2 | 196608 | truncated | 0.191093 [0.0416651, 1.55684] | 0.00699787 [0.00322301, 0.0320551] | 32/32 |

Budget-to-epsilon: 17/56 (case,arm,absolute/relative,epsilon) combinations attained the predeclared>=29/32 requirement; the remaining39 stay right-censored. No epsilon claim is extrapolated. Dense/truncated failures are771/4704 and329/4704 outputs over the entire grid, not just the main points. At n96/maxN dense is28/32 stable versus truncated32/32.

Review02:25 requested exact fixed N/d16,64,256 ratios vs n/r: both absolute and relative are in `report-ce/fixed_budget_ratios.csv` and clean `report-ce-v2/fixed_budget_ratios_clean.png/.svg`. Both ratios coincide because the shared initial gap cancels within each pair. These are finite-pair diagnostics, with the finite/full32 counts explicitly tabulated, not a fitted law or a replacement for failure-inclusive results. System-cluster bootstrap preserves all four seeds.

All paths below `experiments/supplement-20261101/X2/`:

- `report-ce/all_records.csv`
- `report-ce/all_statistics.csv`
- `report-ce/paired_ratios.csv`
- `report-ce/paired_bootstrap_effects.csv`
- `report-ce/fixed_budget_ratios.csv`
- `report-ce/budget_to_epsilon.csv`
- `report-ce/system_certificates.csv`
- `report-ce/dimension_scaling.png/.svg`
- `report-ce/stability_n*_r*_exact.png/.svg`

Exact resolved config/approval hashes are in `ACCEPTED_CE.json` and the formal v13 manifest; report source SHA256 `683951ef6c2864a11651707a7b785d4ece9b47592e95d9077e4e7550e636b343`, frozen engine `9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`. Saved-data refinement source/manifest: `packages/supplement-20261101-ce-figures-refine-v20.manifest.json`. Each plot/table has a complete CSV source. Original report-v1 files are preserved; old178 files remain unchanged.


Review03:00 failure breakdown (all prefixes; k0 is explicitly diagnostic):

| Category | Method | Failed / all outputs |
|---|---|---:|
| learning_r_ge_1 | dense | 771/4704 |
| learning_r_ge_1 | truncated | 329/4704 |

Exact per-case **method x N x k** breakdown: `report-ce-v3/failure_by_n_spectrum_method_k_N.csv`; `failure_summary.csv` and `REPORT.json` give totals and provenance. All32 outputs remain in each tested-cell denominator.

Limit: these pilot-calibrated finite budgets do not numerically certify the theory sample constants; observed finite-budget instability is retained, not described as a contradiction or hidden by successful-case medians. There are no new training transitions in either report job. Full local formal raw delivery verified: `deliveries/delivery-ce-full-formal-raw-v1.verified.json`,1728 files,737700825 bytes. All178 earlier protected files remain byte-identical.
