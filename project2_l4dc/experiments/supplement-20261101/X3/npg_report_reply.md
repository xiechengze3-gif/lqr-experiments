Scope: **X3 NPG REPORT complete**, all planned1440 trajectories; independent numerical report job20359906. No new sampled learning runs or transitions.

The source coverage proof verifies32 bundles/288 multi-runs. Numerical evaluation independently checked 93600 saved candidate policies; max normalized direct-cost/gap identity discrepancy 1.2652e-14. Endpoint failures 0/1440; hard-failure attempts 0; unequal actual counts 0; discarded K0 padding transitions 0. All failures remain+inf; no stable-subset replacement of medians.

All endpoint medians [q25,q75], each cell32 planned runs. M includes every burn/baseline/padding transition:

| Spectrum | batch mult | M | k | Stable/full | Absolute gap | Relative gap |
|---|---:|---:|---:|---|---|---|
| flat | 1 | 88,850,304 | 1 | 32/32 | 0.86787 [0.788906, 0.960243] | 0.565882 [0.553909, 0.583123] |
| flat | 1 | 88,850,304 | 2 | 32/32 | 0.469667 [0.41981, 0.523527] | 0.306608 [0.294181, 0.317051] |
| flat | 1 | 88,850,304 | 4 | 32/32 | 0.162334 [0.143009, 0.188912] | 0.104652 [0.100807, 0.112788] |
| flat | 1 | 88,850,304 | 6 | 32/32 | 0.0661358 [0.0597744, 0.0764071] | 0.0439565 [0.041427, 0.0473599] |
| flat | 1 | 88,850,304 | 12 | 32/32 | 0.0272268 [0.0260259, 0.0290593] | 0.0174973 [0.0167792, 0.0189114] |
| flat | 4 | 355,296,768 | 1 | 32/32 | 0.979857 [0.901134, 1.07386] | 0.637077 [0.632903, 0.658651] |
| flat | 4 | 355,296,768 | 2 | 32/32 | 0.572675 [0.501418, 0.641118] | 0.375389 [0.35587, 0.388424] |
| flat | 4 | 355,296,768 | 4 | 32/32 | 0.230078 [0.191939, 0.262803] | 0.148615 [0.138217, 0.159182] |
| flat | 4 | 355,296,768 | 6 | 32/32 | 0.0968611 [0.0768969, 0.11039] | 0.0622415 [0.0558391, 0.0670933] |
| flat | 4 | 355,296,768 | 12 | 32/32 | 0.0179887 [0.0164225, 0.020349] | 0.0119716 [0.0110672, 0.0123351] |
| flat | 16 | 1,421,082,624 | 1 | 32/32 | 1.05726 [0.969879, 1.16088] | 0.688263 [0.68062, 0.712227] |
| flat | 16 | 1,421,082,624 | 2 | 32/32 | 0.648752 [0.565713, 0.726427] | 0.42273 [0.401402, 0.439826] |
| flat | 16 | 1,421,082,624 | 4 | 32/32 | 0.301147 [0.249099, 0.339132] | 0.191656 [0.180827, 0.204483] |
| flat | 16 | 1,421,082,624 | 6 | 32/32 | 0.142186 [0.11284, 0.160841] | 0.0901778 [0.0836059, 0.0966437] |
| flat | 16 | 1,421,082,624 | 12 | 32/32 | 0.0152495 [0.0145224, 0.0173572] | 0.0102652 [0.00998695, 0.0106571] |
| gapped | 1 | 88,850,304 | 1 | 32/32 | 0.273472 [0.200397, 0.778243] | 0.365943 [0.154005, 0.548201] |
| gapped | 1 | 88,850,304 | 2 | 32/32 | 0.174105 [0.123704, 0.6377] | 0.236466 [0.163351, 0.328613] |
| gapped | 1 | 88,850,304 | 4 | 32/32 | 0.130425 [0.100548, 0.69807] | 0.192404 [0.16015, 0.228686] |
| gapped | 1 | 88,850,304 | 6 | 32/32 | 0.133825 [0.0911657, 0.813696] | 0.187081 [0.17438, 0.213205] |
| gapped | 1 | 88,850,304 | 12 | 32/32 | 0.14063 [0.0917906, 0.843982] | 0.193997 [0.171061, 0.211511] |
| gapped | 4 | 355,296,768 | 1 | 32/32 | 0.132471 [0.107944, 0.54362] | 0.163426 [0.128947, 0.299682] |
| gapped | 4 | 355,296,768 | 2 | 32/32 | 0.0724284 [0.0513179, 0.478499] | 0.106026 [0.0972645, 0.137095] |
| gapped | 4 | 355,296,768 | 4 | 32/32 | 0.0550536 [0.0319407, 0.407223] | 0.0883782 [0.0750341, 0.100653] |
| gapped | 4 | 355,296,768 | 6 | 32/32 | 0.0483958 [0.0296731, 0.381838] | 0.0781886 [0.066466, 0.0897094] |
| gapped | 4 | 355,296,768 | 12 | 32/32 | 0.044748 [0.0261149, 0.35784] | 0.0681245 [0.0628172, 0.0846826] |
| gapped | 16 | 1,421,082,624 | 1 | 32/32 | 0.133431 [0.116645, 0.506018] | 0.165531 [0.118748, 0.322028] |
| gapped | 16 | 1,421,082,624 | 2 | 32/32 | 0.048046 [0.0299985, 0.400905] | 0.0825814 [0.0647456, 0.0923682] |
| gapped | 16 | 1,421,082,624 | 4 | 32/32 | 0.034559 [0.019807, 0.311401] | 0.0557967 [0.0504911, 0.0765969] |
| gapped | 16 | 1,421,082,624 | 6 | 32/32 | 0.0280409 [0.0164872, 0.26723] | 0.0459831 [0.0393804, 0.0601205] |
| gapped | 16 | 1,421,082,624 | 12 | 32/32 | 0.0227179 [0.0130281, 0.213193] | 0.0380491 [0.0317507, 0.0464264] |
| smooth | 1 | 88,850,304 | 1 | 32/32 | 0.439163 [0.272996, 0.593752] | 0.455813 [0.230451, 0.585775] |
| smooth | 1 | 88,850,304 | 2 | 32/32 | 0.272583 [0.17764, 0.429525] | 0.289139 [0.149051, 0.354065] |
| smooth | 1 | 88,850,304 | 4 | 32/32 | 0.169285 [0.102067, 0.292786] | 0.17803 [0.120404, 0.213853] |
| smooth | 1 | 88,850,304 | 6 | 32/32 | 0.136563 [0.0802272, 0.268166] | 0.152873 [0.119395, 0.177572] |
| smooth | 1 | 88,850,304 | 12 | 32/32 | 0.128547 [0.0721768, 0.287546] | 0.149681 [0.117201, 0.159243] |
| smooth | 4 | 355,296,768 | 1 | 32/32 | 0.278538 [0.231128, 0.438864] | 0.289815 [0.16969, 0.410823] |
| smooth | 4 | 355,296,768 | 2 | 32/32 | 0.158679 [0.127714, 0.286267] | 0.167837 [0.103476, 0.236017] |
| smooth | 4 | 355,296,768 | 4 | 32/32 | 0.0898456 [0.0622897, 0.191276] | 0.106782 [0.0815407, 0.118327] |
| smooth | 4 | 355,296,768 | 6 | 32/32 | 0.0632546 [0.0422949, 0.182967] | 0.0796372 [0.0655827, 0.097007] |
| smooth | 4 | 355,296,768 | 12 | 32/32 | 0.0530285 [0.0332208, 0.180611] | 0.071684 [0.0548404, 0.0842208] |
| smooth | 16 | 1,421,082,624 | 1 | 32/32 | 0.28469 [0.235898, 0.493571] | 0.292358 [0.185972, 0.436448] |
| smooth | 16 | 1,421,082,624 | 2 | 32/32 | 0.130517 [0.115347, 0.275793] | 0.144813 [0.109057, 0.213872] |
| smooth | 16 | 1,421,082,624 | 4 | 32/32 | 0.064828 [0.0498585, 0.175253] | 0.0854082 [0.0694559, 0.102939] |
| smooth | 16 | 1,421,082,624 | 6 | 32/32 | 0.0455635 [0.0324435, 0.152779] | 0.0619864 [0.0518321, 0.0781682] |
| smooth | 16 | 1,421,082,624 | 12 | 32/32 | 0.0365131 [0.0253893, 0.138857] | 0.0486399 [0.0407984, 0.0617034] |

