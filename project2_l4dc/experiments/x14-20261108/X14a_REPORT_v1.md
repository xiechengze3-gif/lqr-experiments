# X14a report

Family S, n = m = 24, K0 = 0, order-2 truncation, H = 16, exploration variance 1 and 16 burn blocks plus one baseline per stage. NPG uses 16 updates with η = 0.2 and PI uses eight full greedy updates with PSD projection and joint compression. All cells use eight systems and four paired seeds.

The preregistered α = 0.02 cell has full-rank B and tail energy 0.0088 at k = 2. This is within the 0.01 tail-energy criterion. Gap and stability observations are descriptive, and the pilot calibration does not certify the theorem’s sufficient sampling bounds.
## Largest registered budget


| α | Algorithm | Both stable | Dense / truncated [95% CI] | Interval vs 1 |
| --- | --- | --- | --- | --- |
| 0.02 | NPG | 32/32 | 3.323 [3.004, 3.628] | above 1 |
| 0.02 | PI | 32/32 | 13.29 [12.58, 14.14] | above 1 |

## Nine-rung paired comparisons

Budgets are indexed by j in Ncal / 2^j. Primitive transitions are per arm and include burn-in and baseline. Gap cells show median [Q1, Q3]. Ratio cells show the median with the registered 95% system-cluster interval. Stable counts use all 32 pairs. Infinity represents failed outputs.

### α = 0.02, NPG

| j | Transitions | Dense gap | Truncated gap | Dense relative gap | Truncated relative gap | Stable D / T / both | Both-stable ratio | Failure-inclusive ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 189475712 | 0.05789 [0.0538, 0.06246] | 0.01744 [0.01623, 0.01977] | 0.2154 [0.2003, 0.2466] | 0.06733 [0.05662, 0.08005] | 32 / 32 / 32 | 3.323 [3.004, 3.628] | 3.323 [3.004, 3.628] |
| 1 | 94740080 | 0.1146 [0.11, 0.1268] | 0.04085 [0.03808, 0.04417] | 0.4535 [0.4117, 0.499] | 0.1553 [0.1377, 0.1789] | 32 / 32 / 32 | 2.896 [2.693, 2.996] | 2.896 [2.693, 2.996] |
| 2 | 47372272 | 0.2306 [0.2127, 0.2591] | 0.08584 [0.07893, 0.09051] | 0.8929 [0.8231, 1.05] | 0.3275 [0.2919, 0.3772] | 32 / 32 / 32 | 2.787 [2.624, 2.876] | 2.787 [2.624, 2.876] |
| 3 | 23688352 | 0.4815 [0.4461, 0.5282] | 0.169 [0.1562, 0.1813] | 1.796 [1.669, 2.031] | 0.6407 [0.5538, 0.7636] | 32 / 32 / 32 | 2.832 [2.677, 3.115] | 2.832 [2.677, 3.115] |
| 4 | 11846384 | 1 [0.9295, 1.096] | 0.313 [0.2987, 0.3533] | 3.79 [3.504, 4.263] | 1.238 [1.134, 1.389] | 32 / 32 / 32 | 3.12 [3.046, 3.224] | 3.12 [3.046, 3.224] |
| 5 | 5925440 | 2.246 [2.072, 2.354] | 0.6216 [0.5578, 0.6995] | 8.558 [7.796, 9.256] | 2.405 [2.196, 2.575] | 32 / 32 / 32 | 3.571 [3.35, 3.707] | 3.571 [3.35, 3.707] |
| 6 | 2964976 | 6.023 [5.442, 6.503] | 1.275 [1.175, 1.457] | 22.58 [20.92, 25.49] | 5.093 [4.441, 5.517] | 32 / 32 / 32 | 4.49 [4.376, 4.837] | 4.49 [4.376, 4.837] |
| 7 | 1484704 | ∞ [∞, ∞] | 2.901 [2.576, 3.118] | ∞ [∞, ∞] | 11.21 [10.08, 12.55] | 0 / 32 / 0 | — | ∞ [∞, ∞] |
| 8 | 744608 | ∞ [∞, ∞] | 33.7 [13.98, ∞] | ∞ [∞, ∞] | 134.2 [74.09, ∞] | 0 / 20 / 0 | — | ∞ [∞, ∞] |

