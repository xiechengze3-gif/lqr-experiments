# X6a REPORT v1 — estimation gains and the low-signal failure mechanism

All40 formal/calibration bundles and all320 fixed-gain paths are complete.
12800 observation rows,1920 Stein prefixes,1600 CE fits and3520 estimate-file
hashes passed the accepted Slurm REPORT. All formal cells have32/32 finite
fits. This is **fixed-gain estimation**, not a closed-loop performance experiment.

The new result supports the original diagnosis: rank2 compression lowers
Frobenius error, but when raw signal/noise is poor it can discard much of the
true signal. On S/n24/N2048, raw Z projection is0.9708+/-0.1256 versus
truncated0.1794+/-0.05855; sin(theta)=0.9961. At N524288, projection recovers
to1.0032+/-0.01007 versus0.9844+/-0.01279 and sin(theta)=0.3726.
These are means +/- system SE; errors/angles below use seed-then-system medians.

On S at their largest registered N, NPG paired error ratios are2.34/2.64/3.47/4.00
for n24/36/48/72; PI joint-compression ratios2.44/3.02/3.57/4.32. CE B-estimation
ratios at N524288 are2.46/3.04/3.57/4.26. Ratios are within-system/seed before
hierarchical aggregation; they are not ratios of marginal medians or cost gains.
Do not compare Stein block N with CE transition N as equal sample cost.

The unfiltered U family remains noisy even at the largest budgets: formal NPG
rho_op medians3.75/4.05/5.72/5.90, sin(theta)0.978/0.996/0.996/0.998, and
truncated projections0.453/0.252/0.211/0.161. Its smaller Frobenius errors alone
do not establish a good update direction. PSD-clipped PI and raw-PI are kept
separately; clipping can itself change signal projection. No variant is retuned.

## Largest registered budgets, all formal systems

Each bracket is IQR over8 system medians, after seed medians within each system.
PI uses [G+,Zhat] versus the exact actor_learner two-sided compressed pair.
All other budgets and raw-PI diagnostics remain in the source CSVs.

| Family | n | Estimator | N | Dense relative error [IQR] | Truncated [IQR] | Paired ratio [IQR] | Dense rho_op | Left sin(theta) | Finite/full |
|---|---:|---|---:|---|---|---|---:|---:|---|
| S | 24 | NPG | 524288 | 1.213 [1.166, 1.31] | 0.5297 [0.4918, 0.5785] | 2.336 [2.247, 2.382] | 0.7841 | 0.3726 | 32/32 |
| S | 24 | PI | 524288 | 0.6288 [0.6182, 0.6461] | 0.2606 [0.2513, 0.2617] | 2.442 [2.413, 2.603] | 0.3494 | 0.1604 | 32/32 |
| S | 24 | CE | 524288 | 0.02339 [0.02324, 0.02356] | 0.009611 [0.009348, 0.00994] | 2.465 [2.396, 2.517] | 0.01267 | 0.007533 | 32/32 |
| S | 36 | NPG | 524288 | 2.162 [2.132, 2.202] | 0.8042 [0.7872, 0.8379] | 2.635 [2.594, 2.726] | 1.063 | 0.5694 | 32/32 |
| S | 36 | PI | 524288 | 1.115 [1.073, 1.132] | 0.3712 [0.36, 0.3782] | 3.019 [2.925, 3.095] | 0.4939 | 0.24 | 32/32 |
| S | 36 | CE | 524288 | 0.03507 [0.03494, 0.03518] | 0.01144 [0.0114, 0.01169] | 3.036 [2.978, 3.071] | 0.0158 | 0.008992 | 32/32 |
| S | 48 | NPG | 4194304 | 1.212 [1.198, 1.242] | 0.3503 [0.3428, 0.364] | 3.469 [3.385, 3.501] | 0.5084 | 0.2611 | 32/32 |
| S | 48 | PI | 4194304 | 0.6071 [0.6, 0.6148] | 0.1724 [0.1694, 0.1732] | 3.568 [3.512, 3.626] | 0.2351 | 0.1093 | 32/32 |
| S | 48 | CE | 524288 | 0.04666 [0.0465, 0.047] | 0.01315 [0.01284, 0.01379] | 3.573 [3.393, 3.64] | 0.01856 | 0.01019 | 32/32 |
| S | 72 | NPG | 4194304 | 2.125 [2.038, 2.207] | 0.5248 [0.5042, 0.5509] | 3.995 [3.954, 4.064] | 0.7393 | 0.3645 | 32/32 |
| S | 72 | PI | 4194304 | 1.087 [1.069, 1.106] | 0.2553 [0.2487, 0.2611] | 4.319 [4.202, 4.335] | 0.3493 | 0.1631 | 32/32 |
| S | 72 | CE | 524288 | 0.07005 [0.06982, 0.07035] | 0.01642 [0.01626, 0.01658] | 4.255 [4.196, 4.302] | 0.02265 | 0.01237 | 32/32 |
| U | 24 | NPG | 524288 | 6.115 [2.767, 6.967] | 3.351 [1.5, 3.821] | 1.864 [1.796, 1.95] | 3.754 | 0.9778 | 32/32 |
| U | 24 | PI | 524288 | 2.695 [1.409, 3.128] | 1.4 [0.6081, 1.608] | 1.979 [1.912, 2.312] | 1.608 | 0.8527 | 32/32 |
| U | 24 | CE | 524288 | 0.02345 [0.02308, 0.02374] | 0.009178 [0.009054, 0.00943] | 2.534 [2.494, 2.575] | 0.01281 | 0.007042 | 32/32 |
| U | 36 | NPG | 524288 | 7.921 [6.114, 10.71] | 3.673 [2.808, 4.83] | 2.202 [2.171, 2.226] | 4.048 | 0.9957 | 32/32 |
| U | 36 | PI | 524288 | 3.377 [2.773, 4.828] | 1.424 [1.173, 2.129] | 2.33 [2.307, 2.384] | 1.727 | 0.8336 | 32/32 |
| U | 36 | CE | 524288 | 0.03502 [0.03494, 0.0352] | 0.01131 [0.01117, 0.01198] | 3.072 [2.995, 3.147] | 0.01576 | 0.008802 | 32/32 |
| U | 48 | NPG | 4194304 | 12.9 [8.331, 24.47] | 5.083 [3.364, 9.473] | 2.526 [2.495, 2.555] | 5.725 | 0.9959 | 32/32 |
| U | 48 | PI | 4194304 | 5.296 [3.384, 10.13] | 2.065 [1.216, 3.799] | 2.678 [2.616, 2.799] | 2.302 | 0.9575 | 32/32 |
| U | 48 | CE | 524288 | 0.04674 [0.04653, 0.04696] | 0.01342 [0.01323, 0.01367] | 3.509 [3.414, 3.557] | 0.01838 | 0.01029 | 32/32 |
| U | 72 | NPG | 4194304 | 16.02 [10.03, 37.45] | 5.234 [3.319, 12.03] | 3.06 [2.998, 3.101] | 5.902 | 0.9981 | 32/32 |
| U | 72 | PI | 4194304 | 7.156 [3.968, 14.7] | 2.272 [1.181, 4.555] | 3.271 [3.195, 3.365] | 2.52 | 0.9279 | 32/32 |
| U | 72 | CE | 524288 | 0.07035 [0.07021, 0.07049] | 0.01619 [0.01593, 0.01641] | 4.343 [4.27, 4.435] | 0.02305 | 0.0121 | 32/32 |