Paired dense/method gap ratios, finite/full pairs and system-cluster bootstrap95% (2,000 draws, seed2026110399). The same per-pair initial-gap normalization cancels, so relative-gap ratios coincide:

| Spectrum | batch mult | k | Finite/full | Paired ratio | 95% CI |
|---|---:|---:|---|---:|---|
| flat | 1 | 1 | 32/32 | 0.0316056 | [0.0294176, 0.0333168] |
| flat | 1 | 2 | 32/32 | 0.0577135 | [0.0540883, 0.0620109] |
| flat | 1 | 4 | 32/32 | 0.163615 | [0.154947, 0.181809] |
| flat | 1 | 6 | 32/32 | 0.402145 | [0.367823, 0.433943] |
| flat | 4 | 1 | 32/32 | 0.0185072 | [0.0183415, 0.0189029] |
| flat | 4 | 2 | 32/32 | 0.0316977 | [0.0306655, 0.0324359] |
| flat | 4 | 4 | 32/32 | 0.0799148 | [0.0773026, 0.0848216] |
| flat | 4 | 6 | 32/32 | 0.190387 | [0.181871, 0.214447] |
| flat | 16 | 1 | 32/32 | 0.014924 | [0.0143034, 0.015332] |
| flat | 16 | 2 | 32/32 | 0.0248153 | [0.0231761, 0.0256494] |
| flat | 16 | 4 | 32/32 | 0.0535623 | [0.0502042, 0.0575318] |
| flat | 16 | 6 | 32/32 | 0.113689 | [0.106064, 0.127977] |
| gapped | 1 | 1 | 32/32 | 0.5814 | [0.397158, 1.11781] |
| gapped | 1 | 2 | 32/32 | 0.829825 | [0.692967, 1.09804] |
| gapped | 1 | 4 | 32/32 | 1.02154 | [0.942661, 1.14822] |
| gapped | 1 | 6 | 32/32 | 1.0318 | [0.994947, 1.05637] |
| gapped | 4 | 1 | 32/32 | 0.388354 | [0.247758, 0.65954] |
| gapped | 4 | 2 | 32/32 | 0.586978 | [0.550807, 0.78626] |
| gapped | 4 | 4 | 32/32 | 0.835887 | [0.785051, 0.906834] |
| gapped | 4 | 6 | 32/32 | 0.944933 | [0.917004, 0.983458] |
| gapped | 16 | 1 | 32/32 | 0.192477 | [0.110735, 0.397846] |
| gapped | 16 | 2 | 32/32 | 0.443481 | [0.417849, 0.607949] |
| gapped | 16 | 4 | 32/32 | 0.656997 | [0.593956, 0.723391] |
| gapped | 16 | 6 | 32/32 | 0.807786 | [0.780812, 0.845785] |
| smooth | 1 | 1 | 32/32 | 0.285085 | [0.255854, 0.665567] |
| smooth | 1 | 2 | 32/32 | 0.469755 | [0.42623, 0.902458] |
| smooth | 1 | 4 | 32/32 | 0.768842 | [0.70931, 0.932886] |
| smooth | 1 | 6 | 32/32 | 0.949276 | [0.865316, 1.07085] |
| smooth | 4 | 1 | 32/32 | 0.209927 | [0.161822, 0.669997] |
| smooth | 4 | 2 | 32/32 | 0.357493 | [0.281781, 0.840999] |
| smooth | 4 | 4 | 32/32 | 0.633356 | [0.543022, 0.982239] |
| smooth | 4 | 6 | 32/32 | 0.846622 | [0.796129, 0.977645] |
| smooth | 16 | 1 | 32/32 | 0.136662 | [0.111447, 0.514505] |
| smooth | 16 | 2 | 32/32 | 0.28311 | [0.234757, 0.660482] |
| smooth | 16 | 4 | 32/32 | 0.554212 | [0.508676, 0.822659] |
| smooth | 16 | 6 | 32/32 | 0.806859 | [0.780778, 0.929657] |

