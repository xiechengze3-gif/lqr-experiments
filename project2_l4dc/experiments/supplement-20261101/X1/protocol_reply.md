Protocol: `experiments/supplement-20261101/X1/PROTOCOL_v1.md`.
Config: `configs/X1_v1.json`; exact source hashes: `release-manifest-X1-v1.json`.

The new generator uses independent A and B random streams, rho(A)=1.05, varied
stable eigenvalues (not rotation-only repeats), and a stability-only Schur-mode
pole correction with no cost/optimum input. Formal cells use8 independent systems
x4 sampling seeds; pilot systems/seeds are disjoint. CE uses exploration during
burn; NPG/PI use pulse burn, baseline and adjacent-return Stein estimates.

Please explicitly review the two necessary X1 clarifications before ACCEPTED:
- P0/J0 matching holds for zero-null across all five m, and .25-null across m>r;
  m=r is an explicitly labeled zero-null baseline, not a matched-cost nonzero-null point.
- After an unstable output, later outputs remain absorbing failures while discarded
  observations under K0 fill the fixed assigned budget, preserving actual transition
  parity. Padding is not policy recovery and is separately counted.

Dense-only calibration uses the predeclared ladder; no formal seed or truncated
performance selects parameters. Fixed practical scheduling is not claimed to
numerically certify unknown theorem constants. The resolved post-pilot config/hash
will also be published before formal acceptance.

Initial pilot limits: invariants5min + CE10min + actor calibration0 30min,
single-core/2GiB each, total requested bound0.75SU. No formal array is authorized
without ACCEPTED, measured CPU/memory and a plan within the200SU whole-night cap.
At this protocol publication no new job has yet been submitted.
