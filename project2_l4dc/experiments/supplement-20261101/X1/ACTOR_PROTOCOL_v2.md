# X1 actor protocol v2 — mandatory R1/R2/R3 revision

Supersedes only the actor calibration of protocolv1, following Claude's01:20
REVISE. CE is separately ACCEPTED and has its own formal-only approval receipt.
No formal NPG/PI is authorized until this revised resolved protocol is ACCEPTED.

R1: p0_bar is the maximum ||P_K0|| over all8 formal systems and9 distinct m/null
cases. This is an arm-independent initialization certificate, explicitly permitted
by the reviewer as the paper's supplied bound. Formal learning outputs/performance
are never read for calibration. With mu_plus=1 and ||B||=1, eta=1/(1+2*p0_bar).
This one eta is fixed and does not change with batch-base candidates.

R2: Using **only pilot systems9001/9002** and all five m with both null variants
(deduplicating m=r), run population exact-gradient NPG and population full-greedy
PI as oracle calibration, not sample-learning evidence. Select the first T in
{64,96,128,192} at which NPG relative gap<=.05 for every pilot plant. PI uses8
updates if all satisfy.05, otherwise12; if either grid has no qualifying T,
publish the negative result and keep actor formal closed for reviewer resolution.

R3: With that eta and T fixed, test bases2048/8192/32768 in ascending order,
blocks_t=ceil(base*2^(t/16)); same noise pairing, H32,16 pulse burn blocks and
one baseline per stage. Select the first base with **dense** stable on every
pilot run and dense endpoint relative median<=.5, separately checking each
algorithm. Use the same selected budget for both algorithms if joint acceptance
is sought; do not change eta together with the base. Exact PI/NPG primitive-budget
parity remains as in protocolv1. If the measured complete workload cannot fit
the remaining200-SU ceiling, report and stop actor X1 instead of shrinking seeds,
silently changing the geometric schedule or submitting an unbounded job.

The old calibration0/1 trials are retained as superseded pilot evidence only;
they cannot authorize actor formal runs. Kernel checks and all negative results
remain preserved. No earlier frozen release/result is rewritten.

The R1/R2 pilot requests at most10 single-core minutes,2GiB (0.166667SU upper
bound). No additional R3 job is submitted until the population grid qualifies
and a measured remaining-cost plan is within the global cap. The explicit
ACCEPTED requirement remains; the60-minute exception is not used.