Fixed-order group-median envelope (post-hoc diagnostic only, not online adaptive NPG):

| Spectrum | batch mult | Best k by absolute-gap median | Stable/full | Envelope gap [IQR] |
|---|---:|---:|---|---|
| smooth | 1 | 12 | 32/32 | 0.128547 [0.0721768, 0.287546] |
| smooth | 4 | 12 | 32/32 | 0.0530285 [0.0332208, 0.180611] |
| smooth | 16 | 12 | 32/32 | 0.0365131 [0.0253893, 0.138857] |
| gapped | 1 | 4 | 32/32 | 0.130425 [0.100548, 0.69807] |
| gapped | 4 | 12 | 32/32 | 0.044748 [0.0261149, 0.35784] |
| gapped | 16 | 12 | 32/32 | 0.0227179 [0.0130281, 0.213193] |
| flat | 1 | 12 | 32/32 | 0.0272268 [0.0260259, 0.0290593] |
| flat | 4 | 12 | 32/32 | 0.0179887 [0.0164225, 0.020349] |
| flat | 16 | 12 | 32/32 | 0.0152495 [0.0145224, 0.0173572] |

Review04:35 mechanism: actual last update gives S_k=(K63-K64)/eta-RK63. The target is Z_K=-B^T P_K(A-BK) at that arm's actual K63. Raw Zhat of truncated arms was not saved and is not claimed recovered. The separate common-dense-policy/raw-estimate branch applies each rank offline to dense's recovered Zhat; it creates no alternative endpoint or training run. No top-2 redundant-cost identity is used for full-rank B.

