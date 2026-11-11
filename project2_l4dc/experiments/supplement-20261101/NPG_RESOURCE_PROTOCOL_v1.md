Scope: X2/X3 NPG resolved population values and bounded resource/equivalence pilot.
Population-only calibration selected X2 T96/384/768 for n12/24/48, with eta
.011153919044485441/.0028280344732500365/.001369344203596291. X3 T64 and
eta.014930779908372525 (one common value across spectra). Details and initial-P
certificates are in each experiment's `pilot/NPG_population_calibration.json`.
No formal learning outputs were used.

Before committing the optional n48 or a large finite-data grid, measure complete
Stein collectors at the smallest and largest planned base2048 batches for each
X2 dimension:2048*(n/12)^2 times1/16, H32,16 pulse-burn blocks plus baseline.
These timings use K0 on pilot9003, are NOT dense learning qualification and cannot
select a base or establish performance. They give measured CPU/memory estimates
for the full T-dependent plans. One core/2GiB,max10min,upper.166667SU; all used
transitions/cost are included globally. No automatic rerun on timeout.

The same job verifies the new multi-order collector against the frozen paired
engine on a disjoint X3 pilot plant, retaining every assessed gain and requiring
bitwise equality, identical gap/stability, and independently counted actual
burn/baseline/learning/padding transitions. General multi-order code permits the
five X3 ranks without duplicate dense trajectories; every arm keeps its own
continuous state and paired exogenous innovations. Failed outputs remain
absorbing; any hard failure preserves partial data and is not replayed.

Frozen source hashes are in the new resource-pilot auxiliary manifest. All
finite-data qualification remains dense-only under the preregistered criterion;
the resolved schedules/code still need X2/X3 ACCEPTED before formal submission.
