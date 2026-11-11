Scope: revised X1 actor protocol only. CE remains ACCEPTED and its formal-only
array20358790 has been submitted (32 bundles, total request bound1.6SU).

I have read and implemented every R1–R4 instruction from Review01:20:
`X1/ACTOR_PROTOCOL_v2.md`; frozen population calibration code/config hashes in
`release-manifest-X1-actor-v5.json`.

R1 uses eta=1/(1+2*p0_bar), one arm-independent maximum initial-P certificate
over the formal plants, with no formal learning output/performance used.
R2 checks population NPG T={64,96,128,192} on all pilot plants for relative.05,
and population PI8/12. R3 then fixes eta/T and selects only the batch base from
the dense stability plus median-relative<=.5 criterion. If T or cost does not
qualify within the cap, I will report and stop that actor branch.

Old coupled-eta/budget calibration0/1 results remain preserved but are superseded;
they cannot be promoted to formal evidence. The original scientific engine is
unchanged. Pulse-burn/baseline/pairing/padding remain exactly as accepted.
No formal NPG/PI has been submitted. The new R1/R2 pilot is bounded at10
single-core minutes (0.166667SU), and resolved values/hashes will be reported
for explicit acceptance before any actor formal run.
