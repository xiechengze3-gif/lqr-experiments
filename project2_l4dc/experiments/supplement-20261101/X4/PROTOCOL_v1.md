# X4 optional diagnostic — frozen-policy robustness; zero retraining

Prepared while the accepted primary actors run. X4 formal stays closed until its
own explicit ACCEPTED. It never preempts the mandatory X1/X2/X3 or optional n48
budget decision; total additional pilot/formal/report request upper.25SU.

Use X1 n12,m12,r2,nonzero-null.25 family. Formal sources: systems101–108 x
sampling1001–1004; CE N8192,dense/truncated; NPG final T96,dense/truncated;
PI v4 final T8,dense/truncated. Fixed endpoint only: a failed source endpoint
remains failed on every perturbation, no earlier successful iterate or K0 recovery.
Do not compare CE versus actors as sample-efficiency gains; their source budgets
differ. Pair dense/truncated within identical source system/seed/algorithm only.

Ten fixed directions per system: Gaussian12x12 matrix projected right onto
ker(B), normalized to operator norm1. SeedSequence[2026110401,system,direction]
for directions0–9; all policy seeds/algorithms use the same construction. Evaluate
DeltaB=.25/.5/1 times||B|| times each direction, with DeltaB V_r=0. Verify both
operator norm and null constraint to1e-12, save every perturbation and source-file
hash. A stays the same independent unstable A. True B/V is used only for this
offline diagnostic, never to update a learned policy. No extra observations or
state trajectory is generated.

Formal has192 frozen policies x10 directions x3 scales=5760 evaluations,320
per(algorithm,arm,scale). All eight independent systems and four sampling seeds
are retained. Evaluate the perturbed system's optimal cost offline, absolute gap,
stability, median/IQR with failed policies+inf, and same-perturbation paired ratios.
Bootstrap whole systems8clusters, all40(seed,direction) observations stay together,
2000 resamples, seed2026110499. Report stable counts out of320 and distinguish
failed source outputs from new instability under perturbation.

Relative gap uses the perturbed plant's K0 reference only when K0 is stable.
If that reference is undefined, explicitly report the defined count; do not call
it a learned-policy failure. Also provide gap/source-unperturbed-initial-gap as
a labeled secondary normalization. Neither normalization is an epsilon claim.
Check stable-policy gaps by two independent Lyapunov identities.

Pilot uses only preexisting disjoint R3 systems9001/9002,trial7001,NPG/PI,
same fixed magnitudes/direction rule:240 evaluations, no tuning. One core2GiB,
max5min, upper.083333SU. Freeze `configs/X4_v1.json`,`robustness_x4.py` hashes
before pilot; formal acceptance receipt must match them. Formal one core2GiB,
max5min,upper.083333SU based on the complete pilot timing; report max5min upper
.083333SU. If measurement requires more, publish a new measured bound before
formal and keep the200-SU global gate. No old result or paper TeX is changed.
