Scope: **X4 optional offline diagnostic REPORT complete**, no retraining/observations.5760 evaluations;8 independent source systems x4 sampling seeds x10 fixed directions per algorithm/arm/magnitude;320 is the descriptive denominator, not320 independent systems.

| Algorithm | delta / ||B|| | Method | Gap median [IQR] | Stable | Inherited failed source | New instability | Stable K0 reference |
|---|---:|---|---|---:|---:|---:|---:|
| CE | 0.25 | dense | 1.8769 [0.400576, 9.25542] | 317/320 | 0 | 3 | 320/320 |
| CE | 0.5 | dense | 3.42616 [1.07252, 13.2742] | 315/320 | 0 | 5 | 320/320 |
| CE | 1.0 | dense | 4.94093 [2.11309, 17.3926] | 303/320 | 0 | 17 | 320/320 |
| CE | 0.25 | truncated | 1.82358 [0.391369, 7.61845] | 320/320 | 0 | 0 | 320/320 |
| CE | 0.5 | truncated | 3.91906 [1.08335, 11.4346] | 320/320 | 0 | 0 | 320/320 |
| CE | 1.0 | truncated | 6.0024 [2.10666, 13.9211] | 320/320 | 0 | 0 | 320/320 |
| NPG | 0.25 | dense | 2.30313 [0.509859, 9.41897] | 320/320 | 0 | 0 | 320/320 |
| NPG | 0.5 | dense | 4.3799 [1.22636, 13.48] | 319/320 | 0 | 1 | 320/320 |
| NPG | 1.0 | dense | 6.25278 [2.32192, 18.4792] | 312/320 | 0 | 8 | 320/320 |
| NPG | 0.25 | truncated | 1.97986 [0.538834, 8.30322] | 320/320 | 0 | 0 | 320/320 |
| NPG | 0.5 | truncated | 3.93928 [1.2755, 12.0047] | 320/320 | 0 | 0 | 320/320 |
| NPG | 1.0 | truncated | 5.83048 [2.3679, 15.2076] | 315/320 | 0 | 5 | 320/320 |
| PI | 0.25 | dense | 4.14639 [0.718604, inf] | 180/320 | 140 | 0 | 320/320 |
| PI | 0.5 | dense | 6.34304 [1.45335, inf] | 180/320 | 140 | 0 | 320/320 |
| PI | 1.0 | dense | 9.69794 [2.61632, inf] | 179/320 | 140 | 1 | 320/320 |
| PI | 0.25 | truncated | 1.97432 [0.414501, inf] | 199/320 | 120 | 1 | 320/320 |
| PI | 0.5 | truncated | 3.98597 [1.10074, inf] | 195/320 | 120 | 5 | 320/320 |
| PI | 1.0 | truncated | 5.76099 [2.15181, inf] | 194/320 | 120 | 6 | 320/320 |

Paired absolute-gap ratios, finite/full320 counts shown; bootstrap resamples8 whole systems, preserving all40 seed/direction observations per cluster:

| Algorithm | magnitude | Dense/truncated median [95% CI] | Finite pairs |
|---|---:|---|---:|
| CE | 0.25 | 1.14471 [1.11841, 1.17863] | 317/320 |
| CE | 0.5 | 1.07414 [1.04581, 1.1329] | 315/320 |
| CE | 1.0 | 1.04477 [1.01585, 1.09733] | 303/320 |
| NPG | 0.25 | 1.03563 [0.977385, 1.1051] | 320/320 |
| NPG | 0.5 | 1.01998 [0.99808, 1.08478] | 319/320 |
| NPG | 1.0 | 1.02392 [1.00762, 1.07777] | 308/320 |
| PI | 0.25 | 1.88141 [1.73974, 2.06966] | 180/320 |
| PI | 0.5 | 1.37044 [1.34351, 1.47714] | 180/320 |
| PI | 1.0 | 1.29744 [1.24417, 1.44167] | 179/320 |

Total832 failures =780 inherited source-output failures (26 intended PI endpoints repeated across30 perturbations each) +52 newly unstable evaluations. CE truncated remains320/320 stable at all magnitudes, while dense has some new instability; this does not imply universally lower perturbed cost, because the perturbed optimal problem changes. NPG and PI diagnostics are reported as measured; compare methods only within the same source algorithm/system/seed/direction/magnitude.

`X4/report/robustness_statistics.csv` includes both source-initial-gap normalization and the actual perturbed-K0 relative gap where defined, with the reference-defined count. Undefined K0 references are not learned-policy failures. Infinite PI upper IQRs stay infinite in tables; absence of a finite plotted band is not zero spread. `all_outputs.csv`, `paired_ratios.csv`, `paired_bootstrap_effects.csv`, `fixed_policy_robustness.png/.svg`, and `REPORT.json` provide all values/figure sources. Figure visually inspected.

All constraints pass: max null-product operator error6.59206e-16, norm error4.44089e-16, independent normalized gap error2.95299e-12. Config/core/approval: `X4/prepilot-source-manifest.json`,`X4/ACCEPTED.json`; source policies frozen in `X4/SOURCE_POLICY_MANIFEST.json`; report SHA256`8c5b700946acac21f24fbfbc1aa626a24abda2b56b801cc3435b5ed56f00c7d5`. Raw and report deliveries hash-verified locally; old178 files unchanged. This is a fixed-policy sensitivity diagnostic, not a new learning experiment or an epsilon claim.
