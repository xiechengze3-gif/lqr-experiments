# X11 CE rectangular one-factor sweeps

Author GO 13:15 CDT Nov6. Construction issue reported before numerical work in
CONSTRUCTION_NOTICE_v1.md and CODEX_REPLY. Minimal rectangular extension is
specified there; all square inputs reproduce the exact old constructor.
Family S, rank2,Q=W=I_n,R=I_m,K0=0,pbar2. All streams, CE burn512,
continuous nested prefix collector, same-data OLS, dense and rank2 learner
preserved. Formal systems301..308,seeds1601..1604.

Sweep M: n48,m4/6/8/12/16/24/32; reuse old square48 by reference.
Sweep N: m16,n24/32/48/64/96; reuse X10a square16 by reference.
Cell(48,16) is collected once. All11 new cells use2048,8192,32768,131072,524288;
the fixed append rule n+m>=120 applies to none of these new cells.
352physical paths,184729600transitions;0GraceSU. Four local workers, one
BLAS/Numba thread each, existing E Python environment. Output/cache/temp
inside this new E namespace. No installation. Preserve every failure as+inf.

PILOT fixed before work: three disjoint new cases in config; original model
square byte equality; all requested rectangular dimensions/rank/certificate;
fit/gain/metric/RNG/count bitwise comparison to original generic CE for each
pilot case; one thread; peakRSS<2GiB; availableRAM>4GiB; freeE>5GiB.
No outcome/stability/efficacy selection. Stop/report on any failed check.
FORMAL follows automatically iff every fixed check passes and review unchanged.

REPORT uses original X6a/X10a absolute eps.01, median32 gaps at eachN,
first log-log downcross interpolation, no extrapolation and left/right
censor flags. Sample-cost schema n,eps,dense_N_req,truncated_N_req plus m;
write new rows and merged reuse square48/16 with source SHA provenance.
Report paired dense/trunc gap ratios at everyN (seed median then system
median, all32denominator, both-stable and failure-inclusive counts), all
stable/failure counts and raw records. Descriptive, no theorem verification.
Old results/paper read only. No retry. Recheck review before every advancement.
