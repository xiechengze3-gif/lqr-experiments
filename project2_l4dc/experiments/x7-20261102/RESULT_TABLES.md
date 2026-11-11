# X7 compact saved-CSV tables

Ratios are medians of paired dense/arm gaps, with 5,000 common-draw system-cluster bootstrap samples; 95% pointwise intervals. Post hoc best fixed minimizes the full-32 median absolute gap and includes dense; its interval is descriptive and does not adjust for selecting the order.

| n | Spectrum | N | Post hoc k | Dense relative gap | Post hoc relative gap; ratio [CI] | Paper relative gap; ratio [CI] | Split relative gap; ratio [CI] | Sensitivity C=.5 relative gap; ratio [CI] | Sensitivity C=1 relative gap; ratio [CI] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 24 | geometric | 192 | 1 | 4.405 | 1.089; 4.059 [3.879, 4.193] | 1; 4.405 [3.947, 4.736] | 1.087; 3.93 [3.776, 4.181] | 4.046; 1.077 [1.073, 1.083] | 2.708; 1.565 [1.536, 1.626] |
| 24 | geometric | 768 | 4 | 0.8523 | 0.4072; 2.066 [2.001, 2.124] | 0.5312; 1.588 [1.534, 1.642] | 0.424; 1.97 [1.895, 2.084] | 0.8038; 1.059 [1.047, 1.068] | 0.5511; 1.518 [1.475, 1.594] |
| 24 | geometric | 3072 | 6 | 0.2011 | 0.1256; 1.618 [1.559, 1.683] | 0.1654; 1.215 [1.163, 1.314] | 0.1254; 1.585 [1.539, 1.627] | 0.1911; 1.046 [1.042, 1.051] | 0.1448; 1.374 [1.327, 1.414] |
| 24 | geometric | 12288 | 8 | 0.048 | 0.03568; 1.344 [1.312, 1.455] | 0.04533; 1.046 [1.018, 1.097] | 0.03568; 1.33 [1.278, 1.446] | 0.04598; 1.038 [1.034, 1.05] | 0.03756; 1.266 [1.255, 1.321] |
| 24 | geometric | 49152 | 12 | 0.01227 | 0.01037; 1.151 [1.137, 1.17] | 0.01431; 0.8532 [0.8292, 0.8794] | 0.01033; 1.174 [1.128, 1.218] | 0.01176; 1.033 [1.027, 1.037] | 0.01039; 1.168 [1.149, 1.195] |
| 24 | geometric | 196608 | 12 | 0.003066 | 0.002795; 1.101 [1.094, 1.111] | 0.004023; 0.7793 [0.7193, 0.858] | 0.002817; 1.094 [1.077, 1.111] | 0.002937; 1.028 [1.023, 1.038] | 0.002748; 1.103 [1.089, 1.106] |
| 24 | polynomial | 192 | 1 | 5.117 | 1.104; 4.641 [4.603, 4.923] | 1; 5.117 [4.624, 5.479] | 1.056; 4.67 [4.615, 5.007] | 4.711; 1.075 [1.063, 1.085] | 3.206; 1.56 [1.511, 1.589] |
| 24 | polynomial | 768 | 2 | 0.9892 | 0.5598; 1.739 [1.712, 1.794] | 0.6797; 1.466 [1.424, 1.485] | 0.5867; 1.668 [1.604, 1.715] | 0.9608; 1.033 [1.027, 1.04] | 0.7994; 1.312 [1.222, 1.364] |
| 24 | polynomial | 3072 | 24 | 0.2334 | 0.2334; 1 (self) | 0.3276; 0.712 [0.6796, 0.7832] | 0.2463; 0.9296 [0.9122, 0.9556] | 0.2403; 0.965 [0.9631, 0.9674] | 0.2454; 0.9443 [0.9332, 0.9698] |
| 24 | polynomial | 12288 | 24 | 0.05649 | 0.05649; 1 (self) | 0.1506; 0.3775 [0.3672, 0.3875] | 0.08845; 0.6383 [0.6244, 0.6528] | 0.06046; 0.9366 [0.9154, 0.9435] | 0.0758; 0.7581 [0.7309, 0.7654] |
| 24 | polynomial | 49152 | 24 | 0.01428 | 0.01428; 1 (self) | 0.05749; 0.2512 [0.2408, 0.2677] | 0.01911; 0.7149 [0.6619, 0.7691] | 0.01428; 1 [1, 1] | 0.01579; 0.9128 [0.8596, 1] |
| 24 | polynomial | 196608 | 24 | 0.003542 | 0.003542; 1 (self) | 0.00703; 0.4903 [0.4551, 0.5587] | 0.003542; 1 [1, 1] | 0.003542; 1 [1, 1] | 0.003542; 1 [1, 1] |
| 48 | geometric | 384 | 1 | 8.457 | 1.039; 8.122 [7.886, 8.456] | 1; 8.457 [8.199, 9.105] | 1.039; 8.064 [7.863, 8.501] | 7.842; 1.083 [1.08, 1.085] | 5.119; 1.682 [1.627, 1.718] |
| 48 | geometric | 1536 | 4 | 1.633 | 0.4134; 3.966 [3.894, 4.018] | 0.52; 3.206 [3.156, 3.272] | 0.4272; 3.794 [3.593, 3.961] | 1.522; 1.071 [1.067, 1.076] | 0.9593; 1.723 [1.691, 1.745] |
| 48 | geometric | 6144 | 6 | 0.3887 | 0.133; 2.988 [2.828, 3.071] | 0.1728; 2.291 [2.166, 2.353] | 0.1356; 2.83 [2.764, 2.904] | 0.3647; 1.063 [1.062, 1.067] | 0.236; 1.66 [1.609, 1.685] |
| 48 | geometric | 24576 | 8 | 0.09585 | 0.03871; 2.435 [2.408, 2.507] | 0.05041; 1.914 [1.851, 2.009] | 0.04014; 2.355 [2.292, 2.392] | 0.09069; 1.063 [1.058, 1.066] | 0.05938; 1.622 [1.571, 1.653] |
| 48 | geometric | 98304 | 12 | 0.02322 | 0.01262; 1.875 [1.816, 1.895] | 0.01416; 1.643 [1.567, 1.73] | 0.01122; 2.106 [2.042, 2.153] | 0.02198; 1.059 [1.055, 1.065] | 0.01502; 1.591 [1.549, 1.632] |
| 48 | geometric | 393216 | 12 | 0.005871 | 0.003209; 1.811 [1.786, 1.853] | 0.003945; 1.488 [1.469, 1.571] | 0.003244; 1.801 [1.784, 1.84] | 0.005547; 1.059 [1.056, 1.062] | 0.00396; 1.482 [1.459, 1.515] |
| 48 | polynomial | 384 | 1 | 9.566 | 1.063; 9.199 [8.883, 9.62] | 1; 9.566 [9.305, 10.44] | 1.033; 9.397 [8.883, 9.629] | 8.891; 1.081 [1.076, 1.086] | 5.866; 1.655 [1.609, 1.696] |
| 48 | polynomial | 1536 | 3 | 1.877 | 0.5559; 3.304 [3.238, 3.338] | 0.6563; 2.81 [2.751, 2.921] | 0.6094; 3.025 [2.973, 3.112] | 1.77; 1.06 [1.056, 1.063] | 1.196; 1.548 [1.527, 1.563] |
| 48 | polynomial | 6144 | 6 | 0.4394 | 0.2743; 1.603 [1.545, 1.647] | 0.3522; 1.285 [1.236, 1.321] | 0.2814; 1.544 [1.527, 1.567] | 0.426; 1.028 [1.02, 1.034] | 0.3584; 1.228 [1.208, 1.242] |
| 48 | polynomial | 24576 | 48 | 0.1076 | 0.1076; 1 (self) | 0.1761; 0.6237 [0.607, 0.6405] | 0.1176; 0.9078 [0.8981, 0.9175] | 0.1112; 0.9694 [0.9682, 0.9705] | 0.1173; 0.9224 [0.9104, 0.9262] |
| 48 | polynomial | 98304 | 48 | 0.02612 | 0.02612; 1 (self) | 0.07491; 0.3562 [0.3455, 0.3654] | 0.04306; 0.6203 [0.6126, 0.6227] | 0.02787; 0.9425 [0.9379, 0.9474] | 0.03568; 0.7365 [0.7301, 0.746] |
| 48 | polynomial | 393216 | 48 | 0.006656 | 0.006656; 1 (self) | 0.02646; 0.2476 [0.2453, 0.2556] | 0.009599; 0.6974 [0.6595, 0.7113] | 0.006656; 1 [1, 1] | 0.006964; 0.9357 [0.9234, 1] |


