# X10a PROTOCOL v1 — CE densification, local route

X10 GO authorizes local CE, new configurations only. Explicit local provenance, no Slurm job id, no fabricated compute-node status. One worker, one BLAS/OpenMP/Numba thread. Grace spend0SU for all X10a stages. X10b is independently stopped for its reported resource issue; no X10b approval is inferred here.

Frozen source functions and streams are those of each original panel: author-local X8 run_x8.py unchanged; exact9915fc... frozen engine for X1 and S CE; model and ce_prefixes functions extracted byte-for-byte from the *frozen* F587bd... estimator (not the later904ffaa... working copy). Portable imports omit the Unix-only resource module. The pilot reference preserves every ce_run numerical statement, replacing only its Slurm provenance read with explicit local provenance. Truth is used only in simulator/evaluation, never to choose learner order/parameters. Paired arms share one OLS fit; no new whitening/ridge/critic. Pulse actors are not part of X10a.

Panel(a):n=m48,new exactr3/6/12/24 and geometricrho.4/.6/.75/.85. Original X8 systems0..7,seeds0..3, A/B/noise namespaces unchanged; all Gaussian pulse arrays are drawn before all process-noise arrays, and the original scalar-time OLS accumulation is preserved. All orders1..47+dense at each512..262144 prefix (powers2). Model independent A/B as original; Q=R=W=I,K0zero,nu1,burn512. Absolute targets.01/.005 and the existing documented X8 absolute-target analysis amendment. Effective ranks at.01=3/5/10/19 and.005=3/6/11/21, spectrum-only finite48-dimensional sums. No outcome-dependent order selection.

Panel(b):same frozen S CE model/collector/learner, newn16/20/30/42/60/84/96,rank2,K0zero,p0bound1.5625, systems301..308,seeds1601..1604. Old N grid2048/8192/32768/131072/524288. Forn>=60 append1048576 (the next power after the old maximum), frozen before any run. Original rng(10,n,m,system,seed),512burn,nestedcontinuous trajectory/shared OLS. Dense and rank2 from the same fit. Absolute target.01, original log-log first-downcross arithmetic; regressionN and burn-inclusiveM=N+512 both in raw data.

Panel(c):original unstable independent-A/B X1 construction,n12,r2,nullscale.25,newm-r1/3/5/6/8/9 (m3/5/7/8/10/11),systems101..108,seeds1001..1004,N4096/8192,burn512. CE dense/truncated only. Per-output normalizeN*D/vstar, vstar=||Pstar(A-BKstar)||F² from matching model, then take full32 median/IQR exactly as originalrefine_ce. Failed outputs remain+inf. No old configurations are rerun for CE.

Complete formal counts:256 X8 trajectories,224 S-dimension trajectories,192 X1 trajectories =672 physical paths,236797952 transitions including burn once per path (not a sum over shared arms/prefixes).122880 X8outputs,2432 dimensionoutputs,768 redundant-inputoutputs. Fixed model/seed/config lists in ce-config-protocol-v1.json.

Pilot, before formal and with no performance-based selection: three disjoint inputs only. (1) X8 n48rho.85,sys9901seed7701,all480 outputs of the unchanged original run function/source identity and full count check; (2) S n96,sys9902seed7702,full largest-prefix grid; (3) X1 n12m11,null.25,sys9903seed7703,N4096/8192. Cases2/3 compare complete prefix theta, gain arrays, assessed values and final RNG state/primitive counts bitwise against the originalce_run numerical reference, and count both physical validation trajectories. Time and peak working set only are printed; no stability/gap accuracy selection or retuning. Require source identity, bitwise comparisons/counts and <=2GiB process peak. Otherwise stop/report, no automatic retry. No formal observations collected during pilot.

Before any numerical import/run, launcher checks actual E-drive output/cache/temp paths, free disk and memory; sets TMPDIR/TEMP/TMP to E:/ChatGPT/Temp/LQR_X10a_20261106, XDG/Numba/Matplotlib caches to E:/ChatGPT/Cache/LQR_X10a_20261106, source/outputhereonE; existing E:/anaconda/python.exe, no installations. Threadpoolctl must confirm one thread per loaded numerical library. Small stdlib source/count checks have run; no numerical pilot/formal/data re-analysis has run at protocol publication. Pilot and formal use explicit LOCAL_AUTHOR_APPROVED_X10a provenance. Store complete per-prefix fits/policies/model certificates and immutable path receipts. New output directories only; no overwrite or automatic restart of partial paths.

After all fixed pilot checks PASS, publish PILOT and a time/memory estimate, reread the review log, then FORMAL automatically as X10 GO directs (no extra approval round). Resource failure stops/report. REPORT after complete source/count/hash coverage: full32 failure-inclusive medians, original X8 2000 system bootstrap/seed0 and crossing/censoring, S-dimension median-curve crossing.01, and original X1 normalized median/IQR. Export new-only main CSVs with exactly the original schemas, plus merged copies made by appending new rows to the original baseline bytes. Verify each entire baseline prefix byte-identical. Supplement censor flags/first-grid bounds, all failures, new raw records, fit/model hashes and local provenance. Old bootstrap or old records are never recomputed. Nonfinite/unidentified results remain visible. No smoothing/extrapolation or new epsilon/probability/theorem claim. This is descriptive densification; paper tex/figs code is read-only.

Config SHA256 `898e76199d7c0a489907b7c5e2def123be7a3f95db41d580ba6656c4afed7ca8`.

|source|SHA256|
|---|---|
|ce-src/analyze_ce.py|92b02534dfe396bb805cbd78daa4517f1bed549c22e0885ffa41770cd38a92c7|
|ce-src/ce_driver.py|c9e1601ea6e55dfb975b80bcb00563274b8e237fbf602d2d0e1c0e330f93a4e2|
|ce-src/ce_reference_local.py|844b26905c5025fff5ab0a401b8bf08eee1b322738b1e10ebabf9f5a8c5641bc|
|ce-src/frozen_engine.py|9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989|
|ce-src/s_ce_original.py|6650bc8d59d73479a8952096781f8267c7af70b1b5019c667562f666a2622f9d|
|ce-src/x8_original.py|bd4a810d615c4630e27b2e99f98b49dcaff61727343fcdf3852e070536c01af0|

X10a requested/actual Grace spend0/0SU. X10b requested/actual0/0SU remains stopped separately. X9 requested47.9333333SU plus2reportreserve<=50 and its accepted formal chain continues.
