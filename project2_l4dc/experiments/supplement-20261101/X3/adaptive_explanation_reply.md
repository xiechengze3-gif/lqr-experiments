Scope: X3 CE Review03:30 **postprocessing-only table complete**, C5 unchanged.

For all108(n,spectrum,N) cells, `X3/report-ce-rank-explanation-v4/adaptive_orders_vs_best_fixed.csv` places both adaptive selected-order distributions next to the best fixed-k median. The216-row long table adds stable counts, k0 counts, threshold median/IQR, the smallest retained true singular value and the next omitted true singular value;6912 per-output rows retain exact k/threshold/system/seed.

| n | Spectrum | N | Best fixed k | Method | Selected k median | Threshold median | Smallest retained true sigma median | Next omitted true sigma median | Stable |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| 16 | two-level | 32768 | 16 | adaptive_paper | 2 | 0.0839597 | 1 | 0.05 | 32/32 |
| 16 | two-level | 32768 | 16 | adaptive_split | 12 | 0.040319 | 0.05 | 0.05 | 32/32 |
| 32 | two-level | 65536 | 32 | adaptive_paper | 2 | 0.0821433 | 1 | 0.05 | 31/32 |
| 32 | two-level | 65536 | 32 | adaptive_split | 23 | 0.0424167 | 0.05 | 0.05 | 32/32 |

These are true singular values indexed by the data-selected order, not fitted singular values or an alignment certificate. k0 has no smallest retained singular value and is explicitly undefined, with its count shown. The next-omitted value makes the.05 tail cutoff visible. Frozen C5 and all formal outcomes remain unchanged; zero fitting, trajectories, or learning reruns. Source hashes and local processing provenance are in the new REPORT.json.
