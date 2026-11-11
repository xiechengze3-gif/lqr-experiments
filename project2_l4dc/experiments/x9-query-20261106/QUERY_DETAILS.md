# X9 QUERY — feasibility, reuse and full-rank interpretation

Authority: `CLAUDE_TASK.md`, `X9 QUERY (22:10 CDT 11/05)`. This is a draft answer, not PROTOCOL or GO. No X9 job, pilot, trajectory, model solve, estimator fit or controller evaluation has been run. Additional spend: **0 SU**. X8 also remains a draft. All X0–X8 records, fits, policies, releases and paper tex remain untouched.

## Q1 — Cost and completion window

With alpha=0 reused, either the proposed grid or the four-nonzero-dose alternative below needs four new alpha cells. Per alpha: 8 systems × 4 sampling seeds × 4 rungs × 2 algorithms = 256 paired paths, or 512 arm paths. Across four alphas this is 1,024 paired paths / 2,048 arm paths. Every burn block, baseline block and absorbing-failure padding transition is counted. Per-arm transitions per algorithm at the four rungs are 2,964,976 / 11,846,384 / 47,372,272 / 189,475,712; the complete four-alpha formal grid is **128,849,584,128 primitive transitions**. These counts reproduce the frozen X6b integer schedules; they are not just N_cal times a stage count.

The saved n24 X6b allocation plan requests 1 CPU and 2 GiB per task:

| Per-alpha task group | Tasks | Limit per task | Requested upper SU |
|---|---:|---:|---:|
| Three low rungs, both algorithms | 32 | 8 min | 4.2667 |
| Full rung, NPG | 32 | 7 min | 3.7333 |
| Full rung, PI | 32 | 7 min | 3.7333 |
| Total per alpha | 96 | — | 11.7333 |

Reusing these limits gives **46.9333 SU FORMAL** for the four new alphas. A proposed resource/equivalence PILOT reserve of **1 SU** and REPORT reserve of **2 SU** give **49.9333 SU**, so a **50 SU draft cap** would cover this plan. This is a request for Claude's consideration, not an authorized cap. If full-rank resource measurements require a larger limit, report the revised plan and wait for its acceptance; no outcome-dependent cuts or automatic retries.

Proposed pilot scope after GO and the applicable acceptance: four jobs, each 1 CPU / 2 GiB / 15 min (1 SU requested total), using disjoint pilot systems at the smallest and largest approved nonzero alpha, for each algorithm, exercising both arms and the grouped schedule. This is resource/equivalence-only: time, RSS, transition accounting, source equivalence and output integrity; no gap-based grid or parameter selection. The detailed protocol must freeze the exact pilot ids and checks before submission.

Saved group-DONE timers for all 32 n24 tasks are 5,710.2631 s (low-three), 8,711.2524 s (full NPG), and 8,730.1519 s (full PI): **6.4310 one-core hours per alpha**, or **25.7241 core hours** for four. These are recorded run-body timers, **not billed SU** and not a new full-rank benchmark. Existing observed task maxima were 191.66 / 295.33 / 312.74 s, respectively. Full-rank paths have the same array dimensions and primitive counts; their timings still require the pilot.

At a **global concurrency of 8** one-core tasks across the entire experiment, the formal actor-body extrapolation is about **3 h 13 min**, and the sum of the requested task limits corresponds to about **5 h 52 min** of occupied running time. Add approximately 15 min of concurrently running pilot jobs and a planning allowance of 0.5–1.5 h for report work, plus Slurm queue time and Claude's gate reviews. Global concurrency must be enforced across arrays, not separately as eight per array. This assumes the earlier effective-core billing for 1 CPU / 2 GiB; recheck the current account, partition and billing weights before production.

If GO and the relevant protocol/formal gates permit an **08:00 America/Chicago start on Nov 6**, and resources are available, a reviewable report on **Nov 6 around 13:00–17:00** is a reasonable planning window. This is conditional, not a reservation or a queue forecast. No current queue/balance assertion is made. The computational size is compatible with the Nov 10 figure deadline under ordinary queue conditions, but an unresolved approval or infrastructure issue can move completion.

Evidence: `DRAFT_FEASIBILITY_v1.json`, `x6b_n24_timing_metadata_v1.json`, and the hashed original `X6b-protocol-v2/formal-plan.json`. All are metadata or planning arithmetic; no new benchmark was run for this answer.

## Q2 — Reuse alpha=0 without rerunning it

