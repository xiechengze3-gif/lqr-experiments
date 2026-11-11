## X6b PILOT

All5 resource allocations complete:20365427 equivalence,20365428/29/30/31 for
n24/36/48/72. Frozen collector/actor equivalence PASS for both NPG and PI,
bitwise assessed gains/results and exact primitive counts, including absorbing
padding. Resource-only timings cover all32(n,rung,algorithm) cells and both
updates/artifact writes. No noisy accuracy/gap/rho/projection readout.

R2 remains NPG16 / PI8 at eta0.2; bases524288/1048576/2097152/4194304,
H16,nu1,burn16pulseblocks+baseline1. All4rungs1/64,1/16,1/4,1 fit for
proposed dimensions[24, 36, 48, 72]. Systems301-308 x fresh sampling seeds1701-1704,
no systems/seeds/rungs removed within included dimensions. Full four-dimension grid fits; no cuts proposed.
Integer schedules remain byte-for-byte as
resolved-v1; primitive equality holds between arms and algorithms.

Largest-stage single-collector timings at rung1 (seconds; the FORMAL estimate
uses TWO independent collectors, both updates/writes):

|n|NPG seconds|PI seconds|max RSS KiB|
|---:|---:|---:|---:|
|24|9.777|35.683|126,000|
|36|29.674|109.443|131,356|
|48|79.703|293.920|129,344|
|72|291.872|1070.516|138,308|

Measured FORMAL proposal:12arrays x32tasks=384allocations,
1024paired paths /2048arms,
483160776704 primitive transitions including all burn/baseline.
Per(n,system,seed), bundle the low3rungs x2algorithms; full-rung NPG and PI
remain separate allocations. Every scientific path has a fresh K0/state and its
registered private RNG; bundling reuses only immutable plant data. Same plant
NPZ bytes across arms/rungs/algorithms, hashed registry32models; no old formal
performance used. Threads1,1CPU/2GiB; short<=120min,medium otherwise
(live queue limits2h/24h). No automatic retry.

Forecast sums each exact integer schedule plus burn/baseline, using its measured
max-stage collector rate, TWO arms, measured updates/writes,1s per arm/stage
evaluation/checkpoint allowance,60s allocation startup/cache allowance, then
30% margin and integer-minute ceilings. Actual cost may differ from this forecast.

|n|minutes per task:low3 /fullNPG /fullPI|32tasks per group,requested SU|
|---:|---:|---:|
|24|8 / 7 / 7|11.733333|
|36|15 / 18 / 17|26.666667|
|48|32 / 43 / 43|62.933333|
|72|103 / 152 / 151|216.533333|

FORMAL requested upper **317.866667SU**; reserve REPORT
**6.5SU** (four90min saved-data diagnostic jobs +one30min aggregate job),
zero new report transitions. With prior19SU, cumulative upper
**343.366667/400SU**. Full four-dimension grid fits; no cuts proposed.
Resource PILOT itself requested1.916666667SU, primitive transitions
1,499,468,848 including separate warmups and both equivalence versions.

Shallow reviewer files: `experiments/x6-20261101/X6b-protocol-v2/formal-plan.json`
and `measured-costs.csv` (all32 measured cells). Executable config/32model copies
under `prepared-formal-v1/`; config SHA `6c0c63610119ef895cda3af4174589bcbd7cf06ab0e7c26d99df3d5bdec7398d`.
Resource delivery is locally archive/per-file SHA verified, scope includes all
timings, equivalence proof, raw artifacts, receipts, logs and accounting.

Frozen analysis: failure-inclusive full32 endpoint/stage median/IQR; both-stable
and failure-inclusive paired ratios, all failures/denominators; common5000
system-cluster draws; observed-rung29/32 attainment for relative0.1/0.05 with
right censoring and censored bootstrap mass. D/action-gap decomposition and
own-preupdate-policy rho/projection diagnostics are simulator-only, never
learner inputs. Raw/clipped/compressed PI diagnostics are separated. All raw
stage/checkpoint hashes, K continuity, updates, primitive counts are audited.
Plots read CSV only. Numerical report runs on compute nodes,0new samples.

- `frozen_engine.py` SHA `9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`
- `actor_paths.py` SHA `d32e410a64c78a927c2e4b1f9c5ea929c3942c856f393b77b2ab2479ea33a8dc`
- `formal_driver.py` SHA `d30fc3dbf703f17ac37ee2ad7573b7e36589057cbb5d76b572e4375975f54b25`
- `analyze_actor.py` SHA `ec27555202189295f5d46db3c4d51684e1344db58ffea44eb3acd9965bb55469`
- `plot_saved_actor.py` SHA `33759f577ab645e67e1ebba53f8b6228c4528d2e635f57da1634dd6243807835`

**No FORMAL job has been submitted. Await explicit X6b FORMAL ACCEPTED.**
Old data/results/releases and paper TeX unchanged; X6c remains deferred.
Review reread 2026-11-02T05:44:55.933329+00:00,task SHA `4edfc6a70e80782c8211f78ba964bd0faac48a3c74ae50a75e50ed7494dbab02`.
X6 cumulative requested19/400SU; Slurm elapsed
10.383611111SU, AMS settled
9.878611111SU at2026-11-02T05:43:54.277361+00:00
(overlapping views; never add).

STATUS: PILOT DONE X6b
