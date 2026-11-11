Scope: **X1 Review04:05 P1/P2 REPORT complete**, saved policies plus deterministic exact-gradient model reference; no sampled learner rerun.

P1 evaluated every saved NPG iterate:55,872 X1+30,848 X2=86,720;704 endpoints. U is the orthonormal input null basis ker(B), V_r spans range(B^T), R=I, Pi=V_r V_r^T. The identity g(K)=D+g(Pi K) holds per output; max normalized residual2.04451e-15, orthogonal Frobenius split residual5.68434e-14. Original gap values match exactly; max original D discrepancy7.10543e-14.

Endpoint medians [IQR], each cell32 runs across8 independent systems; D/g is computed per output before summary:

| null | n,m | Method | D | g(Pi K) | D/g | Null Frobenius error² | Action Frobenius error² |
|---:|---|---|---|---|---|---|---|
| 0.0 | 12,2 | dense | 0 [0, 0] | 0.0799763 [0.0109182, 0.466288] | 0 [0, 0] | 0 [0, 0] | 0.0188328 [0.00388479, 0.0889179] |
| 0.0 | 12,2 | truncated | 0 [0, 0] | 0.0799763 [0.0109182, 0.466288] | 0 [0, 0] | 0 [0, 0] | 0.0188328 [0.00388479, 0.0889179] |
| 0.0 | 12,4 | dense | 0.0664933 [0.0189309, 0.239612] | 0.0834762 [0.0117978, 0.470807] | 0.481242 [0.37348, 0.591466] | 0.0549981 [0.0157105, 0.182489] | 0.0157699 [0.00365593, 0.0996099] |
| 0.0 | 12,4 | truncated | 0.0538439 [0.0132636, 0.186713] | 0.0803439 [0.0239423, 0.357601] | 0.351344 [0.274459, 0.407997] | 0.0411207 [0.0108097, 0.144015] | 0.0226781 [0.00751549, 0.0850927] |
| 0.0 | 12,6 | dense | 0.161216 [0.0301306, 0.601001] | 0.0767807 [0.0114054, 0.666969] | 0.633458 [0.544723, 0.750496] | 0.114436 [0.0244514, 0.459166] | 0.0214835 [0.0038983, 0.0978853] |
| 0.0 | 12,6 | truncated | 0.107207 [0.0196538, 0.424924] | 0.0712173 [0.0369985, 0.449879] | 0.408526 [0.337198, 0.526089] | 0.0813725 [0.0166302, 0.335731] | 0.0221477 [0.0119212, 0.0661735] |
| 0.0 | 12,9 | dense | 0.211728 [0.0611304, 0.949808] | 0.0753247 [0.01137, 0.67598] | 0.764866 [0.684119, 0.806671] | 0.15546 [0.0494683, 0.72276] | 0.022337 [0.00406658, 0.110114] |
| 0.0 | 12,9 | truncated | 0.132069 [0.0332816, 0.553325] | 0.103041 [0.0563406, 0.416327] | 0.471893 [0.383507, 0.570648] | 0.103769 [0.0275038, 0.451316] | 0.0299135 [0.0170742, 0.0850553] |
| 0.0 | 12,12 | dense | 0.397179 [0.0808256, 1.68592] | 0.119003 [0.0140677, 0.584753] | 0.820844 [0.739402, 0.857226] | 0.314428 [0.0668873, 1.27196] | 0.0206505 [0.00523144, 0.0910307] |
| 0.0 | 12,12 | truncated | 0.191415 [0.04166, 0.627712] | 0.129343 [0.0641481, 0.444775] | 0.535758 [0.349504, 0.641854] | 0.158127 [0.0352215, 0.492179] | 0.0285778 [0.0174897, 0.0854107] |
| 0.25 | 12,4 | dense | 0.0903004 [0.0307242, 0.265654] | 0.0831924 [0.0122865, 0.472677] | 0.59744 [0.420387, 0.715304] | 0.0710649 [0.0239246, 0.204277] | 0.015848 [0.00363923, 0.0989271] |
| 0.25 | 12,4 | truncated | 0.0794507 [0.0301225, 0.197871] | 0.0798991 [0.0238073, 0.357839] | 0.502308 [0.365531, 0.573885] | 0.0569089 [0.0199951, 0.152904] | 0.0225893 [0.0074839, 0.0844043] |
| 0.25 | 12,6 | dense | 0.162065 [0.0480529, 0.6224] | 0.0781766 [0.0115744, 0.664117] | 0.685767 [0.546993, 0.802426] | 0.112051 [0.0312723, 0.472253] | 0.0214696 [0.00393094, 0.0979333] |
| 0.25 | 12,6 | truncated | 0.115753 [0.0342697, 0.442683] | 0.0710273 [0.0354967, 0.448288] | 0.490243 [0.419429, 0.595675] | 0.0913848 [0.0245059, 0.352119] | 0.0219251 [0.0116468, 0.0661689] |
| 0.25 | 12,9 | dense | 0.237839 [0.0821431, 0.953965] | 0.0753053 [0.011541, 0.686538] | 0.779685 [0.68284, 0.847916] | 0.172236 [0.0618888, 0.722763] | 0.0222594 [0.00409113, 0.110831] |
| 0.25 | 12,9 | truncated | 0.154038 [0.0522023, 0.55302] | 0.103506 [0.055439, 0.414337] | 0.549932 [0.48106, 0.599361] | 0.116818 [0.0390648, 0.447964] | 0.0300067 [0.0169304, 0.0844441] |
| 0.25 | 12,12 | dense | 0.417408 [0.0984514, 1.68424] | 0.120561 [0.0141714, 0.586259] | 0.824561 [0.741179, 0.874414] | 0.327015 [0.075731, 1.27404] | 0.0207576 [0.00527269, 0.0913575] |
| 0.25 | 12,12 | truncated | 0.209249 [0.0605966, 0.628189] | 0.127671 [0.0631369, 0.44497] | 0.568157 [0.467384, 0.651947] | 0.168865 [0.0450628, 0.501644] | 0.0285715 [0.0172215, 0.0855695] |

