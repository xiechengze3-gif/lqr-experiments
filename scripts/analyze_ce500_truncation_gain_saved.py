"""Fit sample-saving gains against a common full-rank CE baseline.

Saved-data analysis only. No trajectories, model fits, or control policies are
regenerated. The four ranks are the user's requested 2, 4, 8, 32 comparison.
"""

import argparse
import csv
import hashlib
import html
import json
import os
import platform
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import ScalarFormatter


RANKS = [2, 4, 8, 32]
TARGETS = [0.1, 0.05]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sources = [args.input / name for name in (
        "sample_complexity.csv", "success_by_budget.csv")]
    source_hashes = {str(path.resolve()): sha256(path) for path in sources}
    summary, success = [read_csv(path) for path in sources]

    # Recompute every reported threshold from observed success counts.
    lookup = {}
    for row in summary:
        key = int(row["rank"]), row["method"], float(row["relative_target"])
        assert key not in lookup
        assert float(row["initial_gap"]) == 1.0 and int(row["seeds"]) == 30
        points = sorted((p for p in success if (
            int(p["rank"]), p["method"], float(p["relative_target"])) == key),
            key=lambda p: int(p["transitions"]))
        assert points and all(int(p["seeds"]) == 30 for p in points)
        qualifying = [p for p in points if int(p["successes"]) / 30 >= 0.9]
        assert qualifying, f"Unreached result requires censoring: {key}"
        assert int(qualifying[0]["transitions"]) == int(float(row["N_hat_90"]))
        assert int(qualifying[0]["successes"]) == int(row["successes"])
        lookup[key] = row
    assert len(lookup) == 24
    for target in TARGETS:
        dense = {int(p["transitions"]): p for p in success if
                 int(p["rank"]) == 500 and p["method"] == "dense" and
                 float(p["relative_target"]) == target}
        trunc = {int(p["transitions"]): p for p in success if
                 int(p["rank"]) == 500 and p["method"] == "truncated" and
                 float(p["relative_target"]) == target}
        assert dense.keys() == trunc.keys()
        assert all(dense[n][k] == trunc[n][k] for n in dense
                   for k in ("successes", "instabilities", "numerical_failures"))

    gains, adjacent, fits = [], [], []
    for target in TARGETS:
        baseline = lookup[500, "dense", target]
        baseline_n = int(float(baseline["N_hat_90"]))
        for rank in [2, 4, 8, 32, 64, 500]:
            row = lookup[rank, "truncated", target]
            n = int(float(row["N_hat_90"]))
            g = baseline_n / n
            same_rank_dense_n = int(float(lookup[rank, "dense", target]["N_hat_90"]))
            gains.append(dict(
                rank=rank, relative_target=target, included_in_fit=rank in RANKS,
                compression=500 / rank, full500_dense_N=baseline_n,
                truncated_N=n, previous_truncated_grid_budget=int(row["previous_tested_budget"]),
                sample_saving_G=g, budget_fraction_of_full=1 / g,
                gain_divided_by_compression=g / (500 / rank),
                same_rank_dense_N=same_rank_dense_n,
                same_rank_dense_over_truncated=same_rank_dense_n / n,
                successes=int(row["successes"]), seeds=int(row["seeds"]),
                success_ci95_low=float(row["success_ci95_low"]),
                success_ci95_high=float(row["success_ci95_high"]),
            ))
        data = [next(p for p in gains if p["rank"] == r and
                     p["relative_target"] == target) for r in RANKS]
        x = np.array([p["compression"] for p in data])
        y = np.array([p["sample_saving_G"] for p in data])
        # Direct least squares on gain with a zero intercept tests G = c*(500/r).
        c = float(x @ y / (x @ x))
        origin_prediction = c * x
        # A descriptive power fit permits an exponent different from one.
        alpha, log_c = np.polyfit(np.log(x), np.log(y), 1)
        power_prediction = np.exp(log_c) * x ** alpha
        fit = dict(
            relative_target=target, ranks=RANKS, full500_dense_N=baseline_n,
            origin_fit_model="G = c * (500/r); zero intercept",
            origin_fit_c=c,
            origin_fit_gain_rmse=float(np.sqrt(np.mean((y-origin_prediction)**2))),
            power_fit_model="G = c * (500/r)^alpha; least squares on log(G)",
            power_fit_c=float(np.exp(log_c)), power_fit_alpha=float(alpha),
            power_fit_predictions=power_prediction.tolist(),
            ideal_multiplicative_scaling_alpha=1.0,
            rank2_anchored_inverse_rank_predictions=(y[0] * 2 / np.array(RANKS)).tolist(),
        )
        fits.append(fit)
        for lo, hi in zip(data[:-1], data[1:]):
            observed = lo["sample_saving_G"] / hi["sample_saving_G"]
            expected = hi["rank"] / lo["rank"]
            adjacent.append(dict(
                relative_target=target, low_rank=lo["rank"], high_rank=hi["rank"],
                gain_ratio=observed, expected_inverse_rank_gain_ratio=expected,
                ratio_over_expected=observed / expected,
            ))

    write_csv(args.output / "gains.csv", gains)
    write_csv(args.output / "adjacent_gain_ratios.csv", adjacent)
    write_csv(args.output / "gain_fits.csv", [
        {key: value for key, value in fit.items() if not isinstance(value, list)}
        for fit in fits])
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.fonttype": "none"})
    for plot_kind in ("gain_vs_rank", "gain_vs_compression"):
        fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.8), sharey=True)
        for ax, target, fit in zip(axes, TARGETS, fits):
            data = [p for p in gains if p["relative_target"] == target and
                    p["rank"] in RANKS]
            r = np.array([p["rank"] for p in data])
            g = np.array([p["sample_saving_G"] for p in data])
            if plot_kind == "gain_vs_rank":
                rr = np.geomspace(2, 32, 200)
                ax.plot(r, g, "o-", color="#2469a0", label="Observed sample saving")
                ax.plot(rr, g[0] * 2 / rr, "--", color="#e28b24",
                        label="1/r reference, anchored at rank 2")
                ax.plot(rr, fit["power_fit_c"] * (500 / rr) ** fit["power_fit_alpha"],
                        ":", color="#668442", label=f"Power fit: exponent {fit['power_fit_alpha']:.3f}")
                ax.set(xscale="log", yscale="log", xlabel="Actuation rank r")
                ax.set_xticks(RANKS)
                ax.set_yticks([1, 2, 4, 8, 16, 32])
                ax.xaxis.set_major_formatter(ScalarFormatter())
                ax.yaxis.set_major_formatter(ScalarFormatter())
                ax.set_ylim(1, 34)
                for rank, gain in zip(r, g):
                    ax.annotate(f"{gain:.2f}x", (rank, gain), xytext=(0, 9),
                                textcoords="offset points", ha="center", fontsize=10)
            else:
                xx = np.linspace(0, 265, 200)
                ax.plot(500/r, g, "o", color="#2469a0", label="Observed sample saving")
                ax.plot(xx, fit["origin_fit_c"] * xx, "--", color="#e28b24",
                        label=f"Zero-intercept fit: G = {fit['origin_fit_c']:.4f}(500/r)")
                ax.set(xlabel="Compression 500/r", xlim=(0, 275), ylim=(0, 28))
                for rank, gain in zip(r, g):
                    ax.annotate(f"r={rank}", (500/rank, gain), xytext=(5, 7),
                                textcoords="offset points", fontsize=10)
            ax.set_title(f"Relative target {target:g} (initial gap = 1)")
            ax.set_ylabel("Sample-saving factor G")
            ax.grid(alpha=0.2)
            ax.legend(loc="lower left" if plot_kind == "gain_vs_rank" else "upper left",
                      fontsize=8, frameon=False)
        fig.suptitle("CE500: truncation gain relative to the common full-rank baseline")
        fig.text(0.5, 0.02, "G = N(full500, dense) / N(r, truncated). 30 paired seeds; "
                 ">=90% observed success. Descriptive fits; budget-grid uncertainty remains.",
                 ha="center", fontsize=9)
        fig.tight_layout(rect=(0, 0.045, 1, 0.94))
        for ext in ("png", "svg"):
            fig.savefig(args.output / f"{plot_kind}.{ext}", dpi=180)
        plt.close(fig)

    caveats = [
        "Fits use the four requested ranks 2, 4, 8, 32; ranks 64 and 500 are supplementary.",
        "The numerator is one common rank-500 dense threshold for each target. "
        "Same-rank dense comparisons are saved separately and do not enter this fit.",
        "G proportional to 500/r predicts G(2)/G(4)=2; it does not require the coefficient c to equal 1.",
        "All selected threshold points have 30/30 successes, Wilson 95% interval [0.8865,1]. "
        "Thus >=90% observed success is not a 95% lower-confidence guarantee of population success >=90%.",
        "Sample thresholds are the first successful tested budgets, not continuous-budget estimates. "
        "Rank-4 target 0.05 jumps from 19/30 successes at 41216 transitions to 30/30 at 65792. "
        "Point bootstrap intervals at these grid points do not remove grid resolution uncertainty. "
        "No fit confidence interval or population scaling claim is inferred.",
        "Common A and gap-1 initialization do not equalize control authority or behavior state distributions; "
        "cross-rank scaling remains an empirical observation for this fixed system.",
    ]
    # Confirm the quoted coarse-grid example directly from saved counts.
    for n, count in ((41216, 19), (65792, 30)):
        point = next(p for p in success if int(p["rank"]) == 4 and
                     p["method"] == "truncated" and float(p["relative_target"]) == 0.05
                     and int(p["transitions"]) == n)
        assert int(point["successes"]) == count

    result = dict(
        status="complete", analysis="saved-data only; no new experiments",
        primary_metric="G_epsilon(r) = Nhat_epsilon,0.9(rank500,dense) / Nhat_epsilon,0.9(rank_r,truncated)",
        hypothesis="G(r) proportional to 500/r; adjacent gain ratios equal inverse rank ratios",
        initial_optimality_gap=1.0, ranks_in_fit=RANKS, fits=fits,
        adjacent_gain_ratios=adjacent, caveats=caveats,
        validation=dict(thresholds_recounted=len(lookup), full500_success_identity=True,
                        source_sha256=source_hashes),
        environment=dict(python=platform.python_version(), numpy=np.__version__,
                         matplotlib=matplotlib.__version__,
                         paths={key: os.environ.get(key) for key in
                                ("TEMP", "TMP", "XDG_CACHE_HOME", "MPLCONFIGDIR")}),
    )
    (args.output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    table_rows = []
    for rank in RANKS:
        points = [next(p for p in gains if p["rank"] == rank and p["relative_target"] == t)
                  for t in TARGETS]
        table_rows.append(f"<tr><td>{rank}</td>" + "".join(
            f"<td>{p['truncated_N']:,}</td><td>{p['sample_saving_G']:.3f}×</td>" for p in points) + "</tr>")
    ratio_rows = [f"<tr><td>{p['relative_target']}</td><td>{p['low_rank']} → {p['high_rank']}</td>"
                  f"<td>{p['gain_ratio']:.3f}</td><td>{p['expected_inverse_rank_gain_ratio']:.0f}</td></tr>"
                  for p in adjacent]
    fit_text = "".join(f"<li>Target {f['relative_target']}: G = {f['origin_fit_c']:.6f}(500/r); "
                       f"power fit G = {f['power_fit_c']:.6f}(500/r)<sup>{f['power_fit_alpha']:.6f}</sup>.</li>"
                       for f in fits)
    report = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>CE500: sample-saving gains</title><style>
body{{font:16px/1.55 system-ui;max-width:1120px;margin:32px auto;padding:0 20px;color:#243447}}
table{{border-collapse:collapse;margin:18px 0}}td,th{{padding:8px 16px;border:1px solid #cdd5df;text-align:right}}
img{{max-width:100%}}code{{background:#eef2f6;padding:2px 4px}}</style>
<h1>CE500: truncation gain against one full-rank baseline</h1>
<p>Corrected analysis target: <b>G(r) = N(full500, dense) / N(rank r, truncated)</b>,
at the same final relative optimality gap and ≥90% observed success. Initial gap is 1.
The full baseline is 327,936 transitions (target 0.1) or 655,616 (target 0.05).</p>
<p>The inverse-rank hypothesis predicts G(2)/G(4) = 2, G(4)/G(8) = 2,
and G(8)/G(32) = 4. We fit the gain itself; a gap-versus-rank fit is a different analysis.</p>
<table><tr><th>Rank</th><th>N at target 0.1</th><th>Gain 0.1</th>
<th>N at target 0.05</th><th>Gain 0.05</th></tr>{''.join(table_rows)}</table>
<img src="gain_vs_rank.png" alt="Gains and rank-2 anchored inverse-rank reference">
<h2>Adjacent gain ratios</h2><table><tr><th>Target</th><th>Rank change</th>
<th>Observed G(low)/G(high)</th><th>Inverse-rank prediction</th></tr>{''.join(ratio_rows)}</table>
<h2>Descriptive fits</h2><ul>{fit_text}</ul>
<p>The four-rank gains decline with rank, while the fitted exponents differ from the ideal 1.
These data do not establish exact doubling of sample saving when rank halves.</p>
<img src="gain_vs_compression.png" alt="Gain versus compression with zero-intercept fit">
<h2>Practical limits</h2><ul>{''.join('<li>'+html.escape(c)+'</li>' for c in caveats)}</ul>
<h2>Saved evidence</h2><p>Source report: {html.escape(str(args.input))}.
No new trajectories were sampled. All 24 threshold summaries were recounted from success counts.
Configuration, source hashes, fits and validation are in <a href="analysis.json">analysis.json</a>;
gain data in <a href="gains.csv">gains.csv</a>, comparisons in
<a href="adjacent_gain_ratios.csv">adjacent_gain_ratios.csv</a>.</p></html>"""
    (args.output / "results.html").write_text(report, encoding="utf-8")
    shutil.copy2(__file__, args.output / Path(__file__).name)
    assert all(sha256(Path(path)) == value for path, value in source_hashes.items())
    manifest = {path.name: sha256(path) for path in args.output.iterdir()
                if path.is_file() and path.name != "manifest.sha256.json"}
    (args.output / "manifest.sha256.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status="complete", thresholds_recounted=len(lookup),
                         fits=fits, adjacent_gain_ratios=adjacent, output=str(args.output)), indent=2))


if __name__ == "__main__":
    main()