- Above 1 at j = 0, 1, 2, 3, 4, 5, 6.
- Below 1 at j = none.
- Contains 1 at j = none.
- Unavailable at j = 7, 8.


### α = 0.02, PI

| j | Transitions | Dense gap | Truncated gap | Dense relative gap | Truncated relative gap | Stable D / T / both | Both-stable ratio | Failure-inclusive ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 189475712 | 0.1237 [0.1122, 0.1329] | 0.009272 [0.007866, 0.01021] | 0.4597 [0.4219, 0.5101] | 0.03526 [0.03041, 0.04043] | 32 / 32 / 32 | 13.29 [12.58, 14.14] | 13.29 [12.58, 14.14] |
| 1 | 94740080 | 0.2355 [0.2206, 0.2612] | 0.01525 [0.01318, 0.01672] | 0.8977 [0.8242, 1.01] | 0.05603 [0.05258, 0.06381] | 32 / 32 / 32 | 15.94 [15.62, 16.55] | 15.94 [15.62, 16.55] |
| 2 | 47372272 | 0.4914 [0.462, 0.5154] | 0.02728 [0.02268, 0.03073] | 1.846 [1.654, 2.043] | 0.1041 [0.09197, 0.1118] | 32 / 32 / 32 | 18.23 [17.16, 19.16] | 18.23 [17.16, 19.16] |
| 3 | 23688352 | 0.9787 [0.921, 1.054] | 0.05055 [0.04366, 0.05799] | 3.76 [3.382, 4.159] | 0.1953 [0.1641, 0.2318] | 32 / 32 / 32 | 19.54 [18.32, 20.7] | 19.54 [18.32, 20.7] |
| 4 | 11846384 | ∞ [46.15, ∞] | 0.0907 [0.08201, 0.1149] | ∞ [234.9, ∞] | 0.3748 [0.2848, 0.517] | 11 / 32 / 11 | 162.8 [89.12, 650.4] | ∞ [863, ∞] |
| 5 | 5925440 | ∞ [∞, ∞] | 0.1789 [0.1513, 0.2194] | ∞ [∞, ∞] | 0.7036 [0.5893, 0.8511] | 0 / 32 / 0 | — | ∞ [∞, ∞] |
| 6 | 2964976 | ∞ [∞, ∞] | 0.367 [0.287, 0.4049] | ∞ [∞, ∞] | 1.303 [1.161, 1.609] | 0 / 32 / 0 | — | ∞ [∞, ∞] |
| 7 | 1484704 | ∞ [∞, ∞] | 0.6982 [0.6082, 0.8603] | ∞ [∞, ∞] | 2.764 [2.31, 3.214] | 0 / 32 / 0 | — | ∞ [∞, ∞] |
| 8 | 744608 | ∞ [∞, ∞] | 1.042 [0.7832, 1.454] | ∞ [∞, ∞] | 3.894 [3.207, 5.503] | 0 / 32 / 0 | — | ∞ [∞, ∞] |

- Above 1 at j = 0, 1, 2, 3, 4.
- Below 1 at j = none.
- Contains 1 at j = none.
- Unavailable at j = 5, 6, 7, 8.

## Grace ledger


| Item | Stage | Job | Allocations | Wall limit (min) | Actual SU | Requested upper SU | Exposure at submission SU |
| --- | --- | --- | --- | --- | --- | --- | --- |
| a | formal | 20441639 | 64 | 12 | 10.235833 | 12.800000 | 17.467778 |
| a | pilot | 20440067 | 4 | 15 | 0.667778 | 1.000000 | 5.000000 |
| a | report | 20442305 | 1 | 10 | 0.009444 | 0.166667 | 15.070278 |

Settled actual 10.913056 SU. Outstanding upper 0.000000 SU. Exposure including the 4 SU report reserve 14.913056 SU. Historical sum of requests 13.966667 SU includes released reservations.