Two-level last Frobenius errors, median [IQR]; own-arm versus common dense policy/estimate, available/full counts explicitly:

| mult | k | Own-arm available | Own-arm ||S_k-Z_K||F | Common-dense available | Common-fit ||T_k(Zhat)-Z_K||F |
|---:|---:|---|---|---|---|
| 1 | 1 | 32/32 | 1.44705 [0.958171, 3.06105] | 32/32 | 1.24155 [0.865287, 2.78716] |
| 1 | 2 | 32/32 | 1.70801 [1.25678, 3.67383] | 32/32 | 1.55337 [1.16589, 3.58594] |
| 1 | 4 | 32/32 | 1.93267 [1.5281, 4.45714] | 32/32 | 1.86211 [1.47354, 4.38021] |
| 1 | 6 | 32/32 | 2.07346 [1.59951, 4.87374] | 32/32 | 2.04532 [1.57807, 4.82004] |
| 1 | 12 | 32/32 | 2.1414 [1.66799, 5.08598] | 32/32 | 2.1414 [1.66799, 5.08598] |
| 4 | 1 | 32/32 | 0.65277 [0.551923, 1.4787] | 32/32 | 0.555368 [0.40817, 1.42105] |
| 4 | 2 | 32/32 | 0.740596 [0.586487, 1.87355] | 32/32 | 0.723071 [0.581685, 1.76426] |
| 4 | 4 | 32/32 | 0.976747 [0.706948, 2.2159] | 32/32 | 0.964332 [0.703299, 2.14831] |
| 4 | 6 | 32/32 | 1.05135 [0.785765, 2.36442] | 32/32 | 1.04648 [0.781672, 2.3305] |
| 4 | 12 | 32/32 | 1.10263 [0.82895, 2.43313] | 32/32 | 1.10263 [0.82895, 2.43313] |
| 16 | 1 | 32/32 | 0.508329 [0.48271, 0.731336] | 32/32 | 0.351736 [0.282404, 0.596971] |
| 16 | 2 | 32/32 | 0.376743 [0.242815, 0.845182] | 32/32 | 0.378781 [0.244268, 0.818913] |
| 16 | 4 | 32/32 | 0.467026 [0.339073, 1.05926] | 32/32 | 0.465396 [0.338315, 1.04486] |
| 16 | 6 | 32/32 | 0.503982 [0.385783, 1.16147] | 32/32 | 0.502861 [0.385253, 1.15482] |
| 16 | 12 | 32/32 | 0.532519 [0.400431, 1.21342] | 32/32 | 0.532519 [0.400431, 1.21342] |

Saved-gain mechanism checks: 1440/1440 actual final updates available; max recovered rank residual 4.79748e-15; update reconstruction residual 1.5606e-18; synthetic recovery error 1.64944e-14. All spectra/normalized errors/true current-target rank-k tails and error-ratio bootstrap are in the accompanying CSV. Frobenius errors include finite-H bias, sampling and truncation effects; they do not alone certify a theorem small-error constant.

