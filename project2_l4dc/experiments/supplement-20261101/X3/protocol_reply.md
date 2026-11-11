Scope: X3 full-rank protocol, with ready-to-run **CE pilot only**. Prepared in
parallel with accepted X1 actor execution as Review01:55 requested. No X3 formal
approval is inferred from X1; the60-minute exception is not used.

`X3/PROTOCOL_v1.md`, `configs/X3_v1.json`, `release-manifest-X3-v1.json`.
CE: n16/32 x smooth/two-level/flat,18 prefixes, the fixed-k grid plus BOTH
adaptive_paper and split-half variants. Formal8 independent systems x4 seeds;
disjoint pilot2 systems x2 seeds. Same accepted independent unstable generator,
one continuous exploration-burn OLS trajectory and exact same-prefix fits.

C5 is calibrated once from the maximum normalized **dense Bhat estimation error**
on pilot fits, times1.25, not from favorable adaptive control performance. Exact
full/half OLS solutions are captured so the adaptive pilot can reuse the SAME fits
after the global constant is selected; no trajectory replay or extra samples.
The constant and resolved config/hash will be supplied for formal acceptance.
It is a pilot-calibrated paper-form threshold, not a certified theoretical radius.

Pilot bound:24 trajectories in one single-core2GiB job,max15min,0.25SU upper.
The implementation preserves k0 DARE failures as diagnostics outside r>=1,
all stable denominators and the flat-spectrum negative control. Certificates
contain tau_k²/beta_k; these are not mislabeled as every current Z_K tail.

NPG n12,k1/2/4/6/12 at3 budgets is specified for subsequent dense-only calibration,
with measured resource/collector checks and resolved hashes required before its
formal run. No uncalibrated actor grid is submitted by this CE pilot.
