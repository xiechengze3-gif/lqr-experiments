# X2 PROTOCOL v1 — exact-rank dimension/rank scaling

Formal CE and NPG are both **not yet ACCEPTED**. No X1 approval is reused for X2.
CE implementation is the frozen X1 engine plus `ce_suite.py`; config and full
source hashes are in `release-manifest-X2-v1.json`. NPG uses the same frozen
observation-only Stein update; its resolved calibration config must be published
and explicitly accepted before formal learning.

## Construction, cases and independent replication

Use the independently generated unstable A/B and cost-free Schur-mode initializer
already accepted under X1-A1. n=m in12/24/48/96 with r2; n24 has r1/2/4/8.
n24/r2 occurs once and is reused in both analyses, not counted twice.
For r<m add the fixed.25 null component as in X1, without matching initial gap.
The generator has rho(A)=1.05 and independently varying stable eigenvalues;
the initializer has no Q/R/K*/P*/cost input. Q=R=W=I, nu=1.

Pilot systems9003/9004, sampling seeds7003/7004; formal systems201–208,
sampling seeds1101–1104. Every formal cell has8 independent systems x4 sampling
seeds. A and U/V use independent RNG streams; within n, rank scans share A and
nested B singular bases. Different ranks are different control problems, so only
within-system dense/truncated comparisons are labeled gains. Initial-P/gap/rho
and action-space overlap diagnostics are mandatory; no claim of geometry-free K0.

## CE, budget grid and statistics

One continuous trajectory per system/seed; all512 burn transitions include
u=-K0*x+xi. Full original-coordinate joint OLS; no sample whitening or feature
compression. Dense and known-rank CE share each exact OLS fit; only Bhat is
truncated, Ahat unchanged. No truth-selected output, best iterate or favorable seed.

For d=n+m, N starts at4d and ends at1024d. To ensure primitive integer grids are
never coarser than sqrt(2), use the recurrence N_next=min(1024d,floor(sqrt(2)*N)),
with unique positive steps. It is the integer realization of the requested grid;
report actual N and N+512, not rounded nominal budgets. It has18 prefixes for
these cases; exact lists are frozen in config. Same-prefix fits give both arms
identical primitive counts, including burn. Evaluation is exact offline, costing
zero additional sampled transitions.

Report absolute/relative gaps, full32-repeat stable counts, median/IQR with failed
outputs as infinity, paired ratios at every prefix and system-cluster bootstrap
95% intervals (8 clusters,4 sampling seeds kept together,2000 resamples,
seed2026110299). Undefined ratios do not replace full-denominator failure reports.
For absolute and relative epsilon.1/.03, first tested prefix with>=29/32 successes
is attained; preserve right censoring at max N, no interpolation/extrapolation.
Bootstrap attainment budgets by resampling systems; retain infinity/censoring.
The varying control geometry/initial gap is reported, not falsely reduced to a
universal empirical n/r sample-complexity law.

Formal CE count:7 unique cells x8 systems x4 seeds=224 trajectories. The raw
source, config, all prefixes and every failed policy are preserved. A candidate
archive allows independent cost-identity and stability verification.

## NPG calibration plan (no formal permission yet)

n=m12/24,r2 are primary;48 is optional only with measured whole-night capacity.
H32,16 pulse burn blocks and one baseline per stage; Zhat-only truncation and
exact RK term; same primitive counts/noise pairing and accepted absorbing-failure
K0 padding rule. The step for each dimension uses the paper's arm-independent
max-formal-initial-P certificate, as explicitly requested for X1 by the reviewer.
Population NPG on the disjoint pilot systems selects the first qualifying T from
{64,96,128,192,256,384,512,768} reaching relative.05 on all pilot plants.

Predeclare a_t²=2^(-4t/T), N_t=ceil(base*[n(n+m)/(12*24)]/a_t²), base in
{2048,8192,32768}. This has the requested nd/a_t² dimension shape, with logs and
fixed H absorbed into one pilot-calibrated common constant. Select the smallest
base with dense stable on all included pilot dimensions and median relative
endpoint<=.5 in each dimension; never select on truncated performance. H/eta/T/
nu/batches are identical across arms and frozen before formal. If population
criteria or measured cost fail, report the failed branch; do not silently alter
the grid or delete systems. A resolved config/hash and measured plan must be
reviewed before NPG formal runs; this is not a theorem-constant certification.

## Costs and stage gate

First CE pilot:4 system×seed bundles x7 cases, single-core/2GiB, up to15min per
bundle (total request bound1 SU). It measures the n96 case and validates complete
data coverage. Formal CE wall/memory requests come from the largest measured
complete per-cell timings with30%+startup allowance, not an unmeasured claim.
The current all-new-job cap is200 SU, shared with X1/X3/all reports and failures.
Optional n48 NPG cannot consume the reserve for required X3 and reporting.
No formal array starts without explicit X2 acceptance; no60-minute bypass.
All outputs use fresh20261101 folders; earlier results and paper TeX stay read only.
