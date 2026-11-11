"""Separate uniform norm bounds from realized rank-normalized CE error.

Only reads saved systems and saved-policy diagnostics. No trajectories or DARE.
"""
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def op(matrix):
    return float(np.linalg.svd(matrix, compute_uv=False)[0])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original", type=Path, required=True)
    p.add_argument("--rank4", type=Path, required=True)
    p.add_argument("--policy-audit", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    policy_path = a.policy_audit / "policy_diagnostics.csv"
    policy = read_csv(policy_path)
    sources = {str(policy_path):sha(policy_path)}
    norms, factors = [], []
    common_original_p0 = None
    for rank in (2, 4, 8, 32, 500):
        root = a.rank4 if rank == 4 else a.original
        path = root / "systems" / f"r{rank:03d}.npz"
        check = json.loads((root / "verification.json").read_text(encoding="utf-8"))
        assert sha(path) == check["system_hashes"][str(rank)]
        sources[str(path)] = sha(path)
        with np.load(path, allow_pickle=False) as archive:
            s = {k:archive[k] for k in ("A", "B", "K0", "Kstar", "Pstar", "P0", "P0_original")}
        if common_original_p0 is None:
            common_original_p0 = s["P0_original"].copy()
        else:
            np.testing.assert_array_equal(common_original_p0, s["P0_original"])
        h = np.eye(500) + s["B"].T @ s["Pstar"] @ s["B"]
        norms.append(dict(rank=rank, A_op=op(s["A"]), B_op=op(s["B"]),
                          Kstar_op=op(s["Kstar"]),
                          Pstar_op=float(np.linalg.eigvalsh(s["Pstar"])[-1]),
                          cost_weight_op=float(np.linalg.eigvalsh((h+h.T)/2)[-1]),
                          K0_op=op(s["K0"]),
                          behavior_closed_loop_op=op(s["A"]-s["B"]@s["K0"]),
                          optimal_closed_loop_op=op(s["A"]-s["B"]@s["Kstar"]),
                          P0_op=float(np.linalg.eigvalsh(s["P0"])[-1]),
                          common_original_P0_op=float(np.linalg.eigvalsh(s["P0_original"])[-1])))
        group = [q for q in policy if int(q["rank"]) == rank and q["method"] == "truncated"]
        assert len(group) == 30
        values = []
        for q in group:
            op2, fro2, gap = [float(q[k]) for k in ("deltaK_op2", "deltaK_fro2", "gap")]
            n = int(q["transitions"])
            left = n*gap/(1000*rank)
            ell = n*op2/1000
            shape = fro2/(rank*op2)
            weight = gap/fro2
            np.testing.assert_allclose(left, ell*shape*weight, rtol=1e-13)
            values.append((ell, shape, weight, left))
        gm = np.exp(np.mean(np.log(values), axis=0))
        np.testing.assert_allclose(gm[3], np.prod(gm[:3]), rtol=1e-13)
        factors.append(dict(rank=rank, seeds=30, transitions=131328,
                            gm_operator_error_coefficient=float(gm[0]),
                            gm_spectral_shape_F2_over_r_op2=float(gm[1]),
                            gm_cost_weight_gap_over_F2=float(gm[2]),
                            gm_rank_normalized_gap_coefficient=float(gm[3])))
    write_csv(a.output / "system_norms.csv", norms)
    write_csv(a.output / "realized_error_factors.csv", factors)
    result = dict(
        status="PASS", analysis="Saved-system norm and saved-policy arithmetic only",
        theory="Uniform gap <= C*r*(n+m)/N does not assert gap = C*r*(n+m)/N. "
               "A common upper constant does not require each rank to attain the bound.",
        exact_samplewise_factorization="N*gap/[r*(n+m)] = [N*||deltaK||op^2/(n+m)] "
                                       "* [||deltaK||F^2/(r*||deltaK||op^2)] * [gap/||deltaK||F^2]",
        aggregation="Geometric means preserve this multiplicative identity exactly; "
                    "these are descriptive fixed-budget diagnostics, not N90 sample-complexity estimates.",
        algebraic_example="With fixed 0<a<1 and delta_N, an error matrix with singular values "
                          "delta_N, a*delta_N,...,a*delta_N (2r values) has the same operator norm "
                          "for every r, but Frobenius square delta_N^2*[1+(2r-1)*a^2]. "
                          "This is an example for the norm inequality, not a constructed LQR counterexample.",
        common_original_certificate_bitwise_equal=True,
        system_norms=norms, realized_factors=factors, source_sha256=sources,
    )
    (a.output/"audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    rows = "".join(f"<tr><td>{q['rank']}</td><td>{q['A_op']:.6f}</td><td>{q['B_op']:.6f}</td>"
                   f"<td>{q['Pstar_op']:.6f}</td><td>{q['Kstar_op']:.6f}</td>"
                   f"<td>{q['cost_weight_op']:.6f}</td></tr>" for q in norms)
    frows = "".join(f"<tr><td>{q['rank']}</td><td>{q['gm_operator_error_coefficient']:.6f}</td>"
                    f"<td>{q['gm_spectral_shape_F2_over_r_op2']:.6f}</td>"
                    f"<td>{q['gm_cost_weight_gap_over_F2']:.6f}</td>"
                    f"<td>{q['gm_rank_normalized_gap_coefficient']:.6f}</td></tr>" for q in factors)
    report = f"""<!doctype html><html lang="zh"><meta charset="utf-8"><title>CE500 统一常数核查</title>
<style>body{{font:16px/1.65 system-ui;max-width:1100px;margin:30px auto;padding:0 20px}}
td,th{{padding:7px 12px;border:1px solid #ccd4dd}}table{{border-collapse:collapse}}</style>
<h1>CE500：统一的 rank-independent 上界与实测缩放</h1>
<p>本次重读保存的系统与策略误差。关键区别：统一 gap≤C·r(n+m)/N 的上界，
并不要求各 rank 的真实误差都等于该上界。即使使用同一 C，也不能推出样本需求精确按 r 成正比。</p>
<h2>主要谱范数确实基本不随 rank 变化</h2>
<table><tr><th>r</th><th>||A||op</th><th>||B||op</th><th>||Pstar||op</th>
<th>||Kstar||op</th><th>||I+BᵀPstar B||op</th></tr>{rows}</table>
<p>原始共同稳定策略的 P0 也逐元素相同。它为 Pstar 提供共同上界；
不能因为实际矩阵 Pstar、Kstar 或探索协方差不同，就断言理论一定需要一个随 rank 恶化的常数。</p>
<h2>实测误差的精确分解</h2>
<p>令 E=Khat−Kstar。每个保存策略均满足：</p>
<p>N·gap/[r(n+m)] = [N||E||op²/(n+m)] × [||E||F²/(r||E||op²)] × [gap/||E||F²]。</p>
<p>下面用 30 seeds 的几何平均，乘积恒等式保持精确。预算固定 131,328；
这是定位机制的诊断，并非替代同一 gap 下的 N90。</p>
<table><tr><th>r</th><th>operator 系数</th><th>谱形状因子 F²/(r·op²)</th>
<th>成本权重 gap/F²</th><th>三项乘积</th></tr>{frows}</table>
<p>秩只限制非零奇异值的个数，不规定它们的平均能量。
在低秩区间 F²≤2r·op²；取等号要求这 2r 个奇异值都达到最大值。
实测谱形状因子明显变化，因此统一 operator 界并不意味着 F² 精确正比于 r。</p>
<h2>单看范数转换的反例</h2><p>固定 a∈(0,1)，令一个秩 2r 的误差矩阵有奇异值
δ、aδ、…、aδ。所有 r 的 operator norm 都是 δ，但 F²=δ²[1+(2r−1)a²]，
包含非零截距。这里没有让 a 随 rank 变化，却不能得到严格的翻倍关系。
此例只说明不等式的逻辑，不声称它是已构造的 LQR 系统。</p>
<p><a href="audit.json">完整结果及源哈希</a> · <a href="system_norms.csv">系统范数</a> ·
<a href="realized_error_factors.csv">误差分解数据</a>。</p></html>"""
    (a.output/"results.html").write_text(report,encoding="utf-8")
    shutil.copy2(__file__,a.output/Path(__file__).name)
    (a.output/"manifest.sha256.json").write_text(json.dumps({p.name:sha(p) for p in a.output.iterdir()
        if p.is_file() and p.name!="manifest.sha256.json"},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(status="PASS", system_norms=norms, realized_factors=factors),indent=2))


if __name__ == "__main__":
    main()
