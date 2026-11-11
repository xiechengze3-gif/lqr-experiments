# X12 n=m60 NPG / PI

Author GO13:15 CDT Nov6. Same X6b S family/certificate/streams/rank2,
eta.2,H16,nu1,burn16+baseline1 each update,NPG16/PI8 stages. Dense RK term
retained in NPG; PI joint left compression/PSD clipping unchanged. Preserve
all absorbing learning failures, their padding budgets and infinity gaps.
No critic/LSTD/recovery/line search/oracle input/rank adaptation.

Kernel and estimator hashes are byte-identical to X10b verified sources.
actor_paths numerical source is literal identical; the one path guard changes
to a fresh X12 namespace and an inverse replacement proves identity. Full
actor file hash therefore differs; this is disclosed. No duplicate replay.

CALIBRATION pilot: systems9101/9102,seeds9601..9604,K0=0; exact frozen Stein
collector/state/RNG/chunk/prefix summation. Grid2048/8192/32768/131072/524288/
2097152/4194304, exactly the registered n48 and n72 grids bracketing n60.
No extra1048576 rung, no formal/truncated/actor readout enters selection.
For eachN, median4seeds per system, then median2systems of dense
||Zhat-Z||op/sigma2(Z). Select smallest registeredN with value<=1. Censored
at4194304 => stop/report, no extension. All8paths run their entire fixed grid.
8oneCPU/2GiB/20min tasks plus1five-min resolution job, requested2.75SU,
536873088primitive calibration transitions, no implicit retries.

Global slot reservation: X10b is two independent lanes of<=32 each. Calibration
array<=8 depends on successful completion of the original first8 n72PI tasks
20416268_0..7. They have no lane1 successor and cannot rerun here. Thus their
completion permanently leaves at least8slots: remainingPI<=24 + otherlane32
+calibration8<=64. Resolution waits for whole calibration and uses1slot.
Every later submission accounts for all extant reserved slots, not merely a
momentary running count. No changes to X10b tasks or frozen configs.

TIMING pilot: disjoint pilot system9102,seed9801, both algorithms/arms,
all9rungs at selectedbase; original integer schedules and exact primitive
parity. Two1CPU/2GiB/180min tasks, requested6SU, only after calibration PASS.
Record full body/wall seconds and peakRSS; no outcome-dependent grid choice.
Checks: kernel/estimator/literal actor identity; calibration coverage/criterion;
all18paired paths/counts/RNG/source receipts; memory<80%of2GiB; Slurm billing1.
Stop/report on hard error, censoring or failed fixed check. Never automatic retry.

FORMAL automatically iff all fixed checks PASS and measured forecast
actual<=230SU/requestedupper<=300SU including all pilot and8SU reportreserve.
Forecast32times each algorithm's full9rung pilot body, plus pilots/report;
wall guards ceil((1.2*body+30)/60) minutes per task. If historical comparable
per-transition runtime yields a larger forecast, keep the larger. Resource
pilot has not happened yet, so there is NO current formal-cost assertion.
Formal systems301..308 xseeds1701..1704, all9rungs, bothalgorithms/arms,
64allocationtasks/576pairedpaths/1152arms. Choose only scheduling throttle
to preserve global64; no science or count changes. No formal observations yet.

REPORT schema exactly X6b summary.csv, append n60 to complete X6b+X10b9rung
table, original matching-budget cross arithmetic transitions_saved_derived.csv.
All failure denominators, censoring, pairing and bootstrap routines unchanged.
Copy every completed raw bundle promptly to E with archive/member SHA checks.
Old datasets used only from verified local copies; no dependency on purged
remote X6b. Descriptive, no theorem verification or epsilon-attainment claim.
No old results/frozen releases/paper edits. Read review log before each stage.
