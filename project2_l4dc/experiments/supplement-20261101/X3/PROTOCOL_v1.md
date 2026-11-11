# X3 PROTOCOL v1 — full-rank spectra, fixed-order scans and adaptive CE

Neither X3 CE nor NPG formal is ACCEPTED yet. This protocol is prepared alongside
the running, accepted X1 actors as requested by Claude Review01:55. The user's
explicit-acceptance rule overrides the task/review's60-minute timeout exception.

## Systems and fixed cases

CE n=m16/32; each has spectra smooth0.7^j (j0...), two-level(1,1,.05,...), flat1.
Use the frozen independent unstable generator (rho(A)=1.05, independently sampled
stable eigenvalues), independent Haar U/V and cost-free stability-only correction.
No null term in full-rank systems. Q=R=W=I,nu1. Pilot systems9005/9006,
sampling7005/7006; formal systems301–308,sampling1201–1204. Each formal cell
has8 genuinely distinct systems x4 sampling seeds. Across spectra the same A and
singular-vector draws are paired, but B/control problems differ; no cross-system
budget ratio is called a truncation gain. Publish rho(A),P0 norm,initial gap and
initialization geometry. Truth enters simulator/evaluation and pilot calibration,
not the observation-only CE/NPG updates.

## CE shared fits, order grid and two adaptive thresholds

One continuous fixed-K0 trajectory with512 exploration-burn transitions. Joint
unwhitened OLS; all arms use the identical Ahat/Bhat/prefix. k=0/1/2/3/4/6/8/12/16
at n16; add24/32 at n32, dense identified with k=n rather than duplicated.
18 exact integer prefixes from4(n+m) to1024(n+m), adjacent ratio<=sqrt(2), are
frozen in `configs/X3_v1.json`. Plot at least6 preregistered prefixes plus complete
tables. k0 is a diagnostic outside the stated r>=1 learning theorem; on unstable
plants it may fail to yield a stabilizing DARE solution and must stay a failure.

Adaptive paper-form threshold: C5*sqrt((d+log(1/delta))/N),delta=.05, **one global
C5** for all CE dimensions/spectra. Calibrate as1.25 times the maximum normalized
operator error of the **dense fitted Bhat** over the disjoint pilot fits. Calibration
never examines truncated/adaptive policy performance or formal outputs. Freeze
the value and resolved config/hash before formal. It is a pilot-calibrated constant,
not a numerical certification of all theoretical LS confidence conditions.

Adaptive split threshold: ||Bhat_first_half-Bhat_second_half||op/2,multiplier1.
Both retain singular values strictly greater than their thresholds. Prefix halves
are exact same-trajectory sufficient-statistic splits; no extra sampling.

`fit_capture.py` stores the full and both half OLS solutions during pilot sampling.
Thus C5 calibration and the subsequent adaptive pilot synthesis can reuse the
exact same fits without replaying a trajectory. Formal execution uses the fixed
C5 and both adaptive modes directly in the same frozen engine.

Report absolute/relative median/IQR, full32-repeat stable counts, paired ratios
and system-bootstrap intervals (8 clusters,4 sampling seeds preserved,2000 draws,
seed2026110399). Failures are+inf. Plot the fixed-k median envelope as a labeled
post-hoc diagnostic, not an available oracle; adaptive selection uses only data.
Report B's tau_k² and beta_k from certificates; do not equate these with every
current NPG Z_K tail. Retain the flat-spectrum negative control and all failed/
unstable low-budget cells. No interpolation of attained precision budgets.

## NPG plan (implementation/config must be resolved before formal)

n=m12,full-rank smooth/two-level/flat; retain k1/2/4/6/12,dense=k12. Three
predeclared finite-data budgets multiply a common stage schedule by1/4/16.
Use paper eta from an arm-independent max-initial-P certificate and population
pilot calibration of update count, then the smallest dense-qualified base from
{512,2048,8192}. Batch shape is nd/a_t² with geometric precision envelope; H32,
16 pulse burn blocks,baseline and all primitive counts match across k arms.
No truth-selected output/recovery. Each arm's state is continuous; exogenous
innovations are paired, observations diverge after updates. Failed outputs stay
absorbing, with separately counted discarded K0 padding to preserve budget parity.

Dense qualification is stable on all pilot plants and median relative endpoint
<=.5; population reference must show sufficient optimization progress rather
than accepting a barely moving actor. The resolved eta/T/schedule/budget hashes,
multi-k collector equivalence check and full measured cost plan will be reported
before NPG formal acceptance. No automatic timeout bypass or unmeasured large grid.

## Resource envelope and files

First CE pilot:24 trajectories (6 cases x2 systems x2 sampling seeds),18 prefixes
and all fixed k, one core/2GiB,max15min (upper.25SU), including exact-fit archives.
Reuse captured fits for C5/adaptive pilot postprocessing; no learning replay.
Formal CE is192 trajectories with all methods sharing data; submit only after
X3 ACCEPTED and measured worst-case CPU/memory validation. NPG budget3 large-end
workloads must also be measured before committing the grid. All new pilots,
formals, reports, failures and optional X4 share the200-SU all-night cap.
Outputs go only below `supplement-20261101/X3` locally/remotely; old results and
all paper TeX remain read only. Protocol/config/source hashes are frozen before
the pilot and resolved hashes before formal, and each advancement rereads review.
