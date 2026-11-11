# X0 PROTOCOL — historical data retrieval, 2026-11-01

This stage performs **zero new experimental runs and zero Slurm submissions**.
The experimental FORMAL gate remains closed for X1–X3 until Claude explicitly
ACCEPTS the corresponding protocol, regardless of the task file's 60-minute exception.
The direct user's 80-SU cap overrides the review-log statement claiming 200 SU.

1. Verify the already delivered group01/group04 files against their existing
   historical retrieval manifest, without changing those files or old documentation.
2. Pilot ingestion: compare the independent-A/B construction metadata and CE500
   pilot-table hashes against the immutable 2026-10-25 snapshot manifest.
3. Full data ingestion (X0 FORMAL, **retrieval only, no formal learning**):
   retrieve `analysis/independent-ab-stabilizer-20261022` and
   `analysis/ce500-common-constants-20261022` from the historical snapshot; also
   retrieve the current CE500 `report-confirm` tables and provenance from the
   original result directory. Keep pilot and confirm explicitly separate.
4. Report files, byte counts, source and local SHA-256, row counts, completion
   limits, and initialization/construction limitations. Do not re-run learning.

All new local artifacts go below `supplement-20261101/X0/`; the old experiment
folders and all paper TeX are read only. Remote transfer staging goes to
`/scratch/user/changze/lqr_experiments/tmp/supplement-20261101/`.
The existing PuTTY main connection is preserved. Scientific diagnostics for
subsequent experiments run only on Slurm compute nodes.
