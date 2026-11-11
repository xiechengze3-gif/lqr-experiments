## X14f extension GO: complete nine-rung n = 60 cell at base B*; X14c also at B* (02:41Z 11/09)

The user decided in chat (2026-11-08, 20:40 CST) that the paper should treat n = 60 like the other dimensions
instead of excluding it. For that, n = 60 needs the same nine-rung ladder as the other dimensions, with base B*.

1. X14f-full: after (or together with) the X14f top-rung formal array, run the eight lower rungs B*/2^j,
   j = 1, ..., 8, for n = m = 60 with exactly the X14f/X12 frozen code, config, systems, seeds, RNG keys, schedule
   shape (NPG ceil((B*/2^j) 2^(t/16)) blocks per stage, PI with the same total), both arms, both algorithms,
   32 paths each. Together with the X14f top rung this gives a complete nine-rung n = 60 cell with base B*.
2. Report this cell exactly like the X12 n = 60 cell (summary rows in the X12/X6b schema, failure counts per
   rung, both-stable and failure-inclusive paired ratios with the same bootstrap, transitions-saved crossing on
   these nine rungs only, i.e. target = dense median gap at B*, truncated curve = the nine B*-base rungs). Also
   deliver merged files X12_summary_merged_B60.csv and X12_transitions_saved_merged_B60.csv in which the n = 60
   rows are the B*-base rows and all other rows are byte-identical to the current merged files. The X12 rule-base
   n = 60 rows stay in their original files.
3. X14c (after the formal arrays): on the X12 n = 60 pilot systems and seeds, report (i) the original rule result
   as specified, and (ii) whether the dense estimate satisfies the calibration criterion at B* for NPG
   (||Zhat_0 - Z_K0|| <= sigma_r(Z_K0)) and for PI (the joint estimate of Psi_K0, without and with the PSD
   projection), with the same code. Pilot systems only.
4. Cap for X14f including this extension: actual <= 250 SU, requested exposure <= 320 SU including report
   reserve. Measure, gate and stop exactly as before; no deletion or modification of existing files.


## Frozen extension inputs

The eight lower rungs cost 1,179,605,040 primitive transitions per arm of each algorithm. The sealed X14f top rung is reused and relabelled as 1 relative to B*. The two pilot tasks each exercise all eight lower rungs on X12 pilot 9102/9801. One CPU, 2 GiB, 160 minutes upper per pilot. Use the same X12 historical resource floor with the pilot to choose the formal wall cap. Only overlap with the original top-rung array if total queue reservation remains within 64. Use the existing X14f ledger.

- Claude review `34d8f762f12971da5d82eb0863132f12c41acfe8695e4a272e1af2874332ab53`
- Extension ruling `4df61df3e25e321e5500fa6653803e67ce2da8de050c5b222bc7f929450d920a`
- X14f top release `4ed35bc55bdd33ece61ce829958baab956a31a1729ff636e01fec1f790e54475`
- `actor_paths.py` `094cf07bb8b2534b97a34648cab20176304ad9dbdd3ffa25c17cf61a61e1a098`
- `frozen_engine.py` `9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989`
- `estimation.py` `f587bd48993288dbf9160dd4cc1e62542f15ee5794bda37590ec48dc672c9c59`
- `analyze_actor.py` `0e6e8291c573a6f3a6f491d135d91ddcfef1b7144f125004ad2d6bdb63d14b72`
- `virtual_task_store_v2.py` `73fb86e75df141b4ce89c901f9b450b1cccb71dcb33db2aad8e926addc91250c`
- `RESOURCE_HISTORY_FLOOR_X12.json` `9564f443985a1429aa254602f24db8e776d194dcc81765f9f4bde09e40b6f6e1`
- `models/n60-s301.npz` `8ebff4e831737f959ae379d822330708bd6dd5dd789b80e5e2daea44200435fe`
- `models/n60-s302.npz` `a3f45c5562def56b691183f6aa9bcce673af36162d38345fb771bb5a2ae240a0`
- `models/n60-s303.npz` `f306503edff37249b016b2dd2133953430c0979c1f1e52fd0180d6dbe8805f4e`
- `models/n60-s304.npz` `7566deacf8b9df08b0317ff28809ae1f0f0b0809983d50a1c08e5e79b397b665`
- `models/n60-s305.npz` `0b19771bbe269fc42ba790eb7689e6ef2c42783cd06807943b53f12cecfdbb1d`
- `models/n60-s306.npz` `c65dec66545bbafb7cd4e4d831dcd3c4603e231202a55a1d0e81b924b9e4ff49`
- `models/n60-s307.npz` `d8ad3ca2da6f448f302cc38f395d1fa42891f071946454b22eb7c91c4ee73bba`
- `models/n60-s308.npz` `872549e42d2b754bd8285f61b6343341330a09c4a84656d2b55460b256ca52ef`
- `run_actor_x14f_full.py` `19c0434b26949ac7554f3dac21785e3522866d0ced2b167f7e16936c3c87df9a`
- `x14f_full_ops.py` `8dc214612109ca46049ae3ca90fc2a032cb38802366660cf1601174d7fde80e7`
- `report_x14f_full.py` `1f5fd3623551b34c00530f94dc1e96ed1b0ad7ee9fef35e74b75f493f6556559`
- `config-x14f-full-v1.json` `907abd5605cd3061bae0229f8069d4f3c0288f4d1f5618c323141068fe8e5596`
- `X12_merged_original_summary.csv` `dfa928176031e212dbde19736f6ea915fe2590155d6f2ba166b1ff3e22f0c469`
- `X12_merged_original_transitions.csv` `82869c56fd13d3abd422df961894bd913e5c3e642e8edd0dadec53681f7a47b7`