**Yes, the draft alpha=0 cell is the X6b n=m=24 cell, provided all frozen identities below are retained. Reuse the entire saved cell by reference, including failures and low rungs.** Do not rerun only the difficult paths or retain only stable paths.

The local metadata audit verified the five frozen scientific source hashes, eight n24 model-file hashes, and **256 existing paired path DONE receipts** (8 systems × 4 seeds × 4 rungs × 2 algorithms), with ids, exact schedules, transition counts and record counts. The audit does not claim a newly executed numerical-equivalence test. Its complete source/model/path references and hashes are in `x6b_reuse_identity_v1.json`.

Reuse identity:

- Family S; systems 301–308; sampling seeds 1701–1704; A, U, V from the original independent RNG streams; Q=R=W=I and K0=0.
- eta=0.2, nu=1, H=16; 16 pulse burn blocks and one baseline block per stage; NPG 16 updates, PI 8 updates; N_cal=524,288 and all four original **integer** schedules unchanged.
- NPG truncates only Zhat; PI uses PSD clipping plus joint compression and the full greedy solve. No critic, LSTD-PI, damping, new regularizer or safety update is inserted.
- Same pairing namespaces `rng(20 or 21, n, m, system, seed, stage)` with no arm or alpha argument. Each rung starts its own policy path, and states remain continuous within an arm/stage sequence as in X6b.

For alpha=0, load the original frozen binary model files; do not regenerate B using a full 24-column multiplication and assume bitwise equality to the original thin rank-2 multiplication. For alpha>0, a new model wrapper can retain the saved A and add `alpha * U_tail @ V_tail.T` to the original B, regenerating the full orthogonal matrices from the original frozen streams. Before formal use, verify consistency on compute and freeze the new wrapper/config hashes. The new wrapper must not overwrite the old model registry or sources.

The saved full-rung absolute medians are NPG dense **0.0579374614**, truncated **0.0148747138**; PI dense **0.1237451098**, truncated **0.0057514761**, with 32/32 stable in all four arms. Those are reference values from the saved summary, not new X9 results. Low-rung failures remain part of the alpha=0 reference. Reuse saves **11.7333 requested SU** and 32,212,396,032 primitive transitions relative to rerunning a fifth alpha.

Pairing across alphas means the same *exogenous Gaussian draws*, not identical observations. Positive-alpha state trajectories and estimates must be collected afresh; alpha=0 states, returns or estimates cannot stand in for them. For positive alpha, recompute Kstar, Pstar, Jstar and the initial-gap denominator for that B on compute for evaluation only. K0=0 makes P0 and J(K0) unchanged, but Jstar and g(K0) change with alpha. Never normalize positive-alpha records by the alpha=0 initial gap.

## Q3 — Grid placement and what it can establish

The proposed `{0, .02, .05, .1, .2}` is a sensible **small-tail robustness scan**. It is not enough to promise a crossover for both algorithms at this finite budget. In particular, PI has a much larger exact-rank gap advantage to begin with. Subtracting the saved group medians gives about 0.0431 for NPG and 0.1180 for PI, but these differences are **not paired effects or calibrated truncation-bias thresholds**. Neither `tau_2^2` nor alpha alone equals the cost penalty; dense performance also changes with B.

If the specific goal is to cover both continuity near rank 2 and a stronger tail stress test at the **same four-new-cell cost**, I suggest pre-registering **`{0, .05, .1, .2, .4}`**. The .4 endpoint replaces the near-baseline .02 dose rather than adding a post hoc run:

| alpha | tau_2^2 = 22 alpha^2 | Role in suggested grid |
|---:|---:|---|
| 0 | 0 | Reused exact-rank reference |
| .05 | .055 | Small, nonzero full-rank tail |
| .1 | .22 | Intermediate tail |
| .2 | .88 | Stronger approximation stress |
| .4 | 3.52 | Explicit large-tail negative control |

The .4 endpoint is a stress control, not a claimed small-tail theorem regime. Even this grid does **not guarantee** that the ratio crosses one: finite-budget estimation error can keep truncation favorable. All rungs and both algorithms must be reported regardless of the shape. No gap-based alpha selection or extra endpoint after inspecting formal results.

If Claude instead prioritizes a very small full-rank perturbation, keep the original grid and describe shrinkage/disappearance as a question rather than a promised outcome. Keeping .02 **and** adding .4 would cost five nonzero cells: 58.6667 SU FORMAL plus the same 3 SU reserve, about **62 SU** total requested; this is an alternative needing an explicit larger cap, not the default recommendation.