## Adaptive order (median [IQR]; zero count)


| n | Spectrum | N | Rule | Order | Zero/32 | Threshold median |
| --- | --- | --- | --- | --- | --- | --- |
| 24 | geometric | 192 | adaptive_paper | 0 [0, 0] | 32 | 1.324 |
| 24 | geometric | 192 | adaptive_split | 1 [1, 2] | 2 | 1.003 |
| 24 | geometric | 192 | sensitivity_C0p5 | 14.5 [14, 15] | 0 | 0.2577 |
| 24 | geometric | 192 | sensitivity_C1p0 | 7 [7, 8] | 0 | 0.5154 |
| 24 | geometric | 768 | adaptive_paper | 2 [2, 2] | 0 | 0.662 |
| 24 | geometric | 768 | adaptive_split | 4 [4, 5] | 0 | 0.3572 |
| 24 | geometric | 768 | sensitivity_C0p5 | 15 [14.75, 16] | 0 | 0.1288 |
| 24 | geometric | 768 | sensitivity_C1p0 | 7 [7, 8] | 0 | 0.2577 |
| 24 | geometric | 3072 | adaptive_paper | 4 [4, 4] | 0 | 0.331 |
| 24 | geometric | 3072 | adaptive_split | 6 [6, 7] | 0 | 0.1694 |
| 24 | geometric | 3072 | sensitivity_C0p5 | 15 [15, 16] | 0 | 0.06442 |
| 24 | geometric | 3072 | sensitivity_C1p0 | 8 [8, 9] | 0 | 0.1288 |
| 24 | geometric | 12288 | adaptive_paper | 6 [6, 6] | 0 | 0.1655 |
| 24 | geometric | 12288 | adaptive_split | 8 [8, 8] | 0 | 0.08403 |
| 24 | geometric | 12288 | sensitivity_C0p5 | 16 [15, 16] | 0 | 0.03221 |
| 24 | geometric | 12288 | sensitivity_C1p0 | 10 [9, 10] | 0 | 0.06442 |
| 24 | geometric | 49152 | adaptive_paper | 8 [8, 8] | 0 | 0.08275 |
| 24 | geometric | 49152 | adaptive_split | 10 [10, 10.25] | 0 | 0.0416 |
| 24 | geometric | 49152 | sensitivity_C0p5 | 16.5 [16, 17] | 0 | 0.01611 |
| 24 | geometric | 49152 | sensitivity_C1p0 | 11.5 [11, 12] | 0 | 0.03221 |
| 24 | geometric | 196608 | adaptive_paper | 10 [9, 10] | 0 | 0.04137 |
| 24 | geometric | 196608 | adaptive_split | 12 [12, 12] | 0 | 0.02071 |
| 24 | geometric | 196608 | sensitivity_C0p5 | 17 [17, 18] | 0 | 0.008053 |
| 24 | geometric | 196608 | sensitivity_C1p0 | 13 [13, 13] | 0 | 0.01611 |
| 24 | polynomial | 192 | adaptive_paper | 0 [0, 0] | 32 | 1.324 |
| 24 | polynomial | 192 | adaptive_split | 1 [1, 1] | 3 | 1.007 |
| 24 | polynomial | 192 | sensitivity_C0p5 | 14 [14, 15] | 0 | 0.2577 |
| 24 | polynomial | 192 | sensitivity_C1p0 | 7 [7, 7.25] | 0 | 0.5154 |
| 24 | polynomial | 768 | adaptive_paper | 1 [1, 1] | 0 | 0.662 |
| 24 | polynomial | 768 | adaptive_split | 4 [4, 4] | 0 | 0.3578 |
| 24 | polynomial | 768 | sensitivity_C0p5 | 15 [15, 16] | 0 | 0.1288 |
| 24 | polynomial | 768 | sensitivity_C1p0 | 8 [7, 8] | 0 | 0.2577 |
| 24 | polynomial | 3072 | adaptive_paper | 3 [3, 3] | 0 | 0.331 |
| 24 | polynomial | 3072 | adaptive_split | 8 [7.75, 8] | 0 | 0.1692 |
| 24 | polynomial | 3072 | sensitivity_C0p5 | 18 [17, 18] | 0 | 0.06442 |
| 24 | polynomial | 3072 | sensitivity_C1p0 | 11 [11, 12] | 0 | 0.1288 |
| 24 | polynomial | 12288 | adaptive_paper | 6 [6, 6] | 0 | 0.1655 |
| 24 | polynomial | 12288 | adaptive_split | 14 [13, 14] | 0 | 0.08409 |
| 24 | polynomial | 12288 | sensitivity_C0p5 | 21 [21, 22] | 0 | 0.03221 |
| 24 | polynomial | 12288 | sensitivity_C1p0 | 17 [16, 17] | 0 | 0.06442 |
| 24 | polynomial | 49152 | adaptive_paper | 12 [12, 13] | 0 | 0.08275 |
| 24 | polynomial | 49152 | adaptive_split | 22 [21, 22] | 0 | 0.0416 |
| 24 | polynomial | 49152 | sensitivity_C0p5 | 24 [24, 24] | 0 | 0.01611 |
| 24 | polynomial | 49152 | sensitivity_C1p0 | 23 [23, 24] | 0 | 0.03221 |
| 24 | polynomial | 196608 | adaptive_paper | 22 [22, 23] | 0 | 0.04137 |
| 24 | polynomial | 196608 | adaptive_split | 24 [24, 24] | 0 | 0.0207 |
| 24 | polynomial | 196608 | sensitivity_C0p5 | 24 [24, 24] | 0 | 0.008053 |
| 24 | polynomial | 196608 | sensitivity_C1p0 | 24 [24, 24] | 0 | 0.01611 |
| 48 | geometric | 384 | adaptive_paper | 0 [0, 0] | 32 | 1.304 |
| 48 | geometric | 384 | adaptive_split | 1 [1, 1] | 2 | 1.059 |
| 48 | geometric | 384 | sensitivity_C0p5 | 29 [28, 30] | 0 | 0.2539 |
| 48 | geometric | 384 | sensitivity_C1p0 | 13 [13, 14] | 0 | 0.5077 |
| 48 | geometric | 1536 | adaptive_paper | 2 [2, 2] | 0 | 0.6522 |
| 48 | geometric | 1536 | adaptive_split | 4 [4, 5] | 0 | 0.3697 |
| 48 | geometric | 1536 | sensitivity_C0p5 | 28 [28, 28] | 0 | 0.1269 |
| 48 | geometric | 1536 | sensitivity_C1p0 | 12 [11.75, 12] | 0 | 0.2539 |
| 48 | geometric | 6144 | adaptive_paper | 4 [4, 4] | 0 | 0.3261 |
| 48 | geometric | 6144 | adaptive_split | 7 [6, 7] | 0 | 0.1756 |
| 48 | geometric | 6144 | sensitivity_C0p5 | 28 [28, 29] | 0 | 0.06347 |
| 48 | geometric | 6144 | sensitivity_C1p0 | 13 [12, 13] | 0 | 0.1269 |
| 48 | geometric | 24576 | adaptive_paper | 6 [6, 6] | 0 | 0.163 |
| 48 | geometric | 24576 | adaptive_split | 9 [8, 9] | 0 | 0.08401 |
| 48 | geometric | 24576 | sensitivity_C0p5 | 29 [29, 30] | 0 | 0.03173 |
| 48 | geometric | 24576 | sensitivity_C1p0 | 14 [13, 14] | 0 | 0.06347 |
| 48 | geometric | 98304 | adaptive_paper | 8 [8, 8] | 0 | 0.08152 |
| 48 | geometric | 98304 | adaptive_split | 10 [10, 10.25] | 0 | 0.04271 |
| 48 | geometric | 98304 | sensitivity_C0p5 | 29.5 [29, 30] | 0 | 0.01587 |
| 48 | geometric | 98304 | sensitivity_C1p0 | 15 [14, 15] | 0 | 0.03173 |
| 48 | geometric | 393216 | adaptive_paper | 10 [10, 10] | 0 | 0.04076 |
| 48 | geometric | 393216 | adaptive_split | 12 [12, 12] | 0 | 0.02134 |
| 48 | geometric | 393216 | sensitivity_C0p5 | 30 [30, 30] | 0 | 0.007933 |
| 48 | geometric | 393216 | sensitivity_C1p0 | 16 [16, 17] | 0 | 0.01587 |
| 48 | polynomial | 384 | adaptive_paper | 0 [0, 0] | 32 | 1.304 |
| 48 | polynomial | 384 | adaptive_split | 1 [1, 1] | 2 | 1.057 |
| 48 | polynomial | 384 | sensitivity_C0p5 | 29 [28, 29.25] | 0 | 0.2539 |
| 48 | polynomial | 384 | sensitivity_C1p0 | 13 [13, 14] | 0 | 0.5077 |
| 48 | polynomial | 1536 | adaptive_paper | 1 [1, 1] | 0 | 0.6522 |
| 48 | polynomial | 1536 | adaptive_split | 4 [4, 4.25] | 0 | 0.3689 |
| 48 | polynomial | 1536 | sensitivity_C0p5 | 29 [28, 29] | 0 | 0.1269 |
| 48 | polynomial | 1536 | sensitivity_C1p0 | 12.5 [12, 13] | 0 | 0.2539 |
| 48 | polynomial | 6144 | adaptive_paper | 3 [3, 3] | 0 | 0.3261 |
| 48 | polynomial | 6144 | adaptive_split | 8 [8, 9] | 0 | 0.1757 |
| 48 | polynomial | 6144 | sensitivity_C0p5 | 31 [30, 31] | 0 | 0.06347 |
| 48 | polynomial | 6144 | sensitivity_C1p0 | 16 [16, 16.25] | 0 | 0.1269 |
| 48 | polynomial | 24576 | adaptive_paper | 6 [6, 6] | 0 | 0.163 |
| 48 | polynomial | 24576 | adaptive_split | 16 [15, 17] | 0 | 0.08403 |
| 48 | polynomial | 24576 | sensitivity_C0p5 | 36 [35, 36] | 0 | 0.03173 |
| 48 | polynomial | 24576 | sensitivity_C1p0 | 23 [22.75, 23.25] | 0 | 0.06347 |
| 48 | polynomial | 98304 | adaptive_paper | 13 [12, 13] | 0 | 0.08152 |
| 48 | polynomial | 98304 | adaptive_split | 27 [26, 27.25] | 0 | 0.04272 |
| 48 | polynomial | 98304 | sensitivity_C0p5 | 44 [44, 44] | 0 | 0.01587 |
| 48 | polynomial | 98304 | sensitivity_C1p0 | 34 [33, 34] | 0 | 0.03173 |
| 48 | polynomial | 393216 | adaptive_paper | 25 [25, 26] | 0 | 0.04076 |
| 48 | polynomial | 393216 | adaptive_split | 43 [42, 43] | 0 | 0.02134 |
| 48 | polynomial | 393216 | sensitivity_C0p5 | 48 [48, 48] | 0 | 0.007933 |
| 48 | polynomial | 393216 | sensitivity_C1p0 | 47 [47, 48] | 0 | 0.01587 |


