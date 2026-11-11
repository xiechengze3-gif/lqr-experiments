# Interpretation for the frozen X6b study

Read-only check of the current paper on2026-11-02, while FORMAL is running.
No paper TeX, accepted algorithm, configuration, schedule or analysis was changed.
These statements describe the scope of the experiment, before its numerical REPORT.

The learner equations agree with the paper: CE truncates the estimated B from
the shared OLS fit; NPG keeps RK and truncates only the Stein Z estimate; PI
PSD-clips G, obtains a joint leading left space of[G+,Z], compresses G on both
sides and Z on the left, then takes the full greedy update. In the current
paper, the PI formula is Appendix E, equation app:eq:tpi. The fixed-class choice
p0=2 is legitimate under the standing assumption ||P_K0||<=p0; p0 need not equal
the realized norm for each plant. With R=I and ||B||=1, this gives eta=0.2.

Theorem thm:e2e(b)'s statement that every iterate stabilizes is conditional on
the appendix schedule and its constants. Appendix C, Schedule for NPG, defines
a_t^2=min{c1^2,c2*gbar_t/(4*C8*r)}, horizons tied to that tolerance, and batches
with the L_batch, H_t, n*d, logarithm and a_t factors. The first-failure argument
uses the event that all stage operator errors are within these tolerances.
The PI remark permits different constants for its joint estimate.

X6b uses the explicitly accepted empirical instantiation: pilot-only bases,
geometric batches, H=16, burn16, population-selected T16/8, eta0.2 and the
registered four-rung ladder. It does not implement or numerically certify every
worst-case constant, logarithmic factor, horizon and stage error inequality in
the appendix. In particular, pilot rho_op<=1 is a relative signal-to-error
diagnostic, not a certificate that all a_t<=c1 and all theorem hypotheses hold
along every learned path. Consequently an experimental failure at these budgets
alone does not contradict the conditional every-iterate stability theorem.

For exact rank2, tau2=beta2=0: there is no discarded true spectral tail. A noisy
estimated leading subspace can still suppress the component along the true
signal. That finite-sample nonlinear estimation effect can coexist with smaller
Frobenius error and weak terminal improvement. Existing X6a evidence and the
new X6b path diagnostics must be kept distinct from an assertion that one fixed
implementation bug, schedule issue, or bias has been conclusively isolated.

A same-system dense/truncated terminal ratio is an empirical comparison, not
an exact dimension-factor identity or a guarantee for every seed. Exact-rank
and fixed certificate assumptions alone do not imply pointwise dominance at
every finite budget. All failures and negative registered cells remain visible.

The epsilon output concerns the smallest observed registered rung with29/32
successful endpoints. It does not estimate an interpolated exact minimum budget,
nor certify a population success probability>=0.9 with95% confidence. Censoring
means the empirical criterion was not attained on the observed ladder; no claim
is made about unobserved intermediate budgets. The5000 system-cluster bootstrap
keeps censored mass and common draws across arms/rungs/ratio definitions.

Read-only source locations under C:/Users/24375/Projects/project2_l4dc:

- sections/02-setting.tex: standing assumption, lines28-37;
  SHA2566f12f0f1d4a992e4f87a77066194f80bf2c144608e1d8350a2c56f4024da4579.
- sections/04-upper.tex: algorithms lines29-58, theorem lines60-78,
  statistical error/schedule discussion lines121-151, PI remark lines153-158;
  SHA256525c54dfb07629fa0fe0cc5e8587f7c5a45947eed027d9f05a488baf17a7a8ac.
- sections/app/C-statistics.tex: schedule starts line404 and first-failure
  argument follows it;
  SHA256ad3ecd644ac07bbe598af0e979bbf1321848181d8ea353a4105f20d02e9de9c3.
- sections/app/E-pi.tex: joint processing/update lines8-20;
  SHA2561778be2d1e3f77afed7145bb7d192db28af441642ecddeca40b4d82807d8eae7.

The current paper may be edited by its author; the hashes identify the exact
read version. Existing provenance/paper_snapshot remains untouched.
