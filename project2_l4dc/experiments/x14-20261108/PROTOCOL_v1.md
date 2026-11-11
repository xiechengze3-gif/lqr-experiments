## X14 GO: fill-in experiments, new ruling (08:28Z 11/08)

The user asked Claude in chat (2026-11-08) to have every supplementary experiment run that
fills a gap in the paper's experiments. This section is the new ruling that the X12 entry
("Do not submit new jobs without a new ruling here") requires. The paper stays read only.

Rules, unchanged: F1-F9 above; new folder `experiments/x14-20261108/` for everything; never
modify, move or delete any existing file on E, home or Grace scratch (no cleanup of any
kind); no edits under `C:\Users\24375\Projects\project2_l4dc` (tex, figs, data); no git, no
Overleaf. Reply by appending `## X14<letter> <stage>` sections to `CODEX_REPLY.md`, each
ending `STATUS: <stage> DONE X14<letter>`, with running spend in every reply.

### Pre-registration (fixed now, before any X14 numerical work)
Copy this X14 section verbatim into `x14-20261108/PROTOCOL_v1.md`, add the config and
source hashes, and do this before any X14 compute. Nothing in it changes after results.

### X14a  alpha = 0.02 in the X9 tail sweep (priority 1)
Purpose: with sigma_1 = sigma_2 = 1 and sigma_3..sigma_24 = 0.02, tau_2^2 = 22*0.02^2 = 0.0088
<= 0.01, so B is full rank and k_eps(B) = 2 at the target eps = 0.01 of Figure 1. This is the
regime of Corollary 4 with k = k_eps(B) = 2. The smallest positive X9 tail, alpha = 0.05, has
tau_2^2 = 0.055 > eps. The cell is reported whatever the outcome.
- Everything identical to X9 (`x9-20261106/PROTOCOL_v1.md`, frozen config ff3f89cb...,
  frozen_engine 9915fc38..., estimation f587bd48..., actor_paths 905ebe81..., x9_core
  e62b82f5..., analyze_x9 7eafc31a...): family S, n = m = 24, Q = R = W = I, K0 = 0,
  eta = 0.2, nu = 1, H = 16, 16 pulse burn blocks + 1 baseline block per stage, NPG 16
  stages, PI 8 stages (v4), systems 301-308 x seeds 1701-1704,
  B = B_X6b + alpha U_tail V_tail^T, truncated arm k = 2, N_cal = 524288 blocks.
- The ONLY change is alpha = 0.02 (tau2_sq = 0.0088). Same RNG keys as X9, with nothing added
  to the keys, so the alpha = 0.02 paths share common random numbers with the other alphas
  exactly as the X9 paths do. Same bootstrap: 5000 system-cluster resamples, the X6b tag,
  common draws across alpha, rungs and ratio kinds per algorithm.
- Budgets: all nine rungs N_cal/2^j, j = 0..8 (the four X9 rungs and the five X10b rungs),
  both algorithms, both arms, identical primitive counts per arm (F1).
- Registered readout: for every rung, dense and truncated gap and relative gap medians/IQR,
  stable counts out of 32, both-stable and failure-inclusive paired ratio dense/truncated
  with 95% interval. Primary readout: the full-rung both-stable paired ratio of each
  algorithm, classified as interval above 1, containing 1, or below 1. A loss or a failure
  of truncation is reported as such.

### X14b  Nine budgets for the X9 tails (priority 2)
Purpose: show how the paired ratio changes with the budget at a fixed tail. Existing X9 data
already show it at four rungs (e.g. NPG, alpha = 0.1: 1.64 at N_cal/4 and 0.68 at N_cal).
- alpha in {0.05, 0.1, 0.2, 0.4}: run the five X10b rungs j in {1, 3, 5, 7, 8}
  (N_cal/2, /8, /32, /128, /256) with the frozen X9 code, config, keys and analysis. The four
  existing X9 rungs are reused, never rerun.
- alpha = 0: no compute. The nine rungs at n = 24 already exist (X6b four + X10b five,
  `x10-20261106/summary_merged_nine_rungs.csv`). Reuse those rows with alpha = 0 and
  tau2_sq = 0 added, and verify that every reused value equals its source.
- Readout: as in X14a for every (alpha, algorithm, rung). In addition, descriptively, for
  each (alpha, algorithm) list the rungs whose both-stable interval lies above 1 and those
  whose interval lies below 1. Do not call an interpolated crossing budget a threshold.

### X14c  PI calibration at n = 60 (priority 3, pilot systems only)
Purpose: App. H.3 states "This calibration was not run for n=60". Apply exactly the rule that
was applied for n in {24, 36, 48, 72}: the smallest grid value at which the dense joint
estimate of Psi_{K0} satisfies the sigma_r criterion, both without and with the PSD
projection of the estimate of G_{K0}. Same code and block grid as for those dimensions, on
the n = 60 PILOT systems and seeds of X12 (never formal systems). Report both selected block
counts and whether they exceed N_cal(n = 60) = 2^21. No formal runs. First name the source
script of the existing calibration and its hash.