Files: `X3/report-actors/endpoint_statistics.csv`, `all_endpoints.csv`, `all_recorded_iterates.csv`, `paired_bootstrap_effects.csv`, `primitive_transition_counts.csv`, `system_certificates.csv`; `report-actors-order-envelope-v2/fixed_order_median_envelope.csv`, `true_B_spectral_tails.csv`, `fixed_order_iqr_gap.png/.svg`, `fixed_order_iqr_relative_gap.png/.svg`, `best_fixed_order.png/.svg`; `report-npg-last-estimator-v1/last_stage_per_output.csv`, `last_estimator_statistics.csv`, `paired_last_error_bootstrap.csv`, `recovered_effective_estimates_and_targets.npz`, two `last_error_*.png/.svg`, `two_level_endpoint_gaps.png/.svg`. Corresponding CSV are the figure numerical sources. First-failure and each-update counts are in new `report-npg-failure-detail-v3/`.

Full raw288 JSON+288 candidate NPZ and32 bundle receipts, proof and reports were delivered with archive/per-file hashes; local source files were never overwritten with differing bytes. Figures were visually inspected before this REPORT append. Formal config SHA256 `09205402ffb4dcb420d0289197056ec0934477ef353a41841948cf88f208b78d`; report package/source/config hashes in `packages/supplement-20261101-x3-actor-report-v28.manifest.json`; exact data-source hashes in all three `REPORT.json` files.

NPG conclusions are fixed-budget empirical comparisons only. No epsilon attainment, success-probability theorem, fitted dimension law or monotone-order law is claimed. True-B tau/beta tables are B-spectrum diagnostics, not every current Z_K tail; the last-stage mechanism tables separately evaluate the actual current Z_K. No adaptive NPG was run. All practical/theorem-regime limitations and negative cells are retained. Optional n48 remains deferred as accepted; no additional experiment was added.

Final interpretation and selection implications, based on the complete formal grid:

- **No clear total-gap advantage for truncated NPG in this grid.** Among36 predeclared
  dense/k gap comparisons,31 bootstrap95% intervals lie wholly below1,5 include1,
  and none lies wholly above1. All pairs are finite32/32; this result is not caused
  by excluding unstable paths. Smooth and flat spectra select dense k12 at every
  budget by the absolute-gap median. The flat control strongly penalizes truncation.
- **The two-level spectrum gives only a weak low-budget tradeoff.** Its absolute-gap
  envelope is k4 -> k12 -> k12; the relative-gap envelope is k6 -> k12 -> k12.
  At multiplier1, the k4 absolute median is.130425 versus dense.140630, but the
  paired ratio1.02154 [.942661,1.14822] does not establish an advantage. At the
  higher budgets all four truncated-arm gap-ratio intervals lie below1.
  Do not write a universal increasing-order law: smooth and flat are constant12.
- **The requested last-stage diagnostic improves while endpoint cost can worsen.**
  On the two-level spectrum, k2 own-arm last Frobenius-error medians are
  1.70801 /.740596 /.376743 versus dense2.14140 /1.10263 /.532519.
  The own-arm paired error ratios1.34675 /1.39405 /1.50404 all have CIs above1.
  At the same dense policy and raw estimate, offline k2 error ratios are
  1.40634 [1.37403,1.44274],1.46098 [1.38465,1.51105],
  1.52297 [1.47541,1.54158], also favoring truncation.
  Nevertheless actual endpoint dense/k2 gap ratios are
  .829825 [.692967,1.09804],.586978 [.550807,.786260],
  .443481 [.417849,.607949]. Lower last-stage unweighted Frobenius error alone
  therefore does not imply lower terminal control cost.

These are full-rank plants with nonzero discarded directions. Truncation bias,
policy-dependent targets, cost weighting and the entire optimization history can
all matter. This diagnostic does not isolate their causal contributions or certify
the theorem's sufficient small-error constants. It does not establish that poor
estimated-subspace alignment is the unique cause. Own-arm estimates belong to
different actual K63; the common-dense-policy branch is the comparison with a
shared policy and shared raw estimate, and has no counterfactual endpoint.

For manuscript selection, keep the NPG result as a negative/control and mechanism
result, or explicitly describe it that way in the main text. It is unsuitable as
positive evidence of a general total-gap or sample-complexity gain from truncation.
CE remains the stronger main positive evidence. Preserve the weak low-budget cell,
flat-spectrum control, all failure denominators and all36 intervals. Do not tune
eta, T, budgets or ranks after seeing this result; no additional experiment was run.

