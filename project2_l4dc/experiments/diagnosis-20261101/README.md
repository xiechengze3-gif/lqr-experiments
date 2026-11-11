# NPG / PI diagnostic follow-up from existing results

This is a source audit, saved-table aggregation and scalar calculation, not a new
learning experiment. No Slurm job was submitted and no frozen result, release or
paper TeX was modified. The overnight accounting remains112.920278SU/200.

The current evidence supports different explanations in different experiments:

| Question | Evidence and assessment |
|---|---|
| Implementation mismatch? | The frozen Stein return, adjacent-block difference, sign, Gram solve, NPG RK term and Z-only truncation match Section4. PI PSD clipping, joint[G+,Z] subspace, two-sided G compression and full greedy match AppendixE. No specific update/sign/count defect was found. Independent cost/gap checks validate evaluation, not the entire estimator. |
| Exact-rank NPG X1/X2? | True Z_K has rank<=2, so there is no true spectral-tail bias. Noise-dependent SVD selection can nevertheless distort the action component. X2n12 D medians.422729->.228913 while action gap.0578845->.259950;32/32 pairs reduce D,25/32 increase action gap. Poor empirical subspace alignment is a plausible mechanism, not yet directly demonstrated by the old saved data. |
| Too few optimization iterations? | At identical eta/T, exact-gradient relative-gap medians are.025608(n12)/.017115(n24), while sampled dense/truncated medians are.577006/.714912 and.144480/.150638. Thus iteration count alone does not explain the discrepancy. Sampling error, finite-H bias and nonlinear truncation effects are not separately identified by this comparison. |
| Full-rank NPG X3? | All36 paired comparisons are full-rank cases, not exact-rank separation tests. Low-order truncation discards nonzero true directions. At larger budgets dense wins; this is consistent with approximation bias and trajectory/cost-weight effects. A lower last-stage Frobenius error is not a terminal-cost dominance theorem. |
| PI? | PI does show truncation benefits: failures116/288dense vs77/288truncated; finite-pair ratios in the .25-null family are3.20/4.76/7.60/9.85 for m4/6/9/12, with20/20/17/18 finite pairs out of32. Both methods still fail often.99/116dense and66/77truncated failures first appear by update3. Even m=r=2, where processing is identical, fails10/32 in both arms. This points to coarse early joint estimates/full greedy sensitivity rather than true spectral-tail bias. Raw PI G/Z were not saved separately, so their individual contributions cannot now be uniquely recovered from K alone. |

Settings: Q=R=W=I,nu1,A independent of B with one eigenvalue1.05 and remaining
eigenvalues independently drawn from[.15,.60]. A and B have independent Haar
orientations. K0 is a cost-independent stability correction to move the unstable
mode to.65. Exact-rank cases use r2 and a zero-null or.25-null initializer.
Each formal cell is8 independent systems x4 sampling seeds. Actors have one
continuous trajectory per arm, H32,16pulse burn blocks plus one baseline per
stage, paired innovations and exact per-arm transition parity. Diverged policies
do not share identical observed states.

| Cell | eta | Updates | Per-arm transitions |
|---|---:|---:|---:|
| X1 NPG,n12,m2/4/6/9/12,r2 | .00900061455 | 96 | 93,308,928 |
| X1 PI,same exact-rank plants | full greedy,no NPG eta damping | 8 | 93,308,928 |
| X2 NPG,n=m12,r2 | .0111539190 | 96 | 33,602,016 |
| X2 NPG,n=m24,r2 | .00282803447 | 384 | 542,850,432 |
| X3 NPG,n=m12,full rank,k1/2/4/6/12 | .0149307799 | 64 | 88,850,304 /355,296,768 /1,421,082,624 |

X1 NPG per-stage blocks grow from2048 to125515; PI from80516 to910947.
PI was formally run only in X1. X2/X3 have no new calibrated PI comparison.
X3 spectra are .7^j(j=0..11), (1,1,.05,...,.05), and flat1.

Important correction in interpretation: the learner formulas match the paper,
but the experiment's pilot-calibrated parameter schedule is not the fully
certified schedule of AppendixC/E. It fixes H32 and burn16, selects T using
population pilot learning, and selects the smallest dense-qualified practical
batch base. AppendixC instead chooses horizons using the certificate and target
accuracy, state-dependent burn, and batch sizes tied to c1,c2,C8,L_stat and logs.
AppendixE similarly requires a small joint-error radius for PI. Stability plus a
dense pilot median<=.5 is not a substitute for these accuracy conditions.

Concrete checks, using the very same common R1 certificate and Q=R=W=I:

- AppendixA sets p=2p0,chi=p,rho=sqrt(1-1/p),kappa^2=chi. AppendixC requires
  kappa^2 rho^H<=1. X1 has p0=55.0517623, giving95.1485 at H32 and requiring
  H>=1031 for this conservative condition. X3 has p0=32.9878689, giving51.6720
  and requiring H>=549. These are proof-based sufficient horizons, not a claim
  that actual mixing empirically needs549 or1031 steps.
- AppendixB constructs c1=min{zeta/(2+p),e_loc/3},zeta=sqrt(1/(p+2)), so
  c1<=(p+2)^(-3/2). For X3 this is.001784305. The two-level tail beta2=.05
  exceeds that chosen sufficient threshold. Dense x16 raw last-error Frobenius
  median.532519 implies an operator-error median at least.153725 by the
  elementary norm bound, also above this sufficient radius. This does not prove
  the impossibility of sharper constants or successful practical learning.
- The exact-rank NPG separation theorem additionally assumes
  (m-r)n>=C11 log(C N_last/delta)^5, not merely rank(B)=2.
  At X1m12,n12,N_last125515,delta=.05 and even C=1, the dimension side is120
  while log(N_last/delta)^5 is694840.65. The proof takes C11>=1 and C>=1.
  This experiment therefore does not meet that high-probability separation
  regime. Increasing N alone does not fix this dimension/log condition.

Consequently these outcomes are not counterexamples to the stated conditional
theorems. Theorem3 bounds gap and stability under a specified error/schedule
event; it does not assert truncated beats dense on every finite sample. The
separation theorem has further hypotheses. Conversely, the current experiments
cannot be described as a strict numerical validation of those hypotheses.

The new X5 task fixes the engine/eta/T/H/burn/seeds and increases only per-stage
batches. This can test whether reduced sampling noise and improved subspace
alignment expose an exact-rank total-gap gain. It cannot automatically repair
the fixed-H discrepancy from the conservative theoretical schedule, and neither
H1 nor H2 may be assumed true in advance. X5 has no protocol/status submission
in this diagnostic follow-up and no new job was started here.

Sources: frozen `supplement-20261101/engine.py` SHA256
`9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`,
its three formal configs, `analysis-P1-P2-tables-v2/`,
`X1/report-actors-full-tables-v2/`, `X3/report-npg-last-estimator-v1/`;
paper `sections/04-upper.tex`, `05-lower.tex`, and appendices A/B/C/E.
