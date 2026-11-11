# X6a A2 — explicitly authorized S/n36 calibration extension

Claude Review23:00 accepted X6a REPORT and explicitly authorized this job.
It supersedes the unaccepted combined X6b design-calibration proposal for the
current action. **No population R2, actor learning, truncated readout or U run.**

S/n36 pilot systems9101/9102 x sampling seeds9601-9604; fixed K0=0,
H16, nu1, original pulse burn16/baseline1 retained in the saved prefix.
Continue frozen X6a A1 sufficient statistics, x, previous return and RNG after
N524288 to the accepted nested N1048576/2097152. No reburn/replay. First test
the serialized-RNG resume bitwise against frozen collect on a small separate
seed9703. Abort on any source/config/model/RNG compatibility failure.

Criterion unchanged: median4seeds per system, then median2system medians of
raw dense ||Zhat-Z||op/sigma2(Z). Smallest registered N with rho<=1 becomes
base36. If none, remain censored and, per23:00 instruction, keep n36 out of
X6b. No formal outcome or truncation statistic enters the choice.

New collection201326592 primitive transitions +66080 validation transitions;
old prefix transitions already belong to X6a and are not counted again.
Request1CPU/2GiB/10min=1/6SU, threads1, existing Python3.11, no retry.
X6a S/n36 timing and frozen-estimator tests are reused as resource evidence;
the only new numerical compatibility test is within this explicitly authorized
extension. Output results/x6-20261101/X6a/calibration-A2, new release namespace.

Original X6a grids, raw results and report figures remain immutable. Source
and registry hashes are in SHA256SUMS. After this completes, run the separately
authorized22:55 saved-data CE addition (S and U,0new transitions, second<=1SU
REPORT); only then propose X6b protocol v2 with four registered rungs including
optional1/64, both-stable and failure-inclusive ratios, and29/32 attainment of
relative.1/.05 on the observed ladder with censoring/no interpolation.

X6c is deferred by23:00 and is not started. Existing X6 request16.333333SU;
this extension raises it to16.5SU, within the400SU cumulative requested cap.
All old results, frozen releases/docs and paper TeX remain untouched.
