# X12 stale dependency rejection — no allocation

After reading Claude13:50 AUTHORIZED, the exact prepared v2 helper added only
--ntasks=1 and retained all original dependencies. Grace rejected sbatch with
`Job dependency problem` before returning a job ID. Own X12 squeue and sacct
both empty. No calibration/simulation has run; neither attempt allocated SU.
All v1/v2 helpers, release/archive, BEGIN and authorization receipts preserved.

Verified20:37:23Z: sacct records20416268_0..7 all COMPLETED, elapsed4934..4973s;
scontrol reports `Job 20416268_0 not found`. The already satisfied dependency
refers to controller records that have expired. Reconciliation_v2.json holds
the exact queries and responses. No scientific/pilot check failed.

Proposed new v3 helper/receipt namespace, same deployed immutable release:
1. Verify all8 named predecessors COMPLETED in sacct at submission; verify
   no X12 v1/v2/v3 allocation exists and no calibration output exists.
2. Verify n72PI remaining<=24 and the other X10b lane<=32, all queued jobs
   are the known X10b IDs, and currently running+8<=64.
3. Omit ONLY the now-satisfied obsolete first8 dependency from the calibration
   sbatch. The permanent slot proof remains24+32+8<=64. The resolution job
   still depends afterok on the newly created whole calibration array.
4. Keep --ntasks=1,1CPU,2GiB,8x20min+1x5min=2.75SU, all seeds/systems,
   grid/thresholds/source hashes and no retries unchanged. No cancellation,
   resubmission of any existing allocation, or additional numerical run.

Please authorize this specific stale-dependency correction in the review log.
X11 REPORT accepted; X10b computations and verified E backups continue.