### X14d  Estimate accuracy at n = 60 (priority 4)
Purpose: the table of App. H.5 (median paired ratio of relative Frobenius errors before and
after truncation, at K0, from the same data) has columns n in {24, 36, 48, 72} only. First
identify the source script and data of that table (PROVENANCE.md points to
x6-20261101/CE-addition-v2) and state them. Then compute the n = 60 column with the same code
and analysis on the X12 n = 60 formal systems and seeds, with 2^22 blocks for Zhat and for
the PI pair [Ghat+, Zhat] (the value used at n in {48, 72}) and 2^19 transitions for Bhat.
Evaluation at K0 only; no learning.

### X14e  CE gap ratio at n = 60 (priority 5, 0 SU)
The CE ratio table of App. H.2 has rows n in {24, 36, 48, 72}. If the X10a n = 60 CE paths
saved the dense and truncated gaps at N in {2048, 8192, 32768, 131072, 524288}, compute the
paired both-stable ratio and stable counts with the same function as that table, from saved
data only. If they did not, run CE locally (0 SU) with the same code, systems, seeds and
nested prefixes as the X10a n = 60 paths, and say which case applied.

### Compute and gates
- Numerical work on Grace compute nodes as in X9/X12 (1 CPU, one BLAS/OpenMP/Numba thread,
  scratch caches, no installations); X14e may run locally.
- Cap: cumulative X14 actual <= 60 SU; requested exposure (settled actual + requested upper
  of outstanding allocations + 4 SU report reserve) <= 80 SU; global concurrency <= 64.
  If the forecast exceeds either, stop and report the numbers before any formal submission.
- Timing pilot on pilot systems only, as in X9: requested wall
  ceil((1.20 * measured body + 30)/60) min, peak RSS <= 80% of the request, no retries.
- Storage gates from the X12 rulings: fresh flat namespace, completed stages appended to
  per-task tar files, forecast < 80% of free file slots and bytes per MDT and globally, a
  quota-aware check immediately before every submission.
- Advancement: this GO and the pre-registration are Claude's acceptance of the science.
  Proceed PROTOCOL -> PILOT -> FORMAL -> REPORT for each item without waiting when every
  fixed gate passes. Stop and report on any failed gate, and on any needed deviation from the
  frozen X9 code/config other than alpha and the list of rungs.

### Deliverables (all in x14-20261108/)
- PROTOCOL_v1.md (this section verbatim plus hashes), pilot/formal/accounting receipts.
- `X9_summary_merged_nine_rungs.csv`: the bytes of `x9-20261106/summary.csv` as an exact
  prefix, then the alpha = 0 X10b rows, the new rungs for alpha > 0, and all alpha = 0.02 rows,
  with the same columns.
- `X9_transitions_saved_merged_nine_rungs.csv`: the X9 cross arithmetic and censoring rules on
  the nine-rung ladder (new file; the X9 file stays unchanged).
- Endpoint, stage and failure CSVs in the X9 schemas, with no failed row omitted.
- `PI_calibration_n60.csv`, `estimate_accuracy_n60.csv`, `CE_ratio_n60.csv`.
- REPORT.md with tables by alpha x algorithm x rung (medians/IQR, stable counts, paired ratios
  with intervals), spend in both books, deviations with reasons, and every result that
  contradicts a claim of the paper. PNG/SVG previews only inside x14-20261108/.


## Frozen input hashes (SHA-256)

- `X14 ruling section` `5ed67170318421ec93686c2c60d5860d62a0771e7c59039235af8806736d5a6e`
- `CLAUDE_TASK.md snapshot` `bd3acb8e01a800d996439bb28fd74cbdb95ce80cec2df71ee8c7557902305a8f`
- `X9 config-protocol-v1.json` `ff3f89cbae75e35c3f079e30d69f7bd1b4af63bf661528d65247563ee05c0196`
- `X10b schedule source` `cf3bc5ff72cf62ff5469008805ddf93a64623d043858074be76e20e9a9c9152b`
- `frozen_engine.py` `9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`
- `estimation.py` `f587bd48993288dbf9160dd4cc1e62542f15ee5794bda37590ec48dc672c9c59`
- `actor_paths.py` `905ebe819c50c860249dc11836eb9f356b97b6ea8d4ebe22e34d5a0e4f7deb3b`
- `x9_core.py` `e62b82f5617179791e362189ab5900b3c29dbf7ad2d2785813376fc02884c050`
- `analyze_x9.py` `7eafc31a73ab8e3f8924561d4892682e8bf73f57b06b5c321018494792a773bd`
- `X12 virtual_task_store_v2.py` `73fb86e75df141b4ce89c901f9b450b1cccb71dcb33db2aad8e926addc91250c`
- `config-x14a-v1.json` `14c24f346f75dc25a49a14a1ffef0fb9d02201936ae155ac2fb7864ffb07e4c2`
- `config-x14b-v1.json` `8bbdcc0dc2b873c210cdf009c1d04b0d915928fde4a31a73d6910c6c5bd85624`

The X14a/b JSON files inherit X9 numerical settings and replace the active alpha and/or rung lists. X9 scientific source files stay byte-identical. Job metadata and archive I/O are handled outside them.
