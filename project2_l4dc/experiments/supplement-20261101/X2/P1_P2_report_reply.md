Scope: **X2 Review04:05 P1/P2 REPORT complete**, saved policies plus deterministic exact-gradient model reference; no sampled learner rerun.

P1 evaluated every saved NPG iterate:55,872 X1+30,848 X2=86,720;704 endpoints. U is the orthonormal input null basis ker(B), V_r spans range(B^T), R=I, Pi=V_r V_r^T. The identity g(K)=D+g(Pi K) holds per output; max normalized residual2.04451e-15, orthogonal Frobenius split residual5.68434e-14. Original gap values match exactly; max original D discrepancy7.10543e-14.

Endpoint medians [IQR], each cell32 runs across8 independent systems; D/g is computed per output before summary:

| null | n,m | Method | D | g(Pi K) | D/g | Null Frobenius error² | Action Frobenius error² |
|---:|---|---|---|---|---|---|---|
| 0.25 | 12,12 | dense | 0.422729 [0.174368, 1.13354] | 0.0578845 [0.0251308, 0.172776] | 0.875649 [0.845952, 0.89309] | 0.32745 [0.139485, 0.872781] | 0.0181134 [0.00879438, 0.0449601] |
| 0.25 | 12,12 | truncated | 0.228913 [0.0984112, 0.573773] | 0.25995 [0.215262, 0.350016] | 0.399812 [0.300089, 0.718084] | 0.18079 [0.0795616, 0.453039] | 0.0473703 [0.0398715, 0.0815223] |
| 0.25 | 24,24 | dense | 0.518342 [0.178414, 3.10939] | 0.108375 [0.0192564, 0.64632] | 0.868799 [0.820203, 0.892315] | 0.409584 [0.140097, 2.47593] | 0.0176935 [0.00443645, 0.0990062] |
| 0.25 | 24,24 | truncated | 0.165444 [0.0641184, 0.870063] | 0.435773 [0.328752, 0.548994] | 0.344341 [0.13098, 0.626028] | 0.132035 [0.0479404, 0.68219] | 0.0691613 [0.0627564, 0.101109] |

P2 population reference uses the same saved K0, original eta/T and exact objective gradient,88 physical model references total (72 X1,16 X2);8 independent system draws per cell. Sampling seeds do not add population models. True-rank2 Z truncation residual<=7.77658e-15 validates one common dense/truncated population reference. No eta/T retuning.

| null | n,m | eta | T | Population relative gap [IQR],8 models |
|---:|---|---:|---:|---|
| 0.25 | 12,12 | 0.011153919 | 96 | 0.025608 [0.0198312, 0.0306194] |
| 0.25 | 24,24 | 0.00282803447 | 384 | 0.0171151 [0.0161915, 0.029352] |

Interpretation: dense D/g medians.87565/.86880 at n12/24 are large, rather than negligible. Truncation lowers them to.39981/.34434 and reduces true D (paired ratios1.848[1.803,2.065],3.151[2.804,3.400]). At the same time, truncated action-gap medians.25995/.43577 exceed dense.05788/.10838; the action-gap paired ratio at n12 is.165[.118,.908], and at n24.298[.0427,1.340]. Thus component tradeoffs can offset the redundant-cost reduction. The original mixed total-gap result remains unchanged. Population relative medians.025608/.017115 are below the sampled.577/.715 and.144/.151 levels, so an optimization-step floor alone does not explain the observed errors.

The per-pair changes and how often D decreases while action error increases are in `analysis-P1-P2-tables-v2/paired_component_changes.csv` and `paired_tradeoff_counts.csv`. This describes endpoint tradeoffs; it does not identify a pure variance or projection-bias causal term. Exact-gradient vs sampled differences may also include finite-H bias and truncation effects. Do not add component medians or call a signed sampled-minus-population gap nonnegative statistical error.

Files: `analysis-P1-P2-v1/all_saved_iterate_decompositions.csv`, `endpoint_decompositions.csv`, `decomposition_statistics.csv`, `population_reference_iterates.csv`, `population_reference_endpoints.csv`, `population_model_statistics.csv`, `population_reference_gains.npz`, `paired_decomposition_effects.csv`, `X1_population_matching_check.csv`, `P1_component_gaps.png/.svg`, `P2_population_vs_sampled.png/.svg`, `REPORT.json`. Complete endpoint/pre-last-update/final16/final-quarter per-run summaries are also joined in `analysis-P1-P2-tables-v2/cell_phase_component_summary.csv`; no correlated iterate is counted as an independent repeat.

New code/config/request protocol frozen in `packages/supplement-20261101-p1-p2-report-v27.manifest.json`; job20359649 completed150s. Delivery15files45,257,314bytes verified locally, old178 files unchanged. Figures visually inspected. Population references are separately counted; training transitions and sampled-learning reruns both0. The original accepted learning results/eta/T remain unchanged, and X3-NPG continues as planned.
