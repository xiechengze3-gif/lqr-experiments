"""Check the rank-to-Frobenius step using saved CE policies, without new solves."""
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--rank4", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records, summary, sources = [], [], {}
    for rank in (2, 4, 8, 32, 500):
        root = args.rank4 if rank == 4 else args.original
        verification = read(root / "verification.json")
        system_path = root / "systems" / f"r{rank:03d}.npz"
        assert digest(system_path) == verification["system_hashes"][str(rank)]
        sources[str(system_path)] = digest(system_path)
        with np.load(system_path, allow_pickle=False) as data:
            kstar = data["Kstar"]
        star_spectrum = np.linalg.svd(kstar, compute_uv=False)
        star_rank = int(np.count_nonzero(star_spectrum > 1e-10))
        assert star_rank <= rank
        for seed in range(200, 230):
            raw_path = root / "raw" / f"ce-r{rank:03d}-s{seed:04d}.json"
            raw = read(raw_path)
            sources[str(raw_path)] = digest(raw_path)
            for method in ("dense", "truncated"):
                q = next(row for row in raw["records"] if row["transitions"] == 131328
                         and row["method"] == method)
                policy_path = root / q["policy_file"]
                assert digest(policy_path) == q["policy_sha256"]
                sources[str(policy_path)] = q["policy_sha256"]
                with np.load(policy_path, allow_pickle=False) as data:
                    k = data["shared" if rank == 500 else method]
                spectrum = np.linalg.svd(k, compute_uv=False)
                delta = k - kstar
                ds = np.linalg.svd(delta, compute_uv=False)
                k_rank = int(np.count_nonzero(spectrum > 1e-10))
                delta_rank = int(np.count_nonzero(ds > 1e-10))
                fro2 = float(np.sum(delta**2))
                op2 = float(ds[0]**2)
                np.testing.assert_allclose(fro2, ds@ds, rtol=1e-12, atol=1e-18)
                if method == "truncated":
                    assert k_rank <= rank and delta_rank <= min(500, 2*rank)
                    assert fro2 <= min(500, 2*rank)*op2*(1+1e-10)
                rank_bound = min(500, 2*rank) if method == "truncated" else 500
                records.append(dict(
                    rank=rank, seed=seed, method=method, transitions=131328,
                    Kstar_numeric_rank=star_rank, Khat_numeric_rank=k_rank,
                    deltaK_numeric_rank=delta_rank,
                    Khat_tail_fro2_fraction=float(spectrum[rank:]@spectrum[rank:]/(spectrum@spectrum)),
                    deltaK_op2=op2, deltaK_fro2=fro2,
                    deltaK_effective_rank=fro2/op2,
                    rank_normalized_deltaK_fro2=fro2/rank,
                    rank_bound_for_deltaK=rank_bound,
                    rank_to_frobenius_bound_fraction=fro2/(rank_bound*op2),
                    gap=float(q["gap"]), gap_over_deltaK_fro2=float(q["gap"])/fro2,
                ))
        for method in ("dense", "truncated"):
            group = [q for q in records if q["rank"] == rank and q["method"] == method]
            fields = ("deltaK_op2", "deltaK_fro2", "deltaK_effective_rank",
                      "rank_normalized_deltaK_fro2", "rank_to_frobenius_bound_fraction",
                      "gap", "gap_over_deltaK_fro2")
            summary.append(dict(rank=rank, method=method, seeds=30,
                Khat_rank_min=min(q["Khat_numeric_rank"] for q in group),
                Khat_rank_max=max(q["Khat_numeric_rank"] for q in group),
                deltaK_rank_min=min(q["deltaK_numeric_rank"] for q in group),
                deltaK_rank_max=max(q["deltaK_numeric_rank"] for q in group),
                max_Khat_tail_fro2_fraction=max(q["Khat_tail_fro2_fraction"] for q in group),
                **{f"median_{key}":float(np.median([q[key] for q in group])) for key in fields}))
        print(json.dumps(dict(rank=rank, status="PASS", summary=summary[-2:])), flush=True)

    write_csv(args.output / "policy_diagnostics.csv", records)
    write_csv(args.output / "policy_summary.csv", summary)
    theory = dict(
        correction="A dense unknown A does not remove the rank benefit: "
                   "rank(Khat)<=r and rank(Kstar)<=r imply rank(Khat-Kstar)<=2r.",
        identification="Under suitable excitation/dependence assumptions, joint OLS "
                       "operator error is of order sqrt((n+m)/N), up to logs and conditioning.",
        truncation="If rank(B)=r, ||Bhat_r-B||_op <= 2 ||Bhat-B||_op.",
        CE_perturbation="In a stable local perturbation region, ||Khat-Kstar||_op "
                        "<= C_r max(||Ahat-A||_op,||Bhat_r-B||_op).",
        gap="gap <= ||Sigma_Khat||_op ||R+B'Pstar B||_op ||Khat-Kstar||_F^2 "
            "<= C'_r r(n+m)/N, with the stability threshold, logs and constants retained.",
        interpretation="This is a sufficient upper rate, not equality for realized N90. "
                       "Uniformly bounded constants alone do not make the upper bound tight or equal across ranks.",
        references=[
            dict(title="Stephen Tu thesis: Proposition 3.2.1 and equation (3.2.3), stable single-trajectory identification",
                 url="https://www2.eecs.berkeley.edu/Pubs/TechRpts/2019/EECS-2019-42.pdf#page=31"),
            dict(title="Mania, Tu, Recht: Lemmas 2-3 and equation (8); rank refinement is our deduction",
                 url="https://arxiv.org/pdf/1902.07826#page=7"),
        ],
        feedback_coordinates="For u=-K0*x+e, identify (F=A-B*K0,B) from [x,e], then "
                             "Ahat=Fhat+Bhat*K0. Unconstrained OLS on [x,u] is an invertible "
                             "reparameterization; norm bounds retain the coordinate-transform conditioning.",
        limitation="Proposition 3.1.1 uses independent rollout endpoints; Proposition 3.2.1 "
                   "instead treats stable single trajectories. Applying it in feedback coordinates "
                   "still requires accounting for K0, Gram conditioning, initialization and burn-in.",
    )
    (args.output / "audit.json").write_text(json.dumps(dict(
        status="PASS", analysis="Saved-policy SVD diagnostics only; no new samples or DARE solves",
        numeric_rank_absolute_tolerance=1e-10, policy_records=len(records),
        summary=summary, theory=theory, source_sha256=sources),indent=2)+"\n",encoding="utf-8")
    table = "".join(f"<tr><td>{q['rank']}</td><td>{q['Khat_rank_max']}</td>"
                    f"<td>{q['deltaK_rank_max']}</td><td>{q['median_deltaK_op2']:.6g}</td>"
                    f"<td>{q['median_deltaK_fro2']:.6g}</td>"
                    f"<td>{q['median_gap_over_deltaK_fro2']:.4f}</td></tr>"
                    for q in summary if q["method"] == "truncated")
    report = f"""<!doctype html><html lang="zh"><meta charset="utf-8"><title>CE 低秩策略界核查</title>
<style>body{{font:16px/1.6 system-ui;max-width:1080px;margin:30px auto;padding:0 20px}}
td,th{{border:1px solid #ccd4dd;padding:8px 12px}}table{{border-collapse:collapse}}</style>
<h1>CE：operator 估计误差 → 低秩策略 → Frobenius 控制误差</h1>
<p>修正：未知 A 是 dense，并不意味着控制误差必须承担完整 n² 的 Frobenius 参数量。
截断 B 后，CE 策略 Khat=(R+BtrᵀPhat Btr)⁻¹BtrᵀPhat Ahat 的 rank≤r；
真实 Kstar 的 rank≤r，因此 rank(Khat−Kstar)≤2r。</p>
<p>在激励充分、满足相应轨迹识别条件且处于稳定的局部扰动区间时，
联合 OLS 的 operator error 为 Õ(√((n+m)/N))；截断的 operator error 至多增大常数倍。
若 Riccati 局部敏感性可控制，则 ||Khat−Kstar||F²≤2r||Khat−Kstar||op²，
从而得到 gap≤Õ(Cr·r(n+m)/N)。这是沿原文扰动证明作出的 rank refinement，
不是原论文直接陈述了本实验的低秩定理。稳定性门槛与系统相关常数需要保留。</p>
<p>模型识别参考：<a href="https://www2.eecs.berkeley.edu/Pubs/TechRpts/2019/EECS-2019-42.pdf#page=31">
Stephen Tu thesis Proposition 3.2.1 / Eq. (3.2.3)</a>讨论稳定系统的单条轨迹。
对本实验的反馈采样，可先在 F=A−BK0 和外源探索输入 e 的坐标下识别，再以 Ahat=Fhat+Bhat K0 变回；
需要保留该变换的条件数、初始状态及 burn-in。独立 rollout 的 Proposition 3.1.1 不能直接用于本实验的预算计数。
策略与成本扰动参考：<a href="https://arxiv.org/pdf/1902.07826#page=7">
Mania–Tu–Recht Lemma 2、Lemma 3 / Eq. (8)</a>。</p>
<h2>保存策略的直接核查</h2><p>固定 131,328 transitions，30 个正式 seeds。
表中误差是各自中位数；秩为该 rank 全部 seeds 的最大数值秩，阈值 1e-10。
同时检查 dense 对照，完整数据在 CSV 中。</p>
<table><tr><th>r</th><th>rank Khat</th><th>rank ΔK</th><th>||ΔK||op²</th>
<th>||ΔK||F²</th><th>gap / ||ΔK||F²</th></tr>{table}</table>
<p>验证上述上界不等于证明实测 sample complexity 严格等于 Cr·r(n+m)/epsilon。
即使 Cr 有共同上界，各 rank 上界的松紧程度与实际常数也可能不同。</p>
<p><a href="audit.json">结果、推导与源哈希</a> ·
<a href="policy_summary.csv">汇总 CSV</a> · <a href="policy_diagnostics.csv">逐策略 CSV</a></p></html>"""
    (args.output / "results.html").write_text(report,encoding="utf-8")
    shutil.copy2(__file__,args.output/Path(__file__).name)
    manifest = {p.name:digest(p) for p in args.output.iterdir()
                if p.is_file() and p.name != "manifest.sha256.json"}
    (args.output / "manifest.sha256.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(status="PASS",policy_records=len(records),output=str(args.output))),flush=True)


if __name__ == "__main__":
    main()
