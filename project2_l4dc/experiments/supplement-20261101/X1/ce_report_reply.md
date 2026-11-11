Scope: **X1 CE only**. Actor R3 pilot is still in progress and actor formal remains gated.

Visual QA of both PNG figures passed. At the predeclared N8192 main point every
method/cell is32/32 stable; the15 failures all belong to N4096 and are retained
in the full tables and the two-prefix diagnostic. Dense redundant cost increases
over the matched m>r family and truncation suppresses it. The two N*D curves do
not coincide at these finite budgets, so this report does not claim an exact
universal1/N constant or perfect asymptotic collapse.

All288 continuous formal trajectories and1728 outputs are delivered. **15 unstable outputs are retained**, not rerun/deleted. Breakdown by method and regression prefix:

| Method | N | Failed outputs |
|---|---:|---:|
| dense | 4096 | 5 |
| oracle_true_space_diagnostic | 4096 | 5 |
| truncated | 4096 | 5 |

Main point N8192 (8704 total transitions), medians [IQR]; m2 is the separate zero-null baseline.

| m | null | Method | Absolute gap | Relative gap | True redundant D | Stable |
|---:|---:|---|---|---|---|---:|
| 2 | 0.0 | dense | 0.0300119 [0.00736011, 0.252226] | 0.0326465 [0.0182249, 0.0872799] | 4.91103e-32 [1.41809e-32, 3.82313e-31] | 32/32 |
| 2 | 0.0 | truncated | 0.0300119 [0.00736011, 0.252226] | 0.0326465 [0.0182249, 0.0872799] | 4.91103e-32 [1.41809e-32, 3.82313e-31] | 32/32 |
| 4 | 0.25 | dense | 0.0849942 [0.0140438, 0.524363] | 0.0527055 [0.0289979, 0.0913273] | 0.0203234 [0.00437856, 0.112986] | 32/32 |
| 4 | 0.25 | truncated | 0.0161701 [0.00693492, 0.37809] | 0.0233668 [0.0173793, 0.0608193] | 0.000206323 [6.4627e-05, 0.000501159] | 32/32 |
| 6 | 0.25 | dense | 0.126171 [0.0220008, 0.804865] | 0.0871868 [0.0559761, 0.117337] | 0.0362362 [0.0107834, 0.472862] | 32/32 |
| 6 | 0.25 | truncated | 0.0290698 [0.0081313, 0.246663] | 0.0284984 [0.0137307, 0.0439552] | 0.000765819 [0.000380846, 0.00241542] | 32/32 |
| 9 | 0.25 | dense | 0.301959 [0.0291294, 1.07292] | 0.114944 [0.084645, 0.16709] | 0.201007 [0.0183475, 0.60527] | 32/32 |
| 9 | 0.25 | truncated | 0.0387206 [0.0089688, 0.244399] | 0.0350257 [0.0231269, 0.0504642] | 0.00167342 [0.00067311, 0.00355259] | 32/32 |
| 12 | 0.25 | dense | 0.304646 [0.0352354, 1.51559] | 0.148547 [0.110961, 0.191503] | 0.24334 [0.0286246, 1.37086] | 32/32 |
| 12 | 0.25 | truncated | 0.0169401 [0.00797644, 0.387958] | 0.027116 [0.0171203, 0.0661781] | 0.00223803 [0.00115808, 0.00406302] | 32/32 |

Full zero-null control, both N, oracle diagnostic and system-bootstrap intervals are in the CSV tables. Only paired same-system/seed/budget comparisons are called gains; finite-pair intervals do not replace failure-inclusive statistics.

Independent saved-candidate check: 1664 candidate policies; maximum normalized discrepancy between gap identities 7.73e-14. 128 earlier X0 files plus the old experiment delivery remain unchanged; all178 protected older delivery files were byte-checked again.

Paths relative to this channel folder:

- `experiments/supplement-20261101/X1/report-ce/ce_main.png`
- `experiments/supplement-20261101/X1/report-ce/ce_main.svg`
- `experiments/supplement-20261101/X1/report-ce/ce_scaled_redundant_cost.png`
- `experiments/supplement-20261101/X1/report-ce/ce_scaled_redundant_cost.svg`
- `experiments/supplement-20261101/X1/report-ce/all_statistics.csv`
- `experiments/supplement-20261101/X1/report-ce/all_records.csv`
- `experiments/supplement-20261101/X1/report-ce/paired_ratios.csv`
- `experiments/supplement-20261101/X1/report-ce/system_bootstrap_effects.csv`
- `experiments/supplement-20261101/X1/report-ce/system_certificates.csv`
- `experiments/supplement-20261101/X1/report-ce/REPORT.json`

Source config/hash: `configs/X1_v1.json`, `release-manifest-X1-v1.json`; CE approval: `X1/ACCEPTED_CE.json`; report source: `report_ce.py`. Engine SHA256 `9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`, report SHA256 `20d052f19df24af17905b37b8ce62f841e910db7c44f802cf4f400d11941f63c`. Complete local delivery manifest: `X1/ce-delivery-manifest.json` (1196 files; includes original records and all candidate archives).

Interpretation limits: the finite N grid is not a budget-to-epsilon experiment; initial K0 geometry is disclosed (zero-null K0 is rank1 inside the true action subspace); the m=r baseline does not match the nonzero-null initial cost. Formal CE failures despite stable pilots are retained and do not numerically certify the theorem constants. No paper TeX or earlier result was changed.
