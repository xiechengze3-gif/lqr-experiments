# X12 FORMAL stopped: file-count quota

At 01:12Z Nov7, all64 formal allocations20424516/20424517 failed (ExitCode1:0). Logs show `OSError: [Errno 122] Disk quota exceeded` when creating stage NPZ files; the exception handler could not create HARD_FAILURE.json.tmp for the same reason. No automatic retry, cancellation, data deletion or REPORT submission occurred. This is infrastructure failure, not observed policy instability. All previous pilot checks and their raw E deliveries remain valid; no FORMAL DONE claim.

Read-only quota evidence at01:15Z:

- Scratch:668.8GB of1TB used; **250000/250000 file-count limit**, zero free inodes in quota-aware df. Physical bytes are available.
- Home:4.2GB of10GB used,9271/10000 files, only729 file slots available.
- Current user has only group changze; no own-group project storage candidate was found through group-scoped checks. No other user's directory was listed.

I omitted the remote file-quota admission check before submitting FORMAL. Earlier local E-space and CPU/RSS checks do not substitute for it. This omission is recorded, and any recovery must explicitly gate both bytes and peak files before numerical work.

All failed outputs/checkpoints/logs/releases remain untouched. Plan: first seal the entire failed partial run and provenance to a **new** home transit archive (few files), copy to E and verify every member. This needs no simulation and leaves the source intact. Scratch cannot create a new archive inode. Home's measured free bytes/file slots accommodate this temporary evidence copy.

No numerical recovery is authorized by the original GO after this failure. A concrete storage and budget correction will be proposed for review. Promising direction: preserve old results and the failed v1 tree; use a fresh home namespace with completed-stage raw bytes appended to per-task tar files, limiting active loose files. Keep collector/learner functions unchanged, validate saved-byte equivalence and quota peak in a metadata-only pilot, and reuse every complete old path by SHA rather than rerun it. Any partial-path restart/resume needs explicit approval and must retain its wasted samples/CPU history.

The original cumulative request book is169.9SU plus8report reserve=177.9, although failed allocations have released unused reservations. A second full request would make historical summed requests exceed300; do not silently reset the book or reinterpret the cap. Recovery needs an explicit requested-cap/accounting ruling, with all failed actual charges retained and actual-forecast cap230 unchanged unless explicitly revised. No new numerical job before that ruling and a complete reviewable plan.
