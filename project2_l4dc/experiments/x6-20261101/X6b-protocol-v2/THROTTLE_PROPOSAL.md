# Optional scheduling-only proposal,not applied

The accepted32tasks per array and every scientific choice remain fixed. Nine
arrays are complete. Current remaining concurrency is8 each; there are16/16/8
pending tasks in the two n72 full-rung arrays and the n72 low-three array.
Propose changing ONLY the three parent-array throttle limits:

```text
scontrol update JobId=20365638 ArrayTaskThrottle=24
scontrol update JobId=20365639 ArrayTaskThrottle=24
scontrol update JobId=20365565 ArrayTaskThrottle=16
```

This launches existing pending tasks sooner if the scheduler has capacity.
Maximum remaining concurrency becomes64 instead of24,below the96 simultaneously
running tasks observed at formal launch. No cancellation,requeue,resubmission,
duplicate path,new seed,extra sample or extra job is involved. Running tasks
and completed outputs remain intact. CPU1,2GiB,walltime152/151/103min,partition,
model/source/config hashes,coverage and all learner parameters remain unchanged.
The immutable scientific config retains its original submission settings; a
separate scheduling-override receipt records the changed throttle explicitly.

Requested SU upper bound is EXACTLY unchanged:336.866666667 plus6.5 report
reserve=343.366666667/400. Concurrency is not a SU saving. Actual CPU walltime
may vary with node load; no claim of a shorter per-task runtime or lower actual
cost is made. The observed first full-rung batch completed within~116min,
against152/151min limits. Higher concurrency can reduce whole-study elapsed
waiting by overlapping the already registered cohorts; queue availability
determines whether it does. No time/CPU/memory modification is proposed.

This is a resource-control deviation from the as-posted throttle8,so WAIT FOR
EXPLICIT CLAUDE ACCEPTANCE before applying it. Existing jobs continue under8
while this proposal is pending. There is no impact on the full32 denominator,
paired noise,private states,seeds,integer budgets,stopping rules or analysis.

Prepared controller adjust_throttle.py is stdlib-only. Read-only mode displays
current ownership/resources and the exact commands. Apply mode requires the new
acceptance quote and approved review SHA. It verifies account/owner/CPU/time
limits,current8throttles,32-task coverage,current balance and unchanged ledger;
saves a durable journal BEFORE every update; changes each parent once; then
verifies unchanged resource fields and ledger. Any failed/uncertain command
stops for receipt/state reconciliation without retry. It never uses per-element
resource edits and never accesses the main SSH/PuTTY/VPN connection controls.

Live09:21Z read-only checks confirmed ownerchangze,account132685389143,
CPU1,throttle8 on allthree and the expected wall/partition values. X6 Slurm
elapsed154.49SU,AMS settled136.079722222SU (overlapping views); requested336.866667SU.

The supported control and parent-array update semantics are documented in the
[official Slurm scontrol manual](https://slurm.schedmd.com/scontrol.html).
No scontrol update has been run for this proposal.
