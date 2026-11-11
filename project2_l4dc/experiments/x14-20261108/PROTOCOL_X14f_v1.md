## X14f GO: n = 60 at a budget in line with n(n+m); order of the remaining items (22:05Z 11/08)

The user decided in chat (2026-11-08, 16:03 CST) to rerun n = 60 at a comparable budget. Reason: the paper's
new Table 2 compares the dense/truncated ratios across n = m in {24, 36, 48, 72}, whose largest budgets are
2^19, 2^20, 2^21, 2^22 blocks, i.e. 455, 405, 455, 405 blocks per unit of n(n+m). For n = 60 the calibration rule
selected 2^21 blocks (291 per unit), so its NPG cells (gap ratio 8.20, transition ratio 5.68) are not comparable.

### X14f  n = m = 60 at the budget B* = 3,276,800 blocks (priority: right after X14b FORMAL/REPORT)
- B* = 2^21 * (60*120)/(48*96) = 3,276,800 blocks, i.e. 455.1 blocks per unit of n(n+m), equal to n = 24 and
  n = 48. This is a disclosed post-hoc supplementary budget, not an output of the calibration rule; the X12 rule
  results stay as they are and remain the registered n = 60 results.
- Everything else exactly as X12 (frozen X12 code, config, systems, seeds, RNG keys, eta = 0.2, H = 16, 17 burn-in
  and baseline blocks per stage, NPG 16 stages with ceil(B* 2^(t/16)) blocks, PI 8 stages with the same total
  number of transitions, both arms, both algorithms, 32 paths each). Only the largest budget is run (one new rung,
  B* in place of N_cal); no smaller rungs.
- Report in the X12/X6b summary schema (new rows, rung recorded as B*/2^21 = 1.5625, primitive counts exact):
  failure-inclusive and both-stable paired ratio medians with the same bootstrap; dense and truncated gap and
  relative-gap medians; stable counts; D/gap of the dense arms. Transition ratio: target = dense median gap at
  B*; truncated median curve = the nine X12 rungs plus the B* rung on the primitive-transition axis, with the
  same cross arithmetic and censoring rules as X12. Report whatever comes out.
- Cap for X14f alone (separate book from X14a-e): actual <= 150 SU, requested exposure <= 200 SU including a
  4 SU report reserve. Timing pilot on the X12 pilot systems first; if the forecast exceeds the cap, stop and
  report the numbers. Same storage and quota gates as X12/X14; no deletion or modification of existing files.

### Order of the remaining items (changes the priority of X14c-e only)
1. X14e now, in parallel with the running X14b formal array (0 SU, saved data or local): the paper needs the CE
   paired gap ratio at N = 524288 for n = m = 60 (same function and both-stable convention as the CE ratio table).
2. X14b FORMAL and REPORT as planned.
3. X14f as above.
4. X14c, then X14d.
All other X14 rules and the pre-registration stay unchanged.


## Frozen X14f inputs and execution

Primitive transitions per arm and algorithm 1,184,199,632, with identical integer budgets. Timing uses the X12 pilot system 9102 and seed 9801, one two-arm path per algorithm, one CPU and 2 GiB, with a 160 minute upper request. The measured bodies and the original X12 historical per-transition floors gate the 64-task formal array. All formal models retain their original X12 bytes. Training, summary and cross functions retain their original source bytes. The report sets the X12 crossing rung-count guard and metadata to ten. A separate archive adapter supplies raw paths.

- Claude review `a53fe7ee42848bef9c5b4e36d51d9f7c30cdaa5ff76f573833338a4a255e0d82`
- X14f ruling `8f48b9bc88f832ad316e1cd17c208bb495642f83e35fd18e24bcd0c9ab630980`
- `actor_paths.py` `094cf07bb8b2534b97a34648cab20176304ad9dbdd3ffa25c17cf61a61e1a098`
- `frozen_engine.py` `9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`
- `estimation.py` `f587bd48993288dbf9160dd4cc1e62542f15ee5794bda37590ec48dc672c9c59`
- `analyze_actor.py` `0e6e8291c573a6f3a6f491d135d91ddcfef1b7144f125004ad2d6bdb63d14b72`
- `paper_cross.py` `d07e548f861e7edf4191c9735015553706d012dfca2077adc7b5d212ea9e5a8e`
- `report_products_v1.py` `256cbb43b6c3ab191a7ce76f43ab726cf97f72346e03866be8522865679286d4`
- `X12_formal_config_readonly.json` `194f34ba2af8bd822396a9ae1e2317219ee5beb2da4f9a54df1d3eb479097d14`
- `virtual_task_store_v2.py` `73fb86e75df141b4ce89c901f9b450b1cccb71dcb33db2aad8e926addc91250c`
- `run_actor_x14f.py` `dffeb1ef27ca1ceab87258a2e6e4e85f3705c715a9b1e3dffdab54f924db331f`
- `x14f_ops.py` `35524575d23e1538f9f87fbd8ad12c0fb96c62e586e2948334a2ee1572316a4b`
- `report_x14f.py` `86edcf3e2149ec0950336c185eae1877c7d7459bda8fca7bfe03d0c7435f56b7`
- `RESOURCE_HISTORY_FLOOR_X12.json` `9564f443985a1429aa254602f24db8e776d194dcc81765f9f4bde09e40b6f6e1`
- `X12_n60_nine_rungs_summary.csv` `a5fcc7ecc5e68c4723389e6c9672252c57fe11b9443bcf63b5eef8bfce32c5bf`
- `models/n60-s301.npz` `8ebff4e831737f959ae379d822330708bd6dd5dd789b80e5e2daea44200435fe`
- `models/n60-s302.npz` `a3f45c5562def56b691183f6aa9bcce673af36162d38345fb771bb5a2ae240a0`
- `models/n60-s303.npz` `f306503edff37249b016b2dd2133953430c0979c1f1e52fd0180d6dbe8805f4e`
- `models/n60-s304.npz` `7566deacf8b9df08b0317ff28809ae1f0f0b0809983d50a1c08e5e79b397b665`
- `models/n60-s305.npz` `0b19771bbe269fc42ba790eb7689e6ef2c42783cd06807943b53f12cecfdbb1d`
- `models/n60-s306.npz` `c65dec66545bbafb7cd4e4d831dcd3c4603e231202a55a1d0e81b924b9e4ff49`
- `models/n60-s307.npz` `d8ad3ca2da6f448f302cc38f395d1fa42891f071946454b22eb7c91c4ee73bba`
- `models/n60-s308.npz` `872549e42d2b754bd8285f61b6343341330a09c4a84656d2b55460b256ca52ef`
- `config-x14f-v1.json` `c565732ef7447c5a70d5d9f18fcee048f2278207cfd8e0d59c2739c1613a8637`
