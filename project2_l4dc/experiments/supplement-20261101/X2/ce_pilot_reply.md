Scope: **X2 CE-only pilot**; NPG is a separate calibrated branch.

Complete shared-data coverage: 28 continuous trajectories; 1008 evaluated outputs, 96 failed/unstable outputs retained. Failure-inclusive medians/IQR and all four-repeat stable counts are in `X2/pilot-ce-statistics.csv`; raw policies/fit archives and delivery hashes are local.

| Method | Failed / all tested outputs |
|---|---:|
| dense | 67/504 |
| truncated | 29/504 |

At the largest regression prefix per case (medians [IQR]):

| n | rank / spectrum | Method | Absolute gap | Relative gap | Stable |
|---:|---|---|---|---|---:|
| 12 | 2 | dense | 0.071225 [0.025838, 0.1174] | 0.054269 [0.046575, 0.058544] | 4/4 |
| 12 | 2 | truncated | 0.018896 [0.0074752, 0.032034] | 0.015919 [0.010555, 0.019211] | 4/4 |
| 24 | 1 | dense | 2.0079 [0.023577, 12.865] | 0.085316 [0.060464, 0.34324] | 4/4 |
| 24 | 1 | truncated | 0.023429 [0.0017329, 4.3112] | 0.0044406 [0.0036261, 0.11746] | 4/4 |
| 24 | 2 | dense | 0.041568 [0.02333, 0.062113] | 0.043804 [0.038082, 0.048697] | 4/4 |
| 24 | 2 | truncated | 0.00305 [0.0027769, 0.0055319] | 0.0049821 [0.0039739, 0.0062264] | 4/4 |
| 24 | 4 | dense | 0.011296 [0.011265, 0.012386] | 0.021376 [0.02052, 0.022336] | 4/4 |
| 24 | 4 | truncated | 0.0031246 [0.0028507, 0.0034437] | 0.0055672 [0.0050996, 0.0060042] | 4/4 |
| 24 | 8 | dense | 0.0074646 [0.0070448, 0.0077852] | 0.0065174 [0.0062011, 0.0067453] | 4/4 |
| 24 | 8 | truncated | 0.0039688 [0.0038756, 0.0040232] | 0.0034935 [0.0033987, 0.0035272] | 4/4 |
| 48 | 2 | dense | 10.895 [8.4658, 13.11] | 0.27331 [0.22617, 0.30473] | 4/4 |
| 48 | 2 | truncated | 1.3556 [0.91843, 1.796] | 0.02864 [0.019487, 0.0439] | 4/4 |
| 96 | 2 | dense | 1.4972 [1.4269, 1.5647] | 0.095053 [0.090888, 0.1] | 4/4 |
| 96 | 2 | truncated | 0.068507 [0.054282, 0.073427] | 0.004398 [0.0034464, 0.0046671] | 4/4 |

Measured pilot: worst complete Slurm bundle37s, largest per-trajectory6.761331s, peak sampled MaxRSS148588KiB; single-core billing1. Formal request:32 bundles x2min x1core/2GiB=1.066667SU upper. The2min request exceeds1.3*37+30=78.1s. No CE hyperparameter is changed based on these outcomes.

Resolved config `configs\X2_v1.json`, SHA256 `1fc7046754e9bfebf7d10b7e6804ec48700cf142fcdb0155fd40bc2942532ba6`; engine `9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`. **Formal remains blocked pending explicit X2 CE ACCEPTED**, not a60-minute timeout. NPG calibration does not reuse these CE outcomes.