P2 population reference uses the same saved K0, original eta/T and exact objective gradient,88 physical model references total (72 X1,16 X2);8 independent system draws per cell. Sampling seeds do not add population models. True-rank2 Z truncation residual<=7.77658e-15 validates one common dense/truncated population reference. No eta/T retuning.

| null | n,m | eta | T | Population relative gap [IQR],8 models |
|---:|---|---:|---:|---|
| 0.0 | 12,2 | 0.00900061455 | 96 | 0.0245376 [0.0161786, 0.0423234] |
| 0.0 | 12,4 | 0.00900061455 | 96 | 0.0245376 [0.0161786, 0.0423234] |
| 0.25 | 12,4 | 0.00900061455 | 96 | 0.05375 [0.039924, 0.0769904] |
| 0.0 | 12,6 | 0.00900061455 | 96 | 0.0245376 [0.0161786, 0.0423234] |
| 0.25 | 12,6 | 0.00900061455 | 96 | 0.05375 [0.039924, 0.0769904] |
| 0.0 | 12,9 | 0.00900061455 | 96 | 0.0245376 [0.0161786, 0.0423234] |
| 0.25 | 12,9 | 0.00900061455 | 96 | 0.05375 [0.039924, 0.0769904] |
| 0.0 | 12,12 | 0.00900061455 | 96 | 0.0245376 [0.0161786, 0.0423234] |
| 0.25 | 12,12 | 0.00900061455 | 96 | 0.05375 [0.039924, 0.0769904] |

Interpretation: the redundant component is not already negligible. In the nonzero-null family, dense median D/g rises.597/.686/.780/.825 with m-r2/4/7/10; truncated fractions remain.502/.490/.550/.568. Paired D ratios are1.20/1.42/1.61/1.90 with component-bootstrap intervals above1, while action-gap ratio intervals include1 and the original total-gap gain intervals still include1. This is component-specific mechanism evidence, not a clear total-gap advantage. Population relative median.05375 matches across all m>r; sampled endpoints.118–.309 dense and.114–.284 truncated are higher. Small eta has not erased null-direction error.

The per-pair changes and how often D decreases while action error increases are in `analysis-P1-P2-tables-v2/paired_component_changes.csv` and `paired_tradeoff_counts.csv`. This describes endpoint tradeoffs; it does not identify a pure variance or projection-bias causal term. Exact-gradient vs sampled differences may also include finite-H bias and truncation effects. Do not add component medians or call a signed sampled-minus-population gap nonnegative statistical error.

Files: `analysis-P1-P2-v1/all_saved_iterate_decompositions.csv`, `endpoint_decompositions.csv`, `decomposition_statistics.csv`, `population_reference_iterates.csv`, `population_reference_endpoints.csv`, `population_model_statistics.csv`, `population_reference_gains.npz`, `paired_decomposition_effects.csv`, `X1_population_matching_check.csv`, `P1_component_gaps.png/.svg`, `P2_population_vs_sampled.png/.svg`, `REPORT.json`. Complete endpoint/pre-last-update/final16/final-quarter per-run summaries are also joined in `analysis-P1-P2-tables-v2/cell_phase_component_summary.csv`; no correlated iterate is counted as an independent repeat.

New code/config/request protocol frozen in `packages/supplement-20261101-p1-p2-report-v27.manifest.json`; job20359649 completed150s. Delivery15files45,257,314bytes verified locally, old178 files unchanged. Figures visually inspected. Population references are separately counted; training transitions and sampled-learning reruns both0. The original accepted learning results/eta/T remain unchanged, and X3-NPG continues as planned.