## Pilot-only calibration, dense estimate only

The criterion is median over2 pilot-system seed medians of rho_op<=1.
It is an empirical precision threshold, not all theorem hypotheses. Separate
raw/clipped PI thresholds are not silently used as the common NPG actor base.

| Family | n | NPG smallest N | Raw PI smallest N | Clipped PI smallest N |
|---|---:|---:|---:|---:|
| S | 24 | 524288 | 131072 | 131072 |
| S | 36 | >524288 | 524288 | 524288 |
| S | 48 | 2097152 | 524288 | 524288 |
| S | 72 | 4194304 | 2097152 | 524288 |
| U | 24 | >524288 | >524288 | >524288 |
| U | 36 | >524288 | >524288 | >524288 |
| U | 48 | >4194304 | >4194304 | >4194304 |
| U | 72 | >4194304 | >4194304 | >4194304 |

**S/n36 NPG is right-censored above524288.** It has no valid calibrated base
in the frozen grid. Do not substitute its formal median, use the PI base, or
extrapolate a qualifying N. All U pilot calibration is right-censored as well.
X6b requires a reviewer-approved S/n36 pilot-grid extension; X6c additionally
needs the approved P0<=15 pilot-selection rule, which may select different U IDs.

## Reproduction and evidence

- CSVs: ../deliveries/report-20365069-v4/X6a/reports/v1/{observations,
  system_summaries,summary,calibration,certificates}.csv.
- Figures: ../figures-v2,12 plots/24PNG+SVG; manifest has source and CSV hashes.
  ../plot_saved_v2.py is CSV-only. v1 is preserved; v2 only widens panels and
  uses power-of-two ticks after visual inspection found overlapping labels.
  No numerical summary, filtering, or scientific method changed.
- All4897 formal-delivery files and64 report-delivery files were SHA-verified
  after transfer; resource delivery adds29 files. Separate snapshots preserve
  overlaps in logs/accounting instead of overwriting historical files.
- Source/config/code are in the immutable formal/report package manifests.
  Accepted analysis SHA0962905f641e9f75eb16f16c47fcfb160c73614234c23cc269db21c9ebaa0cda.
  Exact PI processing comparison maximum relative difference2.22092e-13.
- Resource20364669, formal20364803, report20365069; report84seconds,
  zero additional simulated transitions. Primitive count18287459840 for
  formal collection counts nested prefixes once and includes burn/baseline.

## Interpretation for manuscript and next experiment

These plots are suitable as a mechanism figure or appendix evidence. They show
why a lower total estimator error can coexist with severe signal attenuation
at practical low budgets. They do not alone prove a terminal-cost improvement,
epsilon attainment, universal NPG superiority or a theorem counterexample.
At exact rank2 there is no true discarded spectral tail in Z; nonlinear noisy
rank truncation is distinct from structural full-rank tail bias. The bitwise
check validates agreement with the frozen collector, not every theorem constant.
Keep the U negative result and S/n36 calibration censoring visible.

Next: propose X6b with S bases524288 / PENDING /2097152 /4194304, common eta0.2,
the registered population R2 rule for T, and rungs1/16,1/4,1. A small separate
pilot-only S/n36 extension and explicit approval are needed before resolving it.
No actor learning or X6c selection/calibration was started in this report.

X6 requested upper 16.333333333/400SU; Slurm elapsed 9.542777778SU; AMS settled 8.408333333SU (overlapping views; do not add).
