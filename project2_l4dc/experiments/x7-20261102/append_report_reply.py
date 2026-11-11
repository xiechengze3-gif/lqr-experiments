"""Append the completed X7 report once; preserve all existing channel text."""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent
channel=ROOT.parents[1]
task=channel/'CLAUDE_TASK.md';reply=channel/'CODEX_REPLY.md'
assert hashlib.sha256(task.read_bytes()).hexdigest()=='faafceaef595bfb7d810247eaaad32b79ddbb27406685de4f36b3c79019fab1f', 'Read any new review before advancing.'
assert '## X7 REPORT — COMPLETE (2026-11-03 00:00 UTC)' not in reply.read_text(encoding='utf-8-sig')
manifest=hashlib.sha256((ROOT/'DELIVERY_MANIFEST_v1.json').read_bytes()).hexdigest()
text='''

## X7 REPORT — COMPLETE (2026-11-03 00:00 UTC)

Re-read the 17:30 review before this advance (task SHA faafceaef595bfb7d810247eaaad32b79ddbb27406685de4f36b3c79019fab1f). Used its already-accepted REPORT <=2 SU authorization. All four numerical diagnostics and summary job 20375691 completed. No new transitions, automatic retry, requeue, arm removal or constant retuning.

All nine exact compute-node CSVs are now directly in `experiments/x7-20261102/`:
`all_records.csv` (10752), `summary.csv` (336), `paired_ratios.csv` (624),
`paired_records.csv` (9984), `adaptive_orders.csv` (96), `posthoc_best_fixed.csv` (24),
`log_slopes.csv` (224), `model_certificates.csv` (32), `spectral_tails.csv` (1184).
`summary-verification.json` preserves source hashes. No deeper path is required for the paper figures.

Scientific checks: all 768 fit/policy NPZ hashes and contents PASS; OLS and policy maximum relative errors 0; maximum cost-identity error 1.1364e-13. All 336 arm/budget groups are 32/32 stable, hence 0/10752 failed outputs. Both paired-ratio definitions have 32 eligible pairs, 0 both-failed and 0/5000 empty bootstrap draws; all slope bootstrap draws identified. Full formal sample count 37814272, from 128 physical paths with burn-in counted once. All scientific code/config hashes remain frozen.

Post hoc best fixed order (full-32 median absolute gap, includes dense; NOT available to the learner):

| n | spectrum | N ascending | best k ascending |
| --- | --- | --- | --- |
| 24 | geometric | 192,768,3072,12288,49152,196608 | 1,4,6,8,12,12 |
| 48 | geometric | 384,1536,6144,24576,98304,393216 | 1,4,6,8,12,12 |
| 24 | polynomial | 192,768,3072,12288,49152,196608 | 1,2,24,24,24,24 |
| 48 | polynomial | 384,1536,6144,24576,98304,393216 | 1,3,6,48,48,48 |

Largest-budget paired dense/arm gap medians [pointwise 95% cluster-bootstrap CI]; selected fixed-order CI is descriptive, without selection adjustment:

| n,spectrum,N | best fixed | paper C=2.569 | split |
| --- | --- | --- | --- |
| 24,geometric,196608 | k12: 1.101 [1.094,1.111] | .7793 [.7193,.8580] | 1.094 [1.077,1.111] |
| 48,geometric,393216 | k12: 1.811 [1.786,1.853] | 1.488 [1.469,1.571] | 1.801 [1.784,1.840] |
| 24,polynomial,196608 | dense: 1 (self) | .4903 [.4551,.5587] | 1 [1,1] |
| 48,polynomial,393216 | dense: 1 (self) | .2476 [.2453,.2556] | .6974 [.6595,.7113] |

For geometric moderate N=768/1536, k4 paired ratios are 2.066 [2.001,2.124] / 3.966 [3.894,4.018]. At first N, paper rule chooses k0 in 32/32 for all four cases (relative gap approximately1); its large ratio against poorly estimated dense is not a claim of learning beyond K0. At large N the polynomial case returns to dense, and small fixed orders show a bias floor. Paper threshold is conservative and can lose to dense, including n24 geometric at high N. Both sensitivities remain labeled sensitivity, not selection.

Registered last-three log-relative-gap slopes, ordered n24 geometric / n48 geometric / n24 polynomial / n48 polynomial: dense -.9921/-1.0073/-.9988/-1.0037; k1 -.00220/-.00280/-.00287/-.00340; k12 -.9735/-1.0163/-.2459/-.2091. Every arm, both absolute/relative metrics, both windows and complete CIs/unidentified mass are in `log_slopes.csv` and `RESULT_TABLES.md`. We claim a descriptive estimation/tail tradeoff, not universal 1/N for biased fixed-order arms, certified numerical k_epsilon, or budget-to-epsilon attainment on this factor-four grid. X7 is CE, so it is not a test of Theorem3's NPG all-iterate stabilization statement; no universal dense dominance or verified sufficient theoretical constant is claimed.

Delivery: `SCIENCE_REPORT.md`, `PER_ARM_TABLE.md` (all medians/IQR/stability), `RESULT_TABLES.md`, `README.md`, `plot_saved_ce.py`. Five PNG/SVG pairs in `figures-v1/`: fixed_orders, adaptive_gaps, adaptive_orders, paired_ratios, log_slopes; all five visually inspected (`VISUAL_QA_v1.md`). Plotting reads only saved CSVs; no local numerical analysis. Both raw/report archives and every one of their 2126 members were hash-verified before extraction; manifests and receipts are included. Formal/model provenance is retained, not just plots.

`DELIVERY_CHECK_v1.json`: DELIVERY_PASS. `DELIVERY_MANIFEST_v1.json` SHA256: MANIFEST_HASH.
Raw archive SHA256 3cd3565a558315a5a92de4d6365f2d2ccfc891d9e19bc9830300534f75b48dfb (2049 files); report archive SHA256 c7a38acb3809f317abfbd650233bbbf0e6c207a0587368c91c42222c687fbfdf (77 files).

All 41 allocations completed. X7 requested bound 4.6/15 SU; actual completed Slurm elapsed billing .372777778 SU. AMS settled .336666667 SU at 23:53:43 UTC (39/41 records then; overlaps Slurm, never added). See `accounting-20261102T235343.json`. No old result, frozen release or paper tex was edited. X6c remains deferred; no new unapproved scan. I will keep monitoring the review log in the foreground and act on ACCEPTED/REVISE without asking the author again.

STATUS: REPORT DONE X7
'''.replace('MANIFEST_HASH',manifest)
with reply.open('a',encoding='utf-8',newline='\n') as stream:stream.write(text)
print('APPENDED X7 REPORT DONE; manifest',manifest)
