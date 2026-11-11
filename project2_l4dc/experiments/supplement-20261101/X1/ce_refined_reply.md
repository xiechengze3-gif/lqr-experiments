Scope: X1 CE saved-data follow-up for Review01:55 C1-C3; **no learning reruns or new training transitions**.

New immutable `X1/report-ce-v2/` contains PNG+SVG panels `normalized_N4096`, `normalized_N8192`, `ce_main_v2`, and normalized_records/statistics.csv. C1 computes N*D/v_star on each individual output first, then takes medians/IQR; v_star=||Pstar(A-BKstar)||F² from the matching system certificate. C2 titles give exact regression N, burn-inclusive total, and actual failure denominators. C3 shows null.25 and zero-null side by side at both N. Original `report-ce` is preserved.

| N | null | m-r | Method | ND/vstar median [IQR] | Stable |
|---:|---:|---:|---|---|---:|
| 4096 | 0.0 | 2 | dense | 3.1386 [1.7411, 5.951] | 31/32 |
| 4096 | 0.0 | 2 | truncated | 0.034578 [0.018277, 0.063532] | 31/32 |
| 8192 | 0.0 | 2 | dense | 2.8468 [1.8967, 7.7627] | 32/32 |
| 8192 | 0.0 | 2 | truncated | 0.029093 [0.0083728, 0.104] | 32/32 |
| 4096 | 0.0 | 4 | dense | 10.679 [7.8709, 17.215] | 32/32 |
| 4096 | 0.0 | 4 | truncated | 0.14128 [0.06338, 0.35342] | 32/32 |
| 8192 | 0.0 | 4 | dense | 12.956 [5.4474, 20.043] | 32/32 |
| 8192 | 0.0 | 4 | truncated | 0.12209 [0.061662, 0.31285] | 32/32 |
| 4096 | 0.0 | 7 | dense | 18.21 [12.819, 25.161] | 32/32 |
| 4096 | 0.0 | 7 | truncated | 0.17383 [0.10963, 0.49357] | 32/32 |
| 8192 | 0.0 | 7 | dense | 20.568 [11.836, 31.056] | 32/32 |
| 8192 | 0.0 | 7 | truncated | 0.20356 [0.11636, 0.44593] | 32/32 |
| 4096 | 0.0 | 10 | dense | 28.265 [19.596, 45.537] | 31/32 |
| 4096 | 0.0 | 10 | truncated | 0.40046 [0.14483, 0.97332] | 31/32 |
| 8192 | 0.0 | 10 | dense | 31.307 [20.514, 46.058] | 32/32 |
| 8192 | 0.0 | 10 | truncated | 0.40003 [0.17305, 0.74377] | 32/32 |
| 4096 | 0.25 | 2 | dense | 3.1471 [1.7057, 5.8751] | 31/32 |
| 4096 | 0.25 | 2 | truncated | 0.034347 [0.018333, 0.064019] | 31/32 |
| 8192 | 0.25 | 2 | dense | 2.8214 [1.9112, 7.7707] | 32/32 |
| 8192 | 0.25 | 2 | truncated | 0.028886 [0.0083671, 0.10368] | 32/32 |
| 4096 | 0.25 | 4 | dense | 10.774 [7.8578, 17.457] | 32/32 |
| 4096 | 0.25 | 4 | truncated | 0.14154 [0.063198, 0.35152] | 32/32 |
| 8192 | 0.25 | 4 | dense | 13.028 [5.4817, 20.053] | 32/32 |
| 8192 | 0.25 | 4 | truncated | 0.1213 [0.061512, 0.31242] | 32/32 |
| 4096 | 0.25 | 7 | dense | 18.364 [12.834, 25.357] | 32/32 |
| 4096 | 0.25 | 7 | truncated | 0.17298 [0.10839, 0.48768] | 32/32 |
| 8192 | 0.25 | 7 | dense | 20.592 [11.905, 31.217] | 32/32 |
| 8192 | 0.25 | 7 | truncated | 0.20355 [0.11577, 0.44649] | 32/32 |
| 4096 | 0.25 | 10 | dense | 28.684 [19.634, 45.332] | 31/32 |
| 4096 | 0.25 | 10 | truncated | 0.40135 [0.14453, 0.97402] | 31/32 |
| 8192 | 0.25 | 10 | dense | 31.365 [20.588, 46.024] | 32/32 |
| 8192 | 0.25 | 10 | truncated | 0.40185 [0.17334, 0.74698] | 32/32 |

N4096 failures remain5/288 per method (nonzero-null2/128, zero-null3/160); N8192 has0/288 per method. All15 failed formal outputs remain in raw/failure-inclusive summaries. The normalized dense medians increase with redundant dimension, while this finite grid is not a certification of a universal linear coefficient or theoretical sample constants.

Source/config hashes: `packages/supplement-20261101-ce-refine-v9.manifest.json`; retrieval `deliveries/delivery-x1-ce-refined-population-v1.verified.json`. Both graph types were visually inspected. All178 protected earlier files remain byte-identical.
