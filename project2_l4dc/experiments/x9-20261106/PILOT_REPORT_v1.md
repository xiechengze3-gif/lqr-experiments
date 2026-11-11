# X9 PILOT

Resource-only array20413460: all4 COMPLETED, no retry. All8 comparisons PASS bitwise gains/collector outputs/RNG/counts. No gap/stability/performance was read out or used for selection. The full4-rung real actor paths were timed; controls, pairing and integer schedules are unchanged. Each task used503421344 primitive transitions including equivalence/reference work; total2013685376. Formal observations collected:0. Prepared32 deterministic positive-alpha model inputs for evaluation-only truth; all local model bytes and registry SHA256s verified without numerical array loading.

|task|alpha|algorithm|seconds at rungs1/64,1/16,1/4,1|process peak RSS KiB|equivalence|
|---:|---:|---|---|---:|---|
|0|0.05|NPG|5.068/17.915/70.395/266.185|127132|PASS (both alpha0 and positive alpha)|
|1|0.05|PI|4.556/17.546/65.536/262.500|126872|PASS (both alpha0 and positive alpha)|
|2|0.4|NPG|4.849/17.459/67.113/265.422|126984|PASS (both alpha0 and positive alpha)|
|3|0.4|PI|4.516/16.854/65.195/261.531|126944|PASS (both alpha0 and positive alpha)|

Slurm elapsed times397/388/393/388s, all billing=1. Completed Slurm elapsed cost **0.435000 SU**; requested **1/50 SU**. AMS has no matching own-X9 row at 2026-11-06T04:49:36.827952Z, so settlement is pending; do not call its missing entry zero or add it to Slurm. Maximum Slurm/process RSS 130332 KiB (127.277 MiB), memory headroom 93.79% of2GiB, exceeding20%.

Measured maxima: full NPG 266.185s, full PI 262.500s; the conservative combined low-three body is 181.017s. Frozen wall guards1.20*body+30 are 349.422s / 345.001s / 247.220s, within420/420/480s. PASS. No limit or scientific grid change needed.

FORMAL plan:12 sequential arrays ×32 tasks,1CPU/2GiB, per alpha8min(low-three both algorithms),7min(full NPG),7min(full PI); global concurrency<=8, afterok order, automatic retries0. Four new alphas.05/.1/.2/.4; alpha0 reused in full. Requested **46.933333 SU**, plus pilot1 and REPORT reserve2 = **49.933333/50 SU**. Real actor-body estimate at8cores 3.154h; requested allocation envelope 5.867h, plus queue/review/report time. Source/config hashes and each32-model registry are in the frozen formal config/plan. No formal submission yet.

Formal config SHA256 `580561a73a44a652a3e909b10fd60fb68aab7b79c4e900eee7b7f86b5e8a3dcd`. All5 scientific hashes equal the PROTOCOL freeze. Source checks,32 model hashes and70 transferred member hashes PASS. Pilot model solves were input/evaluation preparation, with no formal sampling, retuning or performance selection. Exact-rank redundant-cost shares remain baseline-only; positive-alpha fields are N/A. The registered empirical scan is outside numerically certified Theorem3 conditions, not a theorem verification.

Files: `experiments/x9-20261106/` PILOT_REPORT_v1.md, PILOT_ACCOUNTING_v1.json, PILOT_DELIVERY_VERIFIED_v1.json, pilot-delivery-v1/, and prepared-formal-v1/formal-config.json/formal-plan.json. No old results/releases/paper tex changed. Await your explicit **PILOT ACCEPTED** before FORMAL.
