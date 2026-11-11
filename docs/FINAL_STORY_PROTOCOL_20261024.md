# Final E1/E2/E3 experiment protocol (2026-10-24)

This is a new frozen study. Historical experiments remain separate. The supplied
24 October technical report is the mathematical reference, not an execution
instruction. In particular, its Section 7 explicitly says estimated-subspace
truncated CE need not have zero true redundant cost.

## Questions and coverage

E1: pad one fixed n=12, rank-2 plant with zero inputs; m=3,6,9,12 (no m>>n).
A=.5 I, Q=R=W=I, nonzero B singular values both 1. Hidden Haar action bases.
K0=.25 v_null h^T, with fixed unit h within each system and one null vector.
Consequently BK0=0, P0, Pstar, Jstar, initial gap and sensitivity are invariant
across m. Three system seeds 101..103, eight sampling seeds 100..107 each.
Independent rotations are conditional system fixtures; all systems are
orthogonally equivalent, not a broad population of dynamical difficulties.

NPG: residual-only hard SVD, exact RK retained, eta=1/9, H=12, burn=132 per
stage, 64 updates, 16 updates each at Nfinal/8,/4,/2,/1, Nfinal=32768.
PI: clip G, joint SVD of [G+,Z], compress G on both sides, full greedy update;
eight stages at N=122964 each. Exactly 11,805,696 assigned transitions per arm
for both algorithms (including 64/8 independent baseline blocks and burns).
Dense/truncated use paired innovations and their own continuous trajectories.
After policies diverge the realized data are not identical. Same-data terminal
counterfactual updates are recorded separately and are not complete learning.

CE: one common continuous OLS trajectory per seed, 132 burn transitions,
prefixes 512,2048,8192,32768; primary E1b prefix8192, total8324.
Both A and B are estimated. Dense and rank-2 B-truncated Riccati syntheses
share exactly the same fit. Report true redundant cost of each, plus a clearly
marked diagnostic true-subspace projection reference, whose redundant cost is
zero. No true projection is used by any learner.

E2: full-rank n=m=12, A=.7 I, B=U diag(.6**j) V^T, j=0..11, Q=R=W=I,
K0=0. Same three system and eight sampling seeds. Only k changes within an
instance. NPG is the main algorithm with the E1 step, horizon, burn and 64-stage
schedule, at Nfinal=2048,8192,32768,131072. Sweep k=0,1,2,3,4,5,6,8,10,12;
k12 is dense (computed once). Fixed k=2 is preregistered for the crossover
panel. Adaptive uses a data-only half-batch disagreement proxy and a frozen
multiplier. Retained rank is allowed to be zero. CE uses the same k sweep and
adaptive rule at consecutive-transition prefixes512..131072 in powers of4.

Calibration is performed before formal tests, on independent system seeds
9001,9002 and sampling seeds900,901. Adaptive NPG multiplier candidates .5,1,2
are compared at all four budgets; choose the candidate minimizing the mean
log(1+gap), with any unstable/failed outcome assigned a fixed loss20. CE is
calibrated separately. Break ties toward the larger multiplier. Freeze the
selection file, calibration data hashes and source/config identity before test
submission. This is an empirically calibrated hard threshold, not a proved
finite-sample confidence radius. Evaluate true spectral-error coverage only
offline. Theoretical oracle k*a^2+tau_k^2 is a diagnostic and not a selector;
report its definition and distinguish it from the empirical lower envelope.

E3: reuse all complete E1 policies at m12, without further training. Ten fixed
independent random perturbation directions per system, normalized to unit
operator norm and right-projected onto the true nominal nullspace. Evaluate
delta=0,1,2,4,8,16. Pair directions across methods. Report signed relative cost
change (Jpert-Jnom)/Jnom, absolute relative change, and instability, with all
nominal failures retained. No deployment samples are collected.

## Reporting and decision rules

Report raw final iterates, absolute gaps, all-seed failure rates and stable-seed
summaries together. Failure-inclusive median treats failure as infinity; do not
draw finite values when that median is infinite. No best-iterate selection,
truth-based update rejection, reset, or test-set hyperparameter selection.
E2 U-shapes, shift of minimizing k, dense early ordering and threshold proximity
are empirical questions, not acceptance gates. Report disagreement promptly;
do not keep tuning to obtain the desired narrative.

For every system/order save tau_k^2, beta_k, ||Pstar Fstar||_F^2, sensitivity
stable rank, p0, J0/Jstar, and all certificates. k_epsilon uses explicitly fixed
operational c_eff=1 and epsilon=.5,.1,.02,.005,.001; it is an illustrative tail
rank, not the unknown numerical constant in the theorem. No cross-rank
invariance is claimed. Every budget includes burn and baseline. Preserve actual
used transitions for early failures and allocated budgets for missing endpoints.
Store every terminal policy, per-stage rank/threshold/critic diagnostics,
source hashes, Slurm provenance, and complete output coverage.

## Execution and cost limits

Numerical simulations and exact evaluations run only on Grace Slurm compute
nodes. Local work is source preparation, PDF extraction and artifact review.
Use the existing environment, one CPU and 2GiB per job, pinned BLAS/Numba threads.
Remote outputs/cache/temp are beneath /scratch/user/changze/lqr_experiments.
Local source and retrieved outputs are beneath E:/ChatGPT/Projects/LQR_experiments
(the currently writable E: workspace); no large C: writes or dependency install.

First a maximum-size complete NPG and PI benchmark plus independent numerical
identities, at most10 minutes/1CPU. Calibration and formal submission sizes
and wall limits must be derived from this measured runtime. Hard total cap
12 allocated CPU-hours including pilot/calibration/report/reserve; no automatic
retries, no cancellation or alteration of existing jobs. Save receipt before
each submission; verify remote state before retrying any uncertain write.