The ratios must remain medians of matched dense/truncated path ratios with system-level paired bootstrap, alongside failure-inclusive medians/IQR, stable/full counts, and first-failure stages. Dividing the two group medians is not the paired-ratio statistic. Existing X6b failures are included, and full-rank failures must be included under the same absorbing-failure/padding convention.

## Q4 — Core learner stays; model/report wrapper needs changes

**No full-rank-specific change is needed to the Stein collector or NPG/PI update mathematics.** Their matrix operations already support a general 24×24 B. They do not invert B or its small singular values. Zhat regresses on a state Gram matrix, with W=I supplying process excitation and nu=1 pulses in all input directions. A finite sample Gram can still be poorly conditioned; record such numerical failures and resource diagnostics, without silently adding ridge, whitening or a different estimator.

The frozen updates are:

- NPG: `K_next = K - eta * (R @ K + Z_used)`, where `Z_used = Zhat` for dense and `T_2(Zhat)` for truncation.
- PI v4: clip sym(Ghat) to Gplus; dense uses `(Gplus, Zhat)`. Truncated PI takes the leading two left singular vectors U of `[Gplus, Zhat]`, uses `G_used = U (U.T Gplus U) U.T` and `Z_used = U U.T Zhat`, and solves `(R + sym(G_used)) K_next = G_used K - Z_used`. With R=I and G_used PSD this solve is positive definite. A nonzero true tail does not require independently truncating G and Z or changing the greedy step.

**New namespace, model metadata and evaluation changes are necessary.** The old formal driver and actor checkpoint wrapper hard-code the X6b output root and exact-rank/basis assumptions. A versioned X9 wrapper must write only to a new X9 root, distinguish physical rank (24 for alpha>0) from retained order (2), preserve the frozen learner/collector and pairing, and freeze equivalence/source checks before formal work. Do not patch X6b in place.

For alpha>0, B has no true input nullspace. The old `analyze_actor.endpoint` assumes `B(I-V2 V2.T)=0` and asserts an exact gap decomposition; it must not be used unchanged. The assessor supports `basis=None`; a new report wrapper must make the exact-rank-only fields consistently null/N/A. Report **true redundant-cost share as N/A for positive alpha**, rather than treating the top-two complement as a nullspace. If a complement-action energy is additionally reported, label it as a descriptive quantity and do not claim an additive gap identity. For alpha=0, keep the existing valid decomposition and its saved values.

K0=0, the unchanged stable A and `||B||_op=1` for all suggested alpha<=1 preserve the P0 bound and the eta certificate. They do **not** establish a common finite-sample accuracy guarantee. With alpha>0, the true Z_K and joint `[G_K,Z_K]` can be full rank. Their tails depend on K and the plant, and are not numerically equal to the singular-value tail of B. Keep the old H, T and batch schedules exactly as requested; no new outcome-based calibration is implied by this answer.

The currently read paper (`sections/04-upper.tex`, read only) gives an accuracy bound with an approximation term `epsilon + C3 tau_k^2` for an admissible fixed k, and its every-iterate stabilization statement assumes the stated schedule/estimation and tail conditions. For X9, fixed k=2, the inherited empirical schedule, and especially the large-tail control have **not been certified** to meet all those numerical constants or small-tail conditions. A shrinking truncation advantage, a bias floor, or failures outside certified conditions do not by themselves contradict that theorem. Conversely, stability in this scan alone is not proof of the theorem's probability statement or an epsilon attainment claim. The PI remark has the analogous assumptions with different constants.

After GO, a preregistered diagnostic could compare the saved raw/processed estimates against their own-policy truth and separate estimation error from approximation tails, without feeding truth into the learner. It is optional report work to freeze in the protocol, not a new calculation performed for this query.

## Delivery checks and pending decision

The audit read saved JSON/CSV metadata and source/model bytes only. It did not import the scientific engine, load arrays for new numerical work, run simulations, fit estimators, solve for a new controller or submit anything. Source hashes are rechecked at append time; the original reply prefix is preserved byte-for-byte. Artifacts live only in `experiments/x9-query-20261106/`.

Await Claude's explicit **X9 GO**, approved grid/cap, and applicable stage acceptance before any pilot/formal submission. Continue monitoring both X8 and X9 review entries. Query spend remains **0 SU**; this answer does not alter any prior experiment budget or authorize new spend.
