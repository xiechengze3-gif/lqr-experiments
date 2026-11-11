Scope: **X1 NPG/PI revised actor PILOT** (CE has a separate accepted formal/report).
Review01:55 explicitly ACCEPTED actor protocolv2, including conditional formal
permission once R3 qualifies and the measured plan fits the cap.

Resolved R1/R2: p0_bar55.05176231884344, eta0.009000614546307517,
NPG96 updates, PI8 full-greedy updates, H32,16 pulse-burn blocks plus baseline.
First R3 base2048 qualifies:18 configurations from2 independent pilot plants
(all5 m/both null variants, m=r deduplicated); dense NPG18/18 and PI18/18
whole paths stable; endpoint relative medians0.1204312868 and0.3982230712<=.5.
Truncated paths are also18/18 stable but were NOT the calibration criterion.

Each arm of either algorithm has93,308,928 actual primitive transitions,
including all burn/baseline and separately counted absorbing-failure padding.
Config `configs/X1_actor_base2048_v2.json`, SHA256
`611a168228198aa5d6e279b0895fc7a3a494bb4f47042c64ae5854eca3c38c99`.
Approval and resolved source hashes: `X1/ACCEPTED_ACTOR.json`.

Measured maximum complete paired-run times: NPG75.606056s, PI71.856636s;
peak pilot RSS132,681,728 bytes, all billing1. For each formal system/seed bundle,
9*(75.606056+71.856636)*1.30+60=1785.3s ->30min at1 core/2GiB.
32 bundles give16SU cumulative requested upper bound for formal actors, within
the200SU global cap. Formal outputs/candidates and exact sampled-transition
counters will be audited; failed candidates and all negative results are kept.

Old coupled-eta/batch trials remain superseded pilot evidence, including both
dense PI failures in the original first ladder entry. They were not relabeled
as formal or deleted. No actor formal data were used in resolving these parameters.
