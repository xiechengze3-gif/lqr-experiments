Scope: **X1 actor REPORT**, independent-policy audit complete; CE was reported separately.

1152 formal endpoints; 193 failed endpoints retained. Independently checked59952 assessed candidates, including unstable candidates; max normalized gap identity discrepancy7.22148e-12. Zero hard numerical task failures and zero unequal-count attempts. Discarded failure-padding transitions total16,202,723,744, reported separately and never as recovery.

Medians [IQR], failed endpoints+infinity; stable counts denote stability, not epsilon attainment. X1 table is the matched nonzero-null family; zero-null control/all cells remain in the CSV.

| Algorithm | n | m | Method | Absolute gap | Relative gap | Stable |
|---|---:|---:|---|---|---|---:|
| NPG | 12 | 4 | dense | 0.194582 [0.0432596, 0.716114] | 0.117573 [0.0985676, 0.144752] | 32/32 |
| NPG | 12 | 4 | truncated | 0.160712 [0.0549265, 0.547863] | 0.113788 [0.0793947, 0.168444] | 32/32 |
| NPG | 12 | 6 | dense | 0.251078 [0.0568425, 1.24588] | 0.167839 [0.145433, 0.182567] | 32/32 |
| NPG | 12 | 6 | truncated | 0.195228 [0.0741783, 0.955] | 0.142323 [0.110638, 0.227649] | 32/32 |
| NPG | 12 | 9 | dense | 0.313144 [0.0953353, 1.72293] | 0.255331 [0.203609, 0.311433] | 32/32 |
| NPG | 12 | 9 | truncated | 0.265441 [0.115834, 1.02266] | 0.207008 [0.146358, 0.30806] | 32/32 |
| NPG | 12 | 12 | dense | 0.55023 [0.110176, 2.18727] | 0.308511 [0.290176, 0.371864] | 32/32 |
| NPG | 12 | 12 | truncated | 0.343368 [0.128148, 1.0555] | 0.283915 [0.157688, 0.380746] | 32/32 |
| PI | 12 | 4 | dense | 0.498665 [0.106801, inf] | 0.352041 [0.274479, inf] | 20/32 |
| PI | 12 | 4 | truncated | 0.201595 [0.0316174, 1.12634] | 0.110045 [0.0840283, 0.157228] | 26/32 |
| PI | 12 | 6 | dense | 0.784265 [0.159295, inf] | 0.555386 [0.403438, inf] | 20/32 |
| PI | 12 | 6 | truncated | 0.204569 [0.038516, 7.21165] | 0.118038 [0.0899463, 1.00935] | 25/32 |
| PI | 12 | 9 | dense | 2.02143 [0.232092, inf] | 0.909447 [0.721235, inf] | 17/32 |
| PI | 12 | 9 | truncated | 0.199406 [0.0332247, inf] | 0.112015 [0.0978752, inf] | 23/32 |
| PI | 12 | 12 | dense | 2.47637 [0.341481, inf] | 1.19216 [0.987457, inf] | 18/32 |
| PI | 12 | 12 | truncated | 0.263353 [0.0350625, inf] | 0.142241 [0.101869, inf] | 20/32 |

Paired NPG dense/method gap ratios (median [system-bootstrap95% interval], all32 pairs finite):

| n | m | Ratio | 95% interval |
|---:|---:|---:|---|
| 12 | 4 | 1.05295 | [0.858574, 1.26191] |
| 12 | 6 | 1.12595 | [0.791061, 1.37503] |
| 12 | 9 | 1.19985 | [0.859385, 1.55521] |
| 12 | 12 | 1.43653 | [0.881988, 1.77237] |

Critical negative result: PI fails116/288 dense endpoints and77/288 truncated endpoints across both initialization families; all1,297 failed PI iterates remain. Nonzero-null family alone has53/128 dense and34/128 truncated failures. This is a finite-budget stability limitation, not a uniformly stable accuracy experiment. PI belongs in diagnostic/supplementary discussion; no rerun or hyperparameter retuning occurred. NPG both arms are stable on all288 trajectories, but every displayed NPG ratio CI includes1, so this experiment does NOT establish a clear truncation advantage for NPG.

Files under `X1/report-actors/`:

- `endpoint_statistics.csv`
- `all_endpoints.csv`
- `all_recorded_iterates.csv`
- `primitive_transition_counts.csv`
- `paired_ratios.csv`
- `paired_bootstrap_effects.csv`
- `system_certificates.csv`
- `REPORT.json`
- `actor_null25.png`
- `actor_null25.svg`
- `actor_null0.png`
- `actor_null0.svg`

Exact source/config/approval hashes are in `X1/ACCEPTED_ACTOR.json` and its formal release manifest. Report source SHA256`55b04ff16d812ec9b08ef296d0ed392fca9f6ca34f961cfe8f826e12a8358fc6`; engine`9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`; source frozen in `packages/supplement-20261101-primary-actor-report-v21.manifest.json`. Both plots visually checked; PI count annotations need a cleaner follow-up view, without changing tables. Reports delivered/hash-verified via `deliveries/delivery-primary-actor-reports-v1.verified.json`. Full raw candidate delivery is separately packaged and being copied.

No theoretical sufficient sample constants were certified; pilot qualification only fixed an arm-independent practical schedule. All formal failures, weak effects and mixed outcomes remain. NPG is reported only as a relative endpoint comparison. No paper TeX or protected older file changed.
