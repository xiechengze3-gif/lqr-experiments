# X12 submission rejection — no allocation, request metadata correction

The initial calibration sbatch was rejected by Grace's job_submit plugin:
`either --ntasks, or --ntasks-per-node, or --nodes should be provided`.
No Slurm ID was returned. Own-name squeue and sacct reconciliation both return
zero rows, and no model/calibration output or success receipt exists. Preserve
the original release, package, helper and BEGIN receipt. No automatic replay.

Proposed correction only: explicitly add `--ntasks=1` to the submit common
arguments (already one CPU/task, 2GiB,20min/5min). This expresses the intended
single process and does not change CPU/memory/time, science, ids, seeds,
calibration grid, thresholds, dependencies or the2.75SU requested ceiling.
Use a new submission helper/control namespace and v2 receipt names, reusing
the deployed immutable pilot release by reference; no package re-upload and
no numerical retry because no allocation/experiment was created. Recheck own
job absence, source hashes, latest review, slot proof and fresh account first.

Please authorize this corrected submission in the review log. X11 and X10b
continue independently. No formal X12 run was submitted. The original failed
submission counts0 allocated SU, subject to subsequent accounting reconciliation.
