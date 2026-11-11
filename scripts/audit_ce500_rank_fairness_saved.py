"""Audit CE500 pairing and distinguish B-recovery gains from control gains.

Uses saved records only: no sampling, DARE solves, or policy reevaluation.
"""
import argparse
import csv
import hashlib
import html
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import ScalarFormatter

RANKS = [2, 4, 8, 32, 64, 500]
FOCUS = [2, 4, 8, 32]
BUDGETS = [131328, 262400]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_save(path, records):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original", type=Path, required=True)
    p.add_argument("--rank4", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    sources = {}
    verification = {}
    configs = {}
    for name, root in (("original", a.original), ("rank4", a.rank4)):
        for filename in ("verification.json", "resolved_config.json", "identification-audit/audit.json"):
            path = root / filename
            sources[str(path.resolve())] = sha(path)
        verification[name] = read(root / "verification.json")
        configs[name] = read(root / "resolved_config.json")
        assert read(root / "identification-audit/audit.json")["status"] == "PASS"
        for relpath, digest in verification[name]["identity"]["sources"].items():
            path = root / "frozen" / relpath
            assert sha(path) == digest
            sources[str(path.resolve())] = digest
    shared_parameters = ("n", "b", "sigma", "burn", "chunk_size", "sampling_seed",
                         "sampling_route", "system_seed", "initialization_seed", "initial_gap")
    assert all(configs["original"][k] == configs["rank4"][k] for k in shared_parameters)
    records = {}
    checked_pairs = 0
    for rank in RANKS:
        root = a.rank4 if rank == 4 else a.original
        for seed in range(200, 230):
            path = root / "raw" / f"ce-r{rank:03d}-s{seed:04d}.json"
            raw = read(path)
            assert raw["seed"] == seed and raw["rank"] == rank
            assert raw["identity"] == verification["rank4" if rank == 4 else "original"]["identity"]
            sources[str(path.resolve())] = sha(path)
            keyed = {(row["transitions"], row["method"]): row for row in raw["records"]}
            assert len(keyed) == len(raw["records"])
            for budget in sorted({key[0] for key in keyed}):
                dense, trunc = [keyed[budget, method] for method in ("dense", "truncated")]
                for key in ("rank", "seed", "transitions", "actual_transitions", "ols_samples",
                            "A_error_fro2", "ols_residual", "policy_file", "policy_sha256"):
                    assert dense[key] == trunc[key], (rank, seed, budget, key)
                if rank == 500:
                    assert {k: v for k, v in dense.items() if k != "method"} == {
                        k: v for k, v in trunc.items() if k != "method"}
                checked_pairs += 1
            for budget in BUDGETS:
                for method in ("dense", "truncated"):
                    row = keyed[budget, method]
                    assert row["stable"] and row["failure"] is None
                    records[rank, seed, budget, method] = row

    stats, ratios = [], []
    rng = np.random.default_rng(2026102021)
    bootstrap_indices = rng.integers(0, 30, size=(2000, 30))
    for budget in BUDGETS:
        base = [records[500, s, budget, "dense"] for s in range(200, 230)]
        base_b = float(np.median([q["B_error_fro2"] for q in base]))
        base_gap = float(np.median([q["gap"] for q in base]))
        for rank in RANKS:
            for method in ("dense", "truncated"):
                group = [records[rank, s, budget, method] for s in range(200, 230)]
                berr = float(np.median([q["B_error_fro2"] for q in group]))
                gap = float(np.median([q["gap"] for q in group]))
                stats.append(dict(
                    transitions=budget, OLS_samples=budget-256, rank=rank, method=method,
                    seeds=30, median_B_error_fro2=berr,
                    median_A_error_fro2=float(np.median([q["A_error_fro2"] for q in group])),
                    median_optimality_gap=gap,
                    B_error_gain_over_full500=base_b / berr,
                    control_gap_gain_over_full500=base_gap / gap,
                    rank_r_B_manifold_dimension=rank*(1000-rank),
                    isotropic_B_dimension_ratio_reference=250000/(rank*(1000-rank)),
                ))
        for low, high in zip(FOCUS[:-1], FOCUS[1:]):
            row = dict(transitions=budget, low_rank=low, high_rank=high,
                       inverse_rank_expected_gain_ratio=high/low)
            for metric, key in (("B_error", "B_error_fro2"), ("control_gap", "gap")):
                lo = np.array([records[low, s, budget, "truncated"][key] for s in range(200, 230)])
                hi = np.array([records[high, s, budget, "truncated"][key] for s in range(200, 230)])
                ratio = float(np.median(hi) / np.median(lo))
                boot = np.median(hi[bootstrap_indices], axis=1) / np.median(lo[bootstrap_indices], axis=1)
                ci = np.quantile(boot, [0.025, 0.975])
                row.update({f"{metric}_adjacent_gain_ratio": ratio,
                            f"{metric}_ratio_bootstrap95_low": float(ci[0]),
                            f"{metric}_ratio_bootstrap95_high": float(ci[1])})
            ratios.append(row)
    csv_save(a.output / "fixed_budget_diagnostics.csv", stats)
    csv_save(a.output / "adjacent_diagnostic_ratios.csv", ratios)

    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, metric, title in zip(axes,
                                ("B_error_gain_over_full500", "control_gap_gain_over_full500"),
                                ("B-estimation error reduction", "Control optimality-gap reduction")):
        for budget, marker in zip(BUDGETS, ("o", "s")):
            group = [next(q for q in stats if q["transitions"] == budget and
                          q["rank"] == r and q["method"] == "truncated") for r in FOCUS]
            ax.plot(FOCUS, [q[metric] for q in group], marker+"-", label=f"{budget:,} transitions")
        rr = np.geomspace(2, 32, 200)
        anchor = next(q[metric] for q in stats if q["rank"] == 2 and
                      q["method"] == "truncated" and q["transitions"] == BUDGETS[0])
        ax.plot(rr, anchor*2/rr, "--", color="gray", label="1/r reference, anchored at rank 2")
        ax.set(xscale="log", yscale="log", xlabel="Actuation rank r", title=title,
               ylabel="Full500 dense error / rank-r truncated error")
        ax.set_xticks(FOCUS)
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.yaxis.set_major_formatter(ScalarFormatter())
        ax.grid(alpha=.2)
        ax.legend(fontsize=8, frameon=False)
    fig.suptitle("CE500 diagnostics: estimation gain and control gain at the same budget")
    fig.text(.5, .02, "Ratios of medians over 30 paired seeds. "
             "These fixed-budget diagnostics are not sample-complexity ratios.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0,.045,1,.94))
    for ext in ("png", "svg"):
        fig.savefig(a.output / f"model_vs_control_gain.{ext}", dpi=180)
    plt.close(fig)

    systems = verification["original"]["systems"] + verification["rank4"]["systems"]
    interpretation = dict(
        method_pairing="Same raw trajectory and joint full OLS; unchanged Ahat; only Bhat truncated.",
        cross_rank_constants={k: configs["original"][k] for k in shared_parameters},
        cross_rank_not_fixed=["B and its Frobenius norm", "Kstar and gap-calibrated K0",
                              "behavior closed-loop matrix", "state exploration covariance",
                              "Riccati and cost sensitivity to model errors"],
        fixed_budget_diagnostic_only=True,
        error_transfer_not_identified="Unknown-A and known-A/known-B interventions have not been compared; "
                                    "these summaries cannot establish that A error dominates.",
        feedback_OLS_algebra="Fhat = Ahat - Bhat*K0; keeping Ahat and replacing Bhat by Btr "
                             "implies Fhat_tr = Fhat + (Bhat-Btr)*K0. This identity alone gives no sign of cost change.",
        scope="One fixed random system family; cross-rank comparisons are empirical, "
              "not an isolated estimator scaling experiment.",
        bootstrap="2000 resamples of the 30 paired seeds; ratio of sample medians. "
                  "Intervals are conditional on the fixed system and budget, not continuous-budget N intervals.",
    )
    result = dict(status="PASS", analysis="saved-data only; no new model solves or samples",
                  checked_method_pairs=checked_pairs, formal_seeds=list(range(200,230)),
                  budgets=BUDGETS, adjacent_diagnostic_ratios=ratios,
                  system_checks=systems, interpretation=interpretation, source_sha256=sources)
    (a.output / "audit.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    rows = [q for q in stats if q["transitions"] == BUDGETS[0] and
            q["method"] == "truncated" and q["rank"] in FOCUS]
    table = "".join(f"<tr><td>{q['rank']}</td><td>{q['median_B_error_fro2']:.8g}</td>"
                    f"<td>{q['B_error_gain_over_full500']:.3f}×</td>"
                    f"<td>{q['median_optimality_gap']:.8g}</td>"
                    f"<td>{q['control_gap_gain_over_full500']:.3f}×</td></tr>" for q in rows)
    report = f"""<!doctype html><html lang="zh"><meta charset="utf-8">
<title>CE500 公平性与误差传递核查</title><style>body{{font:16px/1.6 system-ui;max-width:1100px;
margin:32px auto;padding:0 20px;color:#243447}}img{{max-width:100%}}table{{border-collapse:collapse}}
td,th{{padding:8px 14px;border:1px solid #ccd4dd;text-align:right}}</style>
<h1>CE500：公平性与误差传递核查</h1>
<p>本次仅重读保存结果，没有新增采样或求解策略。核对 {checked_pairs} 对 dense/truncated 记录，
所有配对的 A 估计误差、OLS residual、transition 数及策略文件出处相同；rank500 两方法记录完全一致。</p>
<p>两方法共享真实 trajectory 的完整联合 OLS：用 [x_t,u_t] 回归 x_{{t+1}}，
保持 Ahat 相同，仅对 Bhat 做 rank-r SVD 后 Riccati。已有原始 trajectory 回归和策略重放 audit 均 PASS。</p>
<h2>同预算诊断：131,328 transitions，30 seeds 的中位数</h2>
<p>这里两个收益分别是 full500 dense 的 B 误差/控制 gap 除以 rank-r truncated 的对应量。
这是诊断指标，不是达到同一 gap 的 sample complexity。</p>
<table><tr><th>Rank</th><th>B 误差平方</th><th>B 误差收益</th><th>Control gap</th>
<th>Control gap 收益</th></tr>{table}</table>
<img src="model_vs_control_gain.png" alt="同预算下模型估计收益与控制精度收益">
<h2>固定了什么</h2><p>A、U/V、b=1、Q/R/W=I、初始 gap=1、sigma=2、采样预算和外源随机源相同。
跨 rank 的 Kstar/K0、B 的 Frobenius 范数、闭环与探索状态协方差、误差到控制 gap 的权重不同。
固定初始 gap 只固定一个标量，不等于这些矩阵相同。</p>
<h2>解释边界</h2><p>未知左右子空间的 rank-r、500×500 矩阵自由度为 r(1000-r)。
在理想各向同性噪声和局部小误差条件下，B 估计的维数收益参考为 250000/[r(1000-r)]，
低 rank 时约与 1/r 成正比。控制 gap 同时受 A/B 的联合误差及 Riccati 敏感性影响。
不能由这些统计量直接判定 A 误差主导，也不能把模型误差改善倍数直接当作样本节省倍数。</p>
<p>反馈 OLS 的精确代数关系：Fhat=Ahat-Bhat K0。只截断 Bhat、保持 Ahat 时，
Fhat_tr=Fhat+(Bhat-Btr)K0；这表明结构化后处理也改变闭环估计，但不预先确定成本影响方向。</p>
<p><a href="audit.json">完整核查及源文件哈希</a> ·
<a href="fixed_budget_diagnostics.csv">诊断数据</a> ·
<a href="adjacent_diagnostic_ratios.csv">相邻收益比与配对 bootstrap 区间</a></p></html>"""
    (a.output / "results.html").write_text(report, encoding="utf-8")
    shutil.copy2(__file__, a.output / Path(__file__).name)
    assert all(sha(Path(path)) == digest for path,digest in sources.items())
    manifest = {path.name:sha(path) for path in a.output.iterdir()
                if path.is_file() and path.name != "manifest.sha256.json"}
    (a.output / "manifest.sha256.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(status="PASS", checked_method_pairs=checked_pairs,
                         fixed_budget_131328=rows, adjacent_ratios=ratios),indent=2))


if __name__ == "__main__":
    main()
