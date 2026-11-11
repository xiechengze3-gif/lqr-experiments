Scope: **X3 CE-only pilot**; NPG is a separate calibrated branch.

Complete shared-data coverage: 24 continuous trajectories; 5184 evaluated outputs, 700 failed/unstable outputs retained. Failure-inclusive medians/IQR and all four-repeat stable counts are in `X3/pilot-ce-statistics.csv`; raw policies/fit archives and delivery hashes are local.

| Method | Failed / all tested outputs |
|---|---:|
| adaptive_paper | 40/432 |
| adaptive_split | 16/432 |
| dense | 18/432 |
| k0 | 432/432 |
| k1 | 78/432 |
| k12 | 18/432 |
| k16 | 7/216 |
| k2 | 23/432 |
| k24 | 7/216 |
| k3 | 12/432 |
| k4 | 14/432 |
| k6 | 17/432 |
| k8 | 18/432 |

At the largest regression prefix per case (medians [IQR]):

| n | rank / spectrum | Method | Absolute gap | Relative gap | Stable |
|---:|---|---|---|---|---:|
| 16 | flat | adaptive_paper | 0.0025273 [0.002451, 0.0026613] | 0.0012097 [0.0011854, 0.0012638] | 4/4 |
| 16 | flat | adaptive_split | 0.0025273 [0.002451, 0.0026613] | 0.0012097 [0.0011854, 0.0012638] | 4/4 |
| 16 | flat | dense | 0.0025273 [0.002451, 0.0026613] | 0.0012097 [0.0011854, 0.0012638] | 4/4 |
| 16 | gapped | adaptive_paper | 12.559 [0.13981, 34.118] | 0.4475 [0.23008, 0.90666] | 4/4 |
| 16 | gapped | adaptive_split | 1.0282 [0.048408, 12.475] | 0.072405 [0.050804, 0.36036] | 4/4 |
| 16 | gapped | dense | 0.88805 [0.025783, 5.6584] | 0.045843 [0.042429, 0.15037] | 4/4 |
| 16 | smooth | adaptive_paper | 0.08695 [0.025127, 0.16666] | 0.037926 [0.030012, 0.050194] | 4/4 |
| 16 | smooth | adaptive_split | 0.065819 [0.02479, 0.12825] | 0.03196 [0.028864, 0.039372] | 4/4 |
| 16 | smooth | dense | 0.038731 [0.021976, 0.083978] | 0.023534 [0.017584, 0.034996] | 4/4 |
| 32 | flat | adaptive_paper | 0.0051445 [0.0049963, 0.0053081] | 0.0012046 [0.001104, 0.0013342] | 4/4 |
| 32 | flat | adaptive_split | 0.0051445 [0.0049963, 0.0053081] | 0.0012046 [0.001104, 0.0013342] | 4/4 |
| 32 | flat | dense | 0.0051445 [0.0049963, 0.0053081] | 0.0012046 [0.001104, 0.0013342] | 4/4 |
| 32 | gapped | adaptive_paper | 1.5996 [0.33947, 2.8736] | 0.27175 [0.24276, 0.30113] | 4/4 |
| 32 | gapped | adaptive_split | 0.74504 [0.14688, 1.3496] | 0.1267 [0.10504, 0.14143] | 4/4 |
| 32 | gapped | dense | 0.26652 [0.060171, 0.52087] | 0.048338 [0.04303, 0.054583] | 4/4 |
| 32 | smooth | adaptive_paper | 0.13043 [0.036883, 0.23191] | 0.027617 [0.020255, 0.036187] | 4/4 |
| 32 | smooth | adaptive_split | 0.093862 [0.030435, 0.16856] | 0.02084 [0.016714, 0.026303] | 4/4 |
| 32 | smooth | dense | 0.11541 [0.063025, 0.17777] | 0.030357 [0.02469, 0.036282] | 4/4 |

Global C5=2.569143010355372 from432 dense-fit error diagnostics only; delta.05. Both adaptive variants reuse the24 captured trajectories and exact full/half OLS fits; adaptive postprocessing samples zero new transitions. Conservative paper-form threshold failures are retained; the constant is not tuned to adaptive policy performance.

The fixed-order pilot job completed36s for all24 trajectories, peak sampled RSS145192KiB. The formal32 bundles x2min x1core/2GiB bound1.066667SU leaves allowance for both adaptive solvers. Full-rank flat-spectrum results and k0 failures remain visible.

Resolved config `configs\X3_CE_resolved_v2.json`, SHA256 `99f60251f41ad2e1adcfc9b15f45e67f9d89335699d85fa5ef5f9d208a2ecfa1`; engine `9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`. **Formal remains blocked pending explicit X3 CE ACCEPTED**, not a60-minute timeout. NPG calibration does not reuse these CE outcomes.
