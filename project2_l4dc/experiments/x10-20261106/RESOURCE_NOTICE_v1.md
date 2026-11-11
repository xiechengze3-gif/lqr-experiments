# X10 resource notice — stop/report before X10b submission

X10 GO acknowledged. Your rule is: "If your plan exceeds the cap, stop and report." Before a new benchmark I checked256 saved full-rung task timers, with receipt hashes. The conservative uniform-per-(n,algorithm) resource forecast already exceeds160 SU for FORMAL alone. X10b is therefore **not submitted**. This is a planning issue, not an experimental outcome or a new measurement.

All5 new rungs sum to0.66796875. Forecast each complete five-rung path as old full-rung maximum seconds ×0.66796875, then apply the required1.20×body+30s and round up to minutes,32tasks per cell:

|n|algorithm|saved full-rung maximum s|provisional task minutes|requested upper SU|
|---:|---|---:|---:|---:|
|24|NPG|295.3|5|2.6667|
|24|PI|312.7|5|2.6667|
|36|NPG|902.4|13|6.9333|
|36|PI|819.9|12|6.4000|
|48|NPG|2357.7|32|17.0667|
|48|PI|2307.1|32|17.0667|
|72|NPG|7201.4|97|51.7333|
|72|PI|8037.4|108|57.6000|

Total FORMAL requested upper **162.133333 SU**, before any pilot/report. The corresponding extrapolation from the *sum of old actual timers* is only **115.887 one-core body hours**. Thus I am not asserting that actual X10b consumption would exceed160; the mismatch comes from per-task worst-case limits, headroom and rounding. Actual full-rank X9 n24 pilot times were lower than the older n24 maxima, but extrapolating that speedup to n72 would be unmeasured.

Concrete bounded next option for your decision: authorize only the fixed pilot, **4.166667 requested SU inside the unchanged160 cap**: one1CPU/2GiB/10min equivalence task replaying saved n24,s301,seed1701,rung1/64,both algorithms (only the explicitly requested validation replay); and two1CPU/2GiB/120min resource tasks timing all5new rungs at n72, separate pilot system9102/seed9801, onealgorithm each, unchanged engine/no gap-based selection. The120min limits cover the old n72 worst-body forecast without risking a90min pilot timeout. Start these after X9's last array20413893, preserving global<=8. Then compute a measured formal plan with the frozen checks; if total pilot+formal+report still exceeds160, stop again without a cut or retry. **This option is not submitted or treated as an extra authorization.**

The deadline is not presently the binding issue: the uniform forecast corresponds to20.267h of eight-core formal allocation running time (plus remaining X9 time, up to2h concurrent resource pilot, reporting and queues), within the Nov8 18CT horizon under ordinary queues. No concurrency increase is requested. A queue guarantee is not implied.

Meanwhile X10a protocol preparation can proceed independently, using the expressly authorized local route with0GraceSU. The author-local X8 baseline was located and inventoried:4480 exact-family records and92160 geometric-family records; all8systems×4seeds and the ten2^9..18prefixes exist. Its absolute-gap amendment and source engine are preserved. Finite48-dimensional tail arithmetic verifies the requested new geometric effective ranks3/5/10/19 at epsilon.01, and3/6/11/21 at.005. No X8 baseline will be rerun, and no old file/paper tex changed. No X10 numerical pilot, formal learning, interpolation or controller evaluation has run yet.

Evidence: `experiments/x10-20261106/SOURCE_AND_COST_AUDIT_v1.json`, SHA256 `3441b4e1957b97e906a0d9f82f2b2d22acbd3cba5327b80a69100ae8015f9f20`. It binds source hashes,256 timing receipts, arithmetic and the X8 metadata inventory. X10 requested/actual new spend **0/0 SU**. Awaiting Claude's resource decision for X10b; X10a implementation/protocol and X9 monitoring continue.
