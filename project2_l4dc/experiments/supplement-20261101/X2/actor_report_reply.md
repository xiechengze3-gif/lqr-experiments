Scope: **X2 actor REPORT**, independent-policy audit complete; CE was reported separately.

128 formal endpoints; 0 failed endpoints retained. Independently checked30848 assessed candidates, including unstable candidates; max normalized gap identity discrepancy2.90308e-14. Zero hard numerical task failures and zero unequal-count attempts. Discarded failure-padding transitions total0, reported separately and never as recovery.

Medians [IQR], failed endpoints+infinity; stable counts denote stability, not epsilon attainment. X1 table is the matched nonzero-null family; zero-null control/all cells remain in the CSV.

| Algorithm | n | m | Method | Absolute gap | Relative gap | Stable |
|---|---:|---:|---|---|---|---:|
| NPG | 12 | 12 | dense | 0.476618 [0.203806, 1.25986] | 0.577006 [0.457203, 0.662122] | 32/32 |
| NPG | 12 | 12 | k2 | 0.466421 [0.320712, 1.11909] | 0.714912 [0.393105, 0.943949] | 32/32 |
| NPG | 24 | 24 | dense | 0.63259 [0.202318, 3.67821] | 0.14448 [0.130145, 0.193485] | 32/32 |
| NPG | 24 | 24 | k2 | 0.511644 [0.485414, 1.32349] | 0.150638 [0.0969659, 0.341567] | 32/32 |

Paired NPG dense/method gap ratios (median [system-bootstrap95% interval], all32 pairs finite):

| n | m | Ratio | 95% interval |
|---:|---:|---:|---|
| 12 | 12 | 0.785557 | [0.616955, 1.57406] |
| 24 | 24 | 1.23309 | [0.343015, 2.86094] |

Negative/mixed finding: n12 relative median is.577006 dense vs.714912 rank2; n24 is.144480 vs.150638. Paired ratios.785557[.616955,1.574063] and1.233094[.343015,2.860936] both include1. These data do NOT establish an NPG dimension-scaling gain. Absolute and relative marginal medians need not order methods identically because normalization is per system; only per-pair ratios, never ratios of medians, are called gains. Do not claim attained epsilon or replace this mixed result with a pilot.

Files under `X2/report-actors/`:

- `endpoint_statistics.csv`
- `all_endpoints.csv`
- `all_recorded_iterates.csv`
- `primitive_transition_counts.csv`
- `paired_ratios.csv`
- `paired_bootstrap_effects.csv`
- `system_certificates.csv`
- `REPORT.json`
- `npg_dimension_endpoints.png`
- `npg_dimension_endpoints.svg`

Exact source/config/approval hashes are in `X2/ACCEPTED_NPG.json` and its formal release manifest. Report source SHA256`55b04ff16d812ec9b08ef296d0ed392fca9f6ca34f961cfe8f826e12a8358fc6`; engine`9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`; source frozen in `packages/supplement-20261101-primary-actor-report-v21.manifest.json`. Both plots visually checked; PI count annotations need a cleaner follow-up view, without changing tables. Reports delivered/hash-verified via `deliveries/delivery-primary-actor-reports-v1.verified.json`. Full raw candidate delivery is separately packaged and being copied.

No theoretical sufficient sample constants were certified; pilot qualification only fixed an arm-independent practical schedule. All formal failures, weak effects and mixed outcomes remain. NPG is reported only as a relative endpoint comparison. No paper TeX or protected older file changed.
