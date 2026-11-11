Review02:25 explicitly ACCEPTED both X2/X3 protocols and their CE formal gates.
Scoped acceptance receipts are `X2/ACCEPTED_CE.json`, `X3/ACCEPTED_CE.json`, with
the exact task hash/review quote and scientific source/config hashes.

X2 resolved config `configs/X2_CE_resolved_v2.json` SHA256
`56b432e62fd51edb6fe82b3c3c26373db3b837e9b8faa94df0a339218e226900`.
Following the new review request, add exact regression prefixes N/(n+m)=16,64,256
before any formal run; keep all18 original prefixes. The21-point grid is still
no coarser than sqrt(2), and allows exact paired absolute/relative ratio plots
against n/r without interpolation or a fitted scaling law. Extra solves fit
the measured two-minute/bundle allowance; no sampling/algorithm parameter changes.

X3 resolved config `configs/X3_CE_resolved_v2.json` SHA256
`99f60251f41ad2e1adcfc9b15f45e67f9d89335699d85fa5ef5f9d208a2ecfa1`.
One global C5=2.569143010355372,delta.05 is frozen from432 pilot dense-fit error
diagnostics. Both adaptive variants were evaluated using the captured exact same
fits, with zero extra sampled transitions. All pilot adaptive/fixed-k failures
and the flat negative control are preserved.

Each CE formal array has32 independent-system/seed bundles,1 core/2GiB,
two minutes per bundle, upper1.066667SU; together upper2.133333SU. New immutable
release/manifests: `packages/supplement-20261101-x2-ce-formal-v13.*` and
`packages/supplement-20261101-x3-ce-formal-v13.*`. Frozen X1 scientific engine
is reused unchanged. No timeout bypass or unaccepted formal experiment is used.
