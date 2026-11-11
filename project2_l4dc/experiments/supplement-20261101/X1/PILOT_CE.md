# X1 CE pilot complete; actors separately under REVISE

Scope of this pilot completion: **CE only**. Claude's 01:20 CDT review explicitly
ACCEPTS X1-CE and requests its formal array; it REVISES the actor calibration.

- Invariant pilot20358741 completed in29 seconds, billed1 core:0.008056 SU.
- CE pilot20358752 completed in12 seconds:0.003333 SU. All8 data trajectories,
  2 regression prefixes and3 arms (48 evaluated outputs) were stable.
- Kernel/learner checks20358777 completed in4 seconds and passed sequential-state,
  pulse-return, observed CE triples, full-rank identity and factory checks.
- Prescribed null/m=r invariant exception is now explicitly ACCEPTED by Claude.
- Failure-padding rule and overlap diagnostics are also explicitly ACCEPTED.
- Earlier launch20358732 failed at the checksum guard before science (CRLF
  transfer list), elapsed0 seconds. It is retained in the cumulative request ledger.

CE scientific engine/config hashes remain those of release-manifest-X1-v1.json.
The formal wrapper adds evaluation-candidate archives, including unstable gains,
without changing observations, learner calls, RNG or evaluator values.

Formal CE plan:32 system×sampling bundles,9 distinct null/m cases per bundle;
288 continuous data trajectories, each with2 prefixes and3 evaluated methods.
m=r is physically identical between null variants and sampled only once.
Timing bound:9×the maximum complete CE pilot time10.019494s, multiplied by1.30,
plus30s startup =>147.23s; round to3min/bundle,1 core/2GiB =>1.6SU upper request.
All primitive transitions include512 exploration burn; N=4096/8192.

Actor trials under the old rule remain pilot evidence only. They cannot authorize
formal NPG/PI. Revised R1/R2/R3 calibration and its resolved hash are pending.
