Scope: **X3 CE REPORT** (NPG has separate running/pilot stages). Complete independently checked report and figure files are local.

41472 outputs, 5747 failures retained. Independently rechecked34839 saved candidate policies, including unstable candidates; max normalized discrepancy between two gap identities4.97134e-10<1e-8. Stability/radius agrees exactly.

At largest tested regression N per case, medians [IQR]; failures contribute+infinity:

| n | r / spectrum | N | Method | Absolute gap | Relative gap | Stable |
|---:|---|---:|---|---|---|---:|
| 16 | flat | 32768 | dense | 0.00265457 [0.00250797, 0.00280712] | 0.00126095 [0.00115444, 0.00140717] | 32/32 |
| 16 | flat | 32768 | adaptive_paper | 0.00265457 [0.00250797, 0.00280712] | 0.00126095 [0.00115444, 0.00140717] | 32/32 |
| 16 | flat | 32768 | adaptive_split | 0.00265457 [0.00250797, 0.00280712] | 0.00126095 [0.00115444, 0.00140717] | 32/32 |
| 16 | gapped | 32768 | dense | 0.0739229 [0.0256991, 0.246799] | 0.0528188 [0.037709, 0.069951] | 32/32 |
| 16 | gapped | 32768 | adaptive_paper | 0.447802 [0.0986351, 1.64089] | 0.276897 [0.234275, 0.317636] | 32/32 |
| 16 | gapped | 32768 | adaptive_split | 0.130224 [0.0506986, 0.556387] | 0.107457 [0.0850906, 0.153515] | 32/32 |
| 16 | smooth | 32768 | dense | 0.0368775 [0.0144222, 0.121583] | 0.0275877 [0.0196678, 0.048681] | 32/32 |
| 16 | smooth | 32768 | adaptive_paper | 0.0920199 [0.0323108, 0.449806] | 0.0894755 [0.033567, 0.134596] | 32/32 |
| 16 | smooth | 32768 | adaptive_split | 0.0379717 [0.0175155, 0.192202] | 0.0359996 [0.0231158, 0.0527901] | 32/32 |
| 32 | flat | 65536 | dense | 0.00499988 [0.00483279, 0.00516144] | 0.00126489 [0.00122232, 0.00132698] | 32/32 |
| 32 | flat | 65536 | adaptive_paper | 0.00499988 [0.00483279, 0.00516144] | 0.00126489 [0.00122232, 0.00132698] | 32/32 |
| 32 | flat | 65536 | adaptive_split | 0.00499988 [0.00483279, 0.00516144] | 0.00126489 [0.00122232, 0.00132698] | 32/32 |
| 32 | gapped | 65536 | dense | 0.906282 [0.379215, 2.5463] | 0.0577395 [0.0434619, 0.0699173] | 32/32 |
| 32 | gapped | 65536 | adaptive_paper | 7.41064 [2.09862, 19.4502] | 0.40554 [0.277933, 0.634858] | 31/32 |
| 32 | gapped | 65536 | adaptive_split | 2.05967 [0.860634, 5.0836] | 0.119301 [0.0937844, 0.203953] | 32/32 |
| 32 | smooth | 65536 | dense | 0.306441 [0.13467, 0.480867] | 0.037062 [0.030559, 0.0471764] | 32/32 |
| 32 | smooth | 65536 | adaptive_paper | 0.302888 [0.109681, 0.421965] | 0.0340889 [0.0274227, 0.0431368] | 32/32 |
| 32 | smooth | 65536 | adaptive_split | 0.181309 [0.0895302, 0.292392] | 0.0250983 [0.0190133, 0.0314426] | 32/32 |

Negative findings: at n32/two-level/maxN, adaptive_paper has1/32 failures and absolute median7.41064, versus dense.906282; split median2.05967. Both rules retain too much approximation bias here. k0 fails3456/3456 and remains a diagnostic outside r>=1; it is excluded from the fixed-k envelope, not deleted. Flat spectrum selects full rank throughout and both adaptive rules match dense at high N. Smooth/two-level best fixed order tends to grow with budget but is not strictly monotone. The envelope uses fixed-k group medians, not per-trial truth-selected outputs.

C5=2.569143010355372,delta.05, both data-only rules. `report-ce-v2/best_retained_order.png/.svg` shows the actual nonmonotone order sequence; `stable_region_n16/n32.png/.svg` display only common32/32-stable cells under the disclosed stability rule. The n32/two-level highest prefixes fail that rule and are absent from this **restricted view**, but remain in complete-grid `report-ce/spectrum_scan_n32` and all records/heatmaps. Do not use the restricted view to claim high-budget universal stability.

All paths below `experiments/supplement-20261101/X3/`:

- `report-ce/all_records.csv`
- `report-ce/all_statistics.csv`
- `report-ce/paired_ratios.csv`
- `report-ce/paired_bootstrap_effects.csv`
- `report-ce/fixed_k_envelope.csv`
- `report-ce/spectral_tails.csv`
- `report-ce/system_certificates.csv`
- `report-ce/spectrum_scan_n16/n32.png/.svg`
- `report-ce/stability_n*_r*_{smooth,gapped,flat}.png/.svg`

Exact resolved config/approval hashes are in `ACCEPTED_CE.json` and the formal v13 manifest; report source SHA256 `683951ef6c2864a11651707a7b785d4ece9b47592e95d9077e4e7550e636b343`, frozen engine `9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`. Saved-data refinement source/manifest: `packages/supplement-20261101-ce-figures-refine-v20.manifest.json`. Each plot/table has a complete CSV source. Original report-v1 files are preserved; old178 files remain unchanged.


Review03:00 failure breakdown (all prefixes; k0 is explicitly diagnostic):

| Category | Method | Failed / all outputs |
|---|---|---:|
| diagnostic_k0 | k0 | 3456/3456 |
| learning_r_ge_1 | adaptive_paper | 332/3456 |
| learning_r_ge_1 | adaptive_split | 152/3456 |
| learning_r_ge_1 | dense | 145/3456 |
| learning_r_ge_1 | k1 | 528/3456 |
| learning_r_ge_1 | k12 | 139/3456 |
| learning_r_ge_1 | k16 | 95/1728 |
| learning_r_ge_1 | k2 | 212/3456 |
| learning_r_ge_1 | k24 | 100/1728 |
| learning_r_ge_1 | k3 | 168/3456 |
| learning_r_ge_1 | k4 | 141/3456 |
| learning_r_ge_1 | k6 | 137/3456 |
| learning_r_ge_1 | k8 | 142/3456 |

Exact per-case **method x N x k** breakdown: `report-ce-v3/failure_by_n_spectrum_method_k_N.csv`; `failure_summary.csv` and `REPORT.json` give totals and provenance. Learning outputs fail2291/38016; k0 diagnostic fails3456/3456. The5747 total must not be described as5747 learning failures. All32 outputs remain in each tested-cell denominator.

Limit: these pilot-calibrated finite budgets do not numerically certify the theory sample constants; observed finite-budget instability is retained, not described as a contradiction or hidden by successful-case medians. There are no new training transitions in either report job. Full local formal raw delivery verified: `deliveries/delivery-ce-full-formal-raw-v1.verified.json`,1728 files,737700825 bytes. All178 earlier protected files remain byte-identical.
