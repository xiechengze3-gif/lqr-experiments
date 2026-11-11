# Low-rank LQR experiments

Code, configurations, saved outcomes, and figure scripts for the rank-truncation experiments in linear-quadratic regulation. The experiment families compare dense and rank-truncated certainty equivalence (CE), natural policy gradient (NPG), and policy iteration (PI) on synthetic systems.

## Verify and reproduce

Use Python 3.12 from the repository root. The dependency versions below match the local verification environment. On Windows, set up the environment, pip cache, and temporary directory on your designated drive before installing.

```sh
python -m pip install -r requirements.txt
python reproduce.py verify
python reproduce.py figures --output path/to/new-figure-directory
python reproduce.py smoke --output path/to/new-smoke-directory
```

- `verify` checks the release SHA-256 manifest and independently recomputes the X13 CE cells from the saved per-output CSV. It also checks the X14 tail and n=60 actor grid coverage and the arithmetic of the recorded stability counts.
- `figures` rerenders the four core experiment groups, the X1–X4 supplementary overview, and the X14 nine-budget tail figure from saved records. The command reruns the core package's numerical table checks, verifies the 32 original archived report files, and places regenerated figures and receipts in the supplied directory. It runs on a copy and leaves the versioned files available for byte-for-byte comparison. Figure metadata and rendering can vary with the platform.
- `smoke` runs the Stein estimator, greedy update, and recorded-failure regression tests. These use small synthetic systems. They are separate from the formal training runs.

## Results and provenance

| Experiment | Saved records and figures | Source and protocol |
| --- | --- | --- |
| Four core groups: input padding, same-data decomposition, full-rank rank scans, CE100 | [Core experiment index](project2_l4dc/experiments/README.md) and its `01_`–`04_` folders | [Version audit](project2_l4dc/experiments/AUDIT.md), [source snapshots](project2_l4dc/experiments/provenance/original), [extraction manifest](project2_l4dc/experiments/provenance/extractions.json) |
| October CE/NPG revisions, absolute and normalized gaps | [96,600 saved outputs](local_runs/ce-npg-arguments-20261028/report), [relative-gap and censoring tables](local_runs/ce-npg-initial-gap-20261028/report), [rank comparison](local_runs/ce-npg-rank-review-20261029) | [Frozen bundles](packages), [experiment protocol](docs/CE_NPG_ARGUMENT_PROTOCOL_20261027.md) |
| X1–X4: CE/NPG/PI mechanisms, tails and adaptive rank | [Supplement, figure exports and reports](project2_l4dc/experiments/supplement-20261101) | [Inventory](project2_l4dc/experiments/supplement-20261101/EXPERIMENT_INVENTORY.md), [data dictionary](project2_l4dc/experiments/supplement-20261101/DATA_DICTIONARY.md), frozen configs and source bundles in the supplement |
| X6–X8: scaling, estimator accuracy and CE controls | [X6](project2_l4dc/experiments/x6-20261101), [X7](project2_l4dc/experiments/x7-20261102), [X8](project2_l4dc/experiments/x8-local-20261104) | Protocol, source and configuration files in each experiment directory |
| X9–X11: tail negative control, CE and actor extensions, separate state and input dimension sweeps | [X9 report](project2_l4dc/experiments/x9-20261106/SCIENCE_REPORT.md), [X10 CE](project2_l4dc/experiments/x10-20261106/CE_REPORT.md), [X10 NPG/PI](project2_l4dc/experiments/x10-20261106/ACTOR_REPORT.md), [X11 report](project2_l4dc/experiments/x11-20261106/report-v2/REPORT.md) | Per-study frozen sources, configs and result files |
| X12–X14: n=60, zero null-component CE and nine-budget tail sweeps | [X12 recovered report](project2_l4dc/experiments/x12-20261106/delivery-recovery-report-v6r1/report), [X13 records](project2_l4dc/experiments/x13-20261108/formal), [X14 report and figures](project2_l4dc/experiments/x14-20261108/REPORT.md), [X14 n=60 at B*](project2_l4dc/experiments/x14-20261108/delivery-f-full-report) | [X12 protocol](project2_l4dc/experiments/x12-20261106/PROTOCOL_v1.md), [X13 driver and source](project2_l4dc/experiments/x13-20261108), [X14 protocol and code](project2_l4dc/experiments/x14-20261108) |

The saved results include instability and right-censoring where recorded. A stage or budget prefix is one observation within a trajectory. X13 contains 384 paired budget-prefix evaluations, producing 768 dense/truncated arm outputs. The reports document the paired seeds, denominators, primitive-transition accounting, and budget definitions. In particular, X12's rule-calibrated n=60 budget and X14's supplementary B* budget have separate tables.

## Rerunning the training experiments

The original scripts, scientific configurations, and selected frozen releases preserve the random seeds and experiment settings. The historical Slurm jobs and archival checks can reference site-specific storage and original task bundles. A full training rerun requires adapting those paths and allocating the resources in the corresponding protocol. The repository contains per-output CSV records, selected model inputs, and aggregate and failure tables. Multi-gigabyte raw trajectory archives, internal coordination notes, and manuscript drafts are outside this release. Historical delivery manifests may reference those original archives. Use the root `SHA256SUMS` to check the files distributed here.

To run a bounded example from the original pilot engine, use a Slurm compute node and a fresh output path.

```sh
srun python lqr_experiments.py run --manifest configs/pilot.json --task-id 1 --output path/to/ce-pilot
```