## Registered slopes, all arms

Intervals condition on finite-positive bootstrap medians; unidentified repetitions are retained separately.


| n | Spectrum | Arm | Metric | Window | Slope | Conditional 95% CI | Unidentified |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 24 | geometric | dense | gap | all_six | -1.038 | [-1.048, -1.031] | 0/5000 |
| 24 | geometric | dense | gap | last_three | -1.001 | [-1.019, -0.985] | 0/5000 |
| 24 | geometric | dense | relative_gap | all_six | -1.041 | [-1.048, -1.032] | 0/5000 |
| 24 | geometric | dense | relative_gap | last_three | -0.9921 | [-1.02, -0.986] | 0/5000 |
| 24 | geometric | k1 | gap | all_six | -0.0505 | [-0.07406, -0.04652] | 0/5000 |
| 24 | geometric | k1 | gap | last_three | -0.002725 | [-0.003768, -0.0007256] | 0/5000 |
| 24 | geometric | k1 | relative_gap | all_six | -0.06277 | [-0.07156, -0.04828] | 0/5000 |
| 24 | geometric | k1 | relative_gap | last_three | -0.002196 | [-0.003981, -0.0008716] | 0/5000 |
| 24 | geometric | k2 | gap | all_six | -0.1478 | [-0.1699, -0.1313] | 0/5000 |
| 24 | geometric | k2 | gap | last_three | -0.008323 | [-0.01137, -0.00385] | 0/5000 |
| 24 | geometric | k2 | relative_gap | all_six | -0.1496 | [-0.1617, -0.1336] | 0/5000 |
| 24 | geometric | k2 | relative_gap | last_three | -0.008526 | [-0.01086, -0.004043] | 0/5000 |
| 24 | geometric | k3 | gap | all_six | -0.2576 | [-0.2881, -0.2346] | 0/5000 |
| 24 | geometric | k3 | gap | last_three | -0.02141 | [-0.03137, -0.01363] | 0/5000 |
| 24 | geometric | k3 | relative_gap | all_six | -0.2576 | [-0.2891, -0.2373] | 0/5000 |
| 24 | geometric | k3 | relative_gap | last_three | -0.02337 | [-0.03428, -0.01048] | 0/5000 |
| 24 | geometric | k4 | gap | all_six | -0.4095 | [-0.4262, -0.3971] | 0/5000 |
| 24 | geometric | k4 | gap | last_three | -0.05934 | [-0.07001, -0.04797] | 0/5000 |
| 24 | geometric | k4 | relative_gap | all_six | -0.4107 | [-0.4306, -0.3955] | 0/5000 |
| 24 | geometric | k4 | relative_gap | last_three | -0.05728 | [-0.07013, -0.04797] | 0/5000 |
| 24 | geometric | k6 | gap | all_six | -0.664 | [-0.6888, -0.64] | 0/5000 |
| 24 | geometric | k6 | gap | last_three | -0.2375 | [-0.2574, -0.1867] | 0/5000 |
| 24 | geometric | k6 | relative_gap | all_six | -0.6685 | [-0.6886, -0.6421] | 0/5000 |
| 24 | geometric | k6 | relative_gap | last_three | -0.2256 | [-0.2561, -0.1847] | 0/5000 |
| 24 | geometric | k8 | gap | all_six | -0.8652 | [-0.8762, -0.8458] | 0/5000 |
| 24 | geometric | k8 | gap | last_three | -0.5325 | [-0.5637, -0.4928] | 0/5000 |
| 24 | geometric | k8 | relative_gap | all_six | -0.8584 | [-0.8783, -0.8503] | 0/5000 |
| 24 | geometric | k8 | relative_gap | last_three | -0.5078 | [-0.5503, -0.4876] | 0/5000 |
| 24 | geometric | k12 | gap | all_six | -1.032 | [-1.038, -1.027] | 0/5000 |
| 24 | geometric | k12 | gap | last_three | -0.9758 | [-0.9989, -0.9679] | 0/5000 |
| 24 | geometric | k12 | relative_gap | all_six | -1.034 | [-1.038, -1.026] | 0/5000 |
| 24 | geometric | k12 | relative_gap | last_three | -0.9735 | [-0.9973, -0.9679] | 0/5000 |
| 24 | geometric | k16 | gap | all_six | -1.039 | [-1.05, -1.033] | 0/5000 |
| 24 | geometric | k16 | gap | last_three | -1.004 | [-1.019, -0.992] | 0/5000 |
| 24 | geometric | k16 | relative_gap | all_six | -1.045 | [-1.049, -1.034] | 0/5000 |
| 24 | geometric | k16 | relative_gap | last_three | -0.9967 | [-1.023, -0.9905] | 0/5000 |
| 24 | geometric | adaptive_paper | gap | all_six | -0.828 | [-0.8425, -0.8017] | 0/5000 |
| 24 | geometric | adaptive_paper | gap | last_three | -0.9164 | [-0.9388, -0.8637] | 0/5000 |
| 24 | geometric | adaptive_paper | relative_gap | all_six | -0.8185 | [-0.8406, -0.804] | 0/5000 |
| 24 | geometric | adaptive_paper | relative_gap | last_three | -0.8735 | [-0.9279, -0.8426] | 0/5000 |
| 24 | geometric | adaptive_split | gap | all_six | -0.8682 | [-0.8752, -0.8599] | 0/5000 |
| 24 | geometric | adaptive_split | gap | last_three | -0.9198 | [-0.939, -0.8972] | 0/5000 |
| 24 | geometric | adaptive_split | relative_gap | all_six | -0.8693 | [-0.8763, -0.8576] | 0/5000 |
| 24 | geometric | adaptive_split | relative_gap | last_three | -0.9157 | [-0.9536, -0.8974] | 0/5000 |
| 24 | geometric | sensitivity_C0p5 | gap | all_six | -1.031 | [-1.043, -1.025] | 0/5000 |
| 24 | geometric | sensitivity_C0p5 | gap | last_three | -1 | [-1.013, -0.9832] | 0/5000 |
| 24 | geometric | sensitivity_C0p5 | relative_gap | all_six | -1.035 | [-1.041, -1.027] | 0/5000 |
| 24 | geometric | sensitivity_C0p5 | relative_gap | last_three | -0.9922 | [-1.012, -0.9839] | 0/5000 |
| 24 | geometric | sensitivity_C1p0 | gap | all_six | -0.9833 | [-0.9943, -0.9704] | 0/5000 |
| 24 | geometric | sensitivity_C1p0 | gap | last_three | -0.9376 | [-0.96, -0.9256] | 0/5000 |
| 24 | geometric | sensitivity_C1p0 | relative_gap | all_six | -0.9837 | [-0.9912, -0.9709] | 0/5000 |
| 24 | geometric | sensitivity_C1p0 | relative_gap | last_three | -0.9431 | [-0.9687, -0.9272] | 0/5000 |
| 24 | polynomial | dense | gap | all_six | -1.041 | [-1.049, -1.032] | 0/5000 |
| 24 | polynomial | dense | gap | last_three | -1.007 | [-1.018, -0.9872] | 0/5000 |
| 24 | polynomial | dense | relative_gap | all_six | -1.041 | [-1.05, -1.033] | 0/5000 |
| 24 | polynomial | dense | relative_gap | last_three | -0.9988 | [-1.018, -0.9873] | 0/5000 |
| 24 | polynomial | k1 | gap | all_six | -0.06563 | [-0.08919, -0.06018] | 0/5000 |
| 24 | polynomial | k1 | gap | last_three | -0.002476 | [-0.004575, -0.001807] | 0/5000 |
| 24 | polynomial | k1 | relative_gap | all_six | -0.07614 | [-0.08648, -0.06135] | 0/5000 |
| 24 | polynomial | k1 | relative_gap | last_three | -0.002872 | [-0.004031, -0.001804] | 0/5000 |
| 24 | polynomial | k2 | gap | all_six | -0.1664 | [-0.1829, -0.148] | 0/5000 |
| 24 | polynomial | k2 | gap | last_three | -0.009694 | [-0.01228, -0.004654] | 0/5000 |
| 24 | polynomial | k2 | relative_gap | all_six | -0.1648 | [-0.1778, -0.1511] | 0/5000 |
| 24 | polynomial | k2 | relative_gap | last_three | -0.0104 | [-0.0123, -0.005595] | 0/5000 |
| 24 | polynomial | k3 | gap | all_six | -0.2462 | [-0.2732, -0.2341] | 0/5000 |
| 24 | polynomial | k3 | gap | last_three | -0.02014 | [-0.02372, -0.01375] | 0/5000 |
| 24 | polynomial | k3 | relative_gap | all_six | -0.2482 | [-0.2612, -0.2411] | 0/5000 |
| 24 | polynomial | k3 | relative_gap | last_three | -0.0186 | [-0.02535, -0.01353] | 0/5000 |
| 24 | polynomial | k4 | gap | all_six | -0.3256 | [-0.341, -0.3138] | 0/5000 |
| 24 | polynomial | k4 | gap | last_three | -0.03199 | [-0.03896, -0.02848] | 0/5000 |
| 24 | polynomial | k4 | relative_gap | all_six | -0.3307 | [-0.3362, -0.3123] | 0/5000 |
| 24 | polynomial | k4 | relative_gap | last_three | -0.03462 | [-0.03993, -0.02628] | 0/5000 |
| 24 | polynomial | k6 | gap | all_six | -0.431 | [-0.4503, -0.42] | 0/5000 |
| 24 | polynomial | k6 | gap | last_three | -0.07056 | [-0.08397, -0.05692] | 0/5000 |
| 24 | polynomial | k6 | relative_gap | all_six | -0.4356 | [-0.4458, -0.4258] | 0/5000 |
| 24 | polynomial | k6 | relative_gap | last_three | -0.05988 | [-0.08005, -0.05523] | 0/5000 |
| 24 | polynomial | k8 | gap | all_six | -0.5155 | [-0.5232, -0.502] | 0/5000 |
| 24 | polynomial | k8 | gap | last_three | -0.1249 | [-0.1316, -0.09802] | 0/5000 |
| 24 | polynomial | k8 | relative_gap | all_six | -0.52 | [-0.5259, -0.4989] | 0/5000 |
| 24 | polynomial | k8 | relative_gap | last_three | -0.1144 | [-0.1342, -0.09786] | 0/5000 |
| 24 | polynomial | k12 | gap | all_six | -0.6451 | [-0.6644, -0.6376] | 0/5000 |
| 24 | polynomial | k12 | gap | last_three | -0.2473 | [-0.2653, -0.2221] | 0/5000 |
| 24 | polynomial | k12 | relative_gap | all_six | -0.6482 | [-0.6588, -0.6389] | 0/5000 |
| 24 | polynomial | k12 | relative_gap | last_three | -0.2459 | [-0.2675, -0.2194] | 0/5000 |
| 24 | polynomial | k16 | gap | all_six | -0.7585 | [-0.7779, -0.7449] | 0/5000 |
| 24 | polynomial | k16 | gap | last_three | -0.3943 | [-0.4151, -0.3589] | 0/5000 |
| 24 | polynomial | k16 | relative_gap | all_six | -0.7605 | [-0.7702, -0.7484] | 0/5000 |
| 24 | polynomial | k16 | relative_gap | last_three | -0.3917 | [-0.4175, -0.3641] | 0/5000 |
| 24 | polynomial | adaptive_paper | gap | all_six | -0.684 | [-0.6969, -0.659] | 0/5000 |
| 24 | polynomial | adaptive_paper | gap | last_three | -1.13 | [-1.15, -1.063] | 0/5000 |
| 24 | polynomial | adaptive_paper | relative_gap | all_six | -0.6796 | [-0.6955, -0.6592] | 0/5000 |
| 24 | polynomial | adaptive_paper | relative_gap | last_three | -1.105 | [-1.148, -1.064] | 0/5000 |
| 24 | polynomial | adaptive_split | gap | all_six | -0.8188 | [-0.8269, -0.8045] | 0/5000 |
| 24 | polynomial | adaptive_split | gap | last_three | -1.171 | [-1.183, -1.145] | 0/5000 |
| 24 | polynomial | adaptive_split | relative_gap | all_six | -0.8199 | [-0.8286, -0.8059] | 0/5000 |
| 24 | polynomial | adaptive_split | relative_gap | last_three | -1.161 | [-1.186, -1.145] | 0/5000 |
| 24 | polynomial | sensitivity_C0p5 | gap | all_six | -1.03 | [-1.039, -1.02] | 0/5000 |
| 24 | polynomial | sensitivity_C0p5 | gap | last_three | -1.025 | [-1.047, -1.005] | 0/5000 |
| 24 | polynomial | sensitivity_C0p5 | relative_gap | all_six | -1.03 | [-1.037, -1.022] | 0/5000 |
| 24 | polynomial | sensitivity_C0p5 | relative_gap | last_three | -1.023 | [-1.042, -1.009] | 0/5000 |
| 24 | polynomial | sensitivity_C1p0 | gap | all_six | -0.9676 | [-0.9756, -0.9564] | 0/5000 |
| 24 | polynomial | sensitivity_C1p0 | gap | last_three | -1.115 | [-1.122, -1.087] | 0/5000 |
| 24 | polynomial | sensitivity_C1p0 | relative_gap | all_six | -0.9684 | [-0.9773, -0.9577] | 0/5000 |
| 24 | polynomial | sensitivity_C1p0 | relative_gap | last_three | -1.105 | [-1.121, -1.094] | 0/5000 |
| 48 | geometric | dense | gap | all_six | -1.042 | [-1.051, -1.033] | 0/5000 |
| 48 | geometric | dense | gap | last_three | -1.009 | [-1.017, -0.9935] | 0/5000 |
| 48 | geometric | dense | relative_gap | all_six | -1.041 | [-1.049, -1.037] | 0/5000 |
| 48 | geometric | dense | relative_gap | last_three | -1.007 | [-1.015, -0.9969] | 0/5000 |
| 48 | geometric | k1 | gap | all_six | -0.05949 | [-0.07308, -0.05507] | 0/5000 |
| 48 | geometric | k1 | gap | last_three | -0.002161 | [-0.003362, -0.001828] | 0/5000 |
| 48 | geometric | k1 | relative_gap | all_six | -0.06103 | [-0.06631, -0.05592] | 0/5000 |
| 48 | geometric | k1 | relative_gap | last_three | -0.002803 | [-0.003212, -0.00211] | 0/5000 |
| 48 | geometric | k2 | gap | all_six | -0.1485 | [-0.1659, -0.1375] | 0/5000 |
| 48 | geometric | k2 | gap | last_three | -0.006298 | [-0.009573, -0.006277] | 0/5000 |
| 48 | geometric | k2 | relative_gap | all_six | -0.1446 | [-0.1587, -0.1342] | 0/5000 |
| 48 | geometric | k2 | relative_gap | last_three | -0.008338 | [-0.01052, -0.005762] | 0/5000 |
| 48 | geometric | k3 | gap | all_six | -0.2553 | [-0.278, -0.2441] | 0/5000 |
| 48 | geometric | k3 | gap | last_three | -0.021 | [-0.02426, -0.01756] | 0/5000 |
| 48 | geometric | k3 | relative_gap | all_six | -0.2609 | [-0.272, -0.247] | 0/5000 |
| 48 | geometric | k3 | relative_gap | last_three | -0.02137 | [-0.02429, -0.01657] | 0/5000 |
| 48 | geometric | k4 | gap | all_six | -0.3912 | [-0.4153, -0.3848] | 0/5000 |
| 48 | geometric | k4 | gap | last_three | -0.0512 | [-0.05712, -0.04356] | 0/5000 |
| 48 | geometric | k4 | relative_gap | all_six | -0.3987 | [-0.4095, -0.3903] | 0/5000 |
| 48 | geometric | k4 | relative_gap | last_three | -0.05047 | [-0.05677, -0.04559] | 0/5000 |
| 48 | geometric | k6 | gap | all_six | -0.6744 | [-0.6949, -0.6592] | 0/5000 |
| 48 | geometric | k6 | gap | last_three | -0.2283 | [-0.2418, -0.2042] | 0/5000 |
| 48 | geometric | k6 | relative_gap | all_six | -0.6731 | [-0.6867, -0.6594] | 0/5000 |
| 48 | geometric | k6 | relative_gap | last_three | -0.2214 | [-0.2371, -0.1994] | 0/5000 |
| 48 | geometric | k8 | gap | all_six | -0.8852 | [-0.916, -0.88] | 0/5000 |
| 48 | geometric | k8 | gap | last_three | -0.5431 | [-0.6042, -0.5365] | 0/5000 |
| 48 | geometric | k8 | relative_gap | all_six | -0.8884 | [-0.9012, -0.8817] | 0/5000 |
| 48 | geometric | k8 | relative_gap | last_three | -0.5475 | [-0.5786, -0.5372] | 0/5000 |
| 48 | geometric | k12 | gap | all_six | -1.048 | [-1.064, -1.043] | 0/5000 |
| 48 | geometric | k12 | gap | last_three | -1.021 | [-1.031, -1.003] | 0/5000 |
| 48 | geometric | k12 | relative_gap | all_six | -1.047 | [-1.056, -1.043] | 0/5000 |
| 48 | geometric | k12 | relative_gap | last_three | -1.016 | [-1.027, -1.001] | 0/5000 |
| 48 | geometric | k16 | gap | all_six | -1.045 | [-1.057, -1.037] | 0/5000 |
| 48 | geometric | k16 | gap | last_three | -1.024 | [-1.04, -1.01] | 0/5000 |
| 48 | geometric | k16 | relative_gap | all_six | -1.045 | [-1.053, -1.039] | 0/5000 |
| 48 | geometric | k16 | relative_gap | last_three | -1.028 | [-1.035, -1.012] | 0/5000 |
| 48 | geometric | k24 | gap | all_six | -1.042 | [-1.051, -1.032] | 0/5000 |
| 48 | geometric | k24 | gap | last_three | -1.012 | [-1.023, -0.9968] | 0/5000 |
| 48 | geometric | k24 | relative_gap | all_six | -1.039 | [-1.05, -1.036] | 0/5000 |
| 48 | geometric | k24 | relative_gap | last_three | -1.012 | [-1.02, -1.002] | 0/5000 |
| 48 | geometric | k32 | gap | all_six | -1.041 | [-1.05, -1.032] | 0/5000 |
| 48 | geometric | k32 | gap | last_three | -1.011 | [-1.017, -0.9942] | 0/5000 |
| 48 | geometric | k32 | relative_gap | all_six | -1.04 | [-1.049, -1.036] | 0/5000 |
| 48 | geometric | k32 | relative_gap | last_three | -1.009 | [-1.017, -1] | 0/5000 |
| 48 | geometric | adaptive_paper | gap | all_six | -0.8187 | [-0.8246, -0.8126] | 0/5000 |
| 48 | geometric | adaptive_paper | gap | last_three | -0.9138 | [-0.931, -0.8967] | 0/5000 |
| 48 | geometric | adaptive_paper | relative_gap | all_six | -0.8186 | [-0.8223, -0.814] | 0/5000 |
| 48 | geometric | adaptive_paper | relative_gap | last_three | -0.9189 | [-0.9343, -0.9025] | 0/5000 |
| 48 | geometric | adaptive_split | gap | all_six | -0.844 | [-0.8587, -0.839] | 0/5000 |
| 48 | geometric | adaptive_split | gap | last_three | -0.9059 | [-0.9305, -0.8997] | 0/5000 |
| 48 | geometric | adaptive_split | relative_gap | all_six | -0.8447 | [-0.855, -0.8388] | 0/5000 |
| 48 | geometric | adaptive_split | relative_gap | last_three | -0.9073 | [-0.9316, -0.9006] | 0/5000 |
| 48 | geometric | sensitivity_C0p5 | gap | all_six | -1.038 | [-1.048, -1.03] | 0/5000 |
| 48 | geometric | sensitivity_C0p5 | gap | last_three | -1.01 | [-1.018, -0.9912] | 0/5000 |
| 48 | geometric | sensitivity_C0p5 | relative_gap | all_six | -1.038 | [-1.047, -1.033] | 0/5000 |
| 48 | geometric | sensitivity_C0p5 | relative_gap | last_three | -1.008 | [-1.013, -0.9968] | 0/5000 |
| 48 | geometric | sensitivity_C1p0 | gap | all_six | -1.027 | [-1.034, -1.019] | 0/5000 |
| 48 | geometric | sensitivity_C1p0 | gap | last_three | -0.9708 | [-0.9959, -0.9606] | 0/5000 |
| 48 | geometric | sensitivity_C1p0 | relative_gap | all_six | -1.024 | [-1.032, -1.017] | 0/5000 |
| 48 | geometric | sensitivity_C1p0 | relative_gap | last_three | -0.9766 | [-0.998, -0.9614] | 0/5000 |
| 48 | polynomial | dense | gap | all_six | -1.043 | [-1.052, -1.033] | 0/5000 |
| 48 | polynomial | dense | gap | last_three | -1.009 | [-1.017, -0.9903] | 0/5000 |
| 48 | polynomial | dense | relative_gap | all_six | -1.043 | [-1.05, -1.038] | 0/5000 |
| 48 | polynomial | dense | relative_gap | last_three | -1.004 | [-1.015, -0.9941] | 0/5000 |
| 48 | polynomial | k1 | gap | all_six | -0.07016 | [-0.08508, -0.06418] | 0/5000 |
| 48 | polynomial | k1 | gap | last_three | -0.002877 | [-0.004318, -0.002464] | 0/5000 |
| 48 | polynomial | k1 | relative_gap | all_six | -0.07355 | [-0.07754, -0.06631] | 0/5000 |
| 48 | polynomial | k1 | relative_gap | last_three | -0.003404 | [-0.003634, -0.002568] | 0/5000 |
| 48 | polynomial | k2 | gap | all_six | -0.1586 | [-0.1805, -0.1496] | 0/5000 |
| 48 | polynomial | k2 | gap | last_three | -0.008583 | [-0.009605, -0.006721] | 0/5000 |
| 48 | polynomial | k2 | relative_gap | all_six | -0.1544 | [-0.1642, -0.1475] | 0/5000 |
| 48 | polynomial | k2 | relative_gap | last_three | -0.007216 | [-0.01021, -0.006801] | 0/5000 |
| 48 | polynomial | k3 | gap | all_six | -0.2329 | [-0.2597, -0.2277] | 0/5000 |
| 48 | polynomial | k3 | gap | last_three | -0.01638 | [-0.0187, -0.01411] | 0/5000 |
| 48 | polynomial | k3 | relative_gap | all_six | -0.2357 | [-0.2482, -0.2294] | 0/5000 |
| 48 | polynomial | k3 | relative_gap | last_three | -0.01842 | [-0.02033, -0.01285] | 0/5000 |
| 48 | polynomial | k4 | gap | all_six | -0.3107 | [-0.3343, -0.303] | 0/5000 |
| 48 | polynomial | k4 | gap | last_three | -0.03007 | [-0.033, -0.027] | 0/5000 |
| 48 | polynomial | k4 | relative_gap | all_six | -0.3132 | [-0.3223, -0.3045] | 0/5000 |
| 48 | polynomial | k4 | relative_gap | last_three | -0.02943 | [-0.03288, -0.02396] | 0/5000 |
| 48 | polynomial | k6 | gap | all_six | -0.4238 | [-0.4444, -0.4178] | 0/5000 |
| 48 | polynomial | k6 | gap | last_three | -0.06305 | [-0.06958, -0.05527] | 0/5000 |
| 48 | polynomial | k6 | relative_gap | all_six | -0.4256 | [-0.4353, -0.4182] | 0/5000 |
| 48 | polynomial | k6 | relative_gap | last_three | -0.06337 | [-0.07169, -0.05361] | 0/5000 |
| 48 | polynomial | k8 | gap | all_six | -0.5093 | [-0.5294, -0.5008] | 0/5000 |
| 48 | polynomial | k8 | gap | last_three | -0.09949 | [-0.1112, -0.09328] | 0/5000 |
| 48 | polynomial | k8 | relative_gap | all_six | -0.5107 | [-0.5185, -0.5003] | 0/5000 |
| 48 | polynomial | k8 | relative_gap | last_three | -0.09916 | [-0.1066, -0.09391] | 0/5000 |
| 48 | polynomial | k12 | gap | all_six | -0.638 | [-0.6463, -0.6257] | 0/5000 |
| 48 | polynomial | k12 | gap | last_three | -0.2236 | [-0.2275, -0.2059] | 0/5000 |
| 48 | polynomial | k12 | relative_gap | all_six | -0.6335 | [-0.6406, -0.6274] | 0/5000 |
| 48 | polynomial | k12 | relative_gap | last_three | -0.2091 | [-0.2255, -0.2021] | 0/5000 |
| 48 | polynomial | k16 | gap | all_six | -0.7244 | [-0.7303, -0.7101] | 0/5000 |
| 48 | polynomial | k16 | gap | last_three | -0.3334 | [-0.3407, -0.3135] | 0/5000 |
| 48 | polynomial | k16 | relative_gap | all_six | -0.7192 | [-0.7271, -0.7138] | 0/5000 |
| 48 | polynomial | k16 | relative_gap | last_three | -0.3179 | [-0.3333, -0.3103] | 0/5000 |
| 48 | polynomial | k24 | gap | all_six | -0.8346 | [-0.8432, -0.8234] | 0/5000 |
| 48 | polynomial | k24 | gap | last_three | -0.5155 | [-0.5273, -0.5044] | 0/5000 |
| 48 | polynomial | k24 | relative_gap | all_six | -0.8348 | [-0.8407, -0.8266] | 0/5000 |
| 48 | polynomial | k24 | relative_gap | last_three | -0.5183 | [-0.5219, -0.5009] | 0/5000 |
| 48 | polynomial | k32 | gap | all_six | -0.9092 | [-0.9172, -0.899] | 0/5000 |
| 48 | polynomial | k32 | gap | last_three | -0.6624 | [-0.6696, -0.6473] | 0/5000 |
| 48 | polynomial | k32 | relative_gap | all_six | -0.9077 | [-0.9158, -0.9025] | 0/5000 |
| 48 | polynomial | k32 | relative_gap | last_three | -0.6557 | [-0.6678, -0.6459] | 0/5000 |
| 48 | polynomial | adaptive_paper | gap | all_six | -0.5272 | [-0.5332, -0.5165] | 0/5000 |
| 48 | polynomial | adaptive_paper | gap | last_three | -0.6851 | [-0.7002, -0.6583] | 0/5000 |
| 48 | polynomial | adaptive_paper | relative_gap | all_six | -0.5228 | [-0.5292, -0.5129] | 0/5000 |
| 48 | polynomial | adaptive_paper | relative_gap | last_three | -0.6835 | [-0.6919, -0.6666] | 0/5000 |
| 48 | polynomial | adaptive_split | gap | all_six | -0.6653 | [-0.671, -0.6584] | 0/5000 |
| 48 | polynomial | adaptive_split | gap | last_three | -0.9089 | [-0.9243, -0.8918] | 0/5000 |
| 48 | polynomial | adaptive_split | relative_gap | all_six | -0.664 | [-0.6715, -0.6571] | 0/5000 |
| 48 | polynomial | adaptive_split | relative_gap | last_three | -0.9037 | [-0.9219, -0.8932] | 0/5000 |
| 48 | polynomial | sensitivity_C0p5 | gap | all_six | -1.026 | [-1.036, -1.016] | 0/5000 |
| 48 | polynomial | sensitivity_C0p5 | gap | last_three | -1.021 | [-1.029, -1.001] | 0/5000 |
| 48 | polynomial | sensitivity_C0p5 | relative_gap | all_six | -1.026 | [-1.033, -1.021] | 0/5000 |
| 48 | polynomial | sensitivity_C0p5 | relative_gap | last_three | -1.016 | [-1.028, -1.005] | 0/5000 |
| 48 | polynomial | sensitivity_C1p0 | gap | all_six | -0.9331 | [-0.9432, -0.9243] | 0/5000 |
| 48 | polynomial | sensitivity_C1p0 | gap | last_three | -1.013 | [-1.033, -1.007] | 0/5000 |
| 48 | polynomial | sensitivity_C1p0 | relative_gap | all_six | -0.9343 | [-0.9406, -0.9261] | 0/5000 |
| 48 | polynomial | sensitivity_C1p0 | relative_gap | last_three | -1.019 | [-1.026, -1.001] | 0/5000 |
