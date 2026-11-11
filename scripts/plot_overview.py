"""Small scientific figure assembled from completed Grace reports."""
import argparse
import csv
import json
import os
from pathlib import Path

if not os.environ.get("SLURM_JOB_ID"):
    raise RuntimeError("Run reporting on Grace compute nodes")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("--root", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
root = Path(args.root)
report_names = ["pilot-5d78e80516eb6812", "actor-refinement-197699f5", "tail-controls-47965418"]
data = {}
for name in report_names:
    report = root / name / "report"
    summary = json.loads((report / "summary.json").read_text())
    if summary["counts"]["missing"] or summary["counts"]["failed"]:
        raise RuntimeError("Overview requires complete reports")
    data[name] = list(csv.DictReader((report / "aggregate.csv").open()))

fig, axes = plt.subplots(2, 2, figsize=(12, 8))
colors = {"raw": "#555555", "B_rank_2": "#1468a8", "rank_2": "#1468a8", "oracle_subspace": "#39945e"}


def draw(ax, rows, mode, dimension, tail, shape, method, label, color, style="-", batch=None):
    chosen = [r for r in rows if r["mode"] == mode and int(r["n"]) == dimension
              and float(r["tail"]) == tail and r["tail_shape"] == shape and r["method"] == method
              and (batch is None or int(r["batch_blocks"]) == batch)]
    chosen = sorted([r for r in chosen if r["gap_median_available"] and float(r["transitions"]) > 0],
                    key=lambda r: int(r["transitions"]))
    if not chosen:
        raise RuntimeError(f"Missing plot series: {label}")
    if any(float(r["stable_rate"]) != 1 for r in chosen):
        raise RuntimeError("Add failure visualization before plotting conditional costs")
    ax.loglog([int(r["transitions"]) for r in chosen], [float(r["gap_median_available"]) for r in chosen],
              label=label, color=color, linestyle=style, marker="o", markersize=3)


pilot = data[report_names[0]]
for ax, dimension in zip(axes[0], (16, 32)):
    for method, label in (("raw", "Raw CE"), ("B_rank_2", "Truncate estimated B to rank 2")):
        draw(ax, pilot, "ce", dimension, 0., "flat", method, label, colors[method])
    ax.axhline(.2, color="#bbbbbb", linestyle=":", linewidth=1)
    ax.set_title(f"Exact rank: n=m={dimension}, r=2 (CE)")

ax = axes[1, 0]
controls = data[report_names[2]]
for rows, tail, shape, label, color in ((controls, .01, "flat", "flat tail 0.01", "#1468a8"),
                                       (controls, .05, "energy", "Frobenius tail norm 0.05", "#39945e"),
                                       (pilot, .05, "flat", "flat tail 0.05", "#b34530")):
    for method, style in (("B_rank_2", "-"), ("raw", "--")):
        draw(ax, rows, "ce", 16, tail, shape, method,
             f"{label}: {'truncated' if method == 'B_rank_2' else 'raw'}", color, style)
ax.set_title("Approximate rank: n=m=16 (CE)")

ax = axes[1, 1]
refinement = data[report_names[1]]
for method, label, style in (("raw", "Raw residual NPG", "-"),
                              ("rank_2", "Rank-2 residual NPG", "-"),
                              ("oracle_subspace", "True subspace reference", ":")):
    draw(ax, refinement, "actor", 16, 0., "flat", method, label, colors[method], style, batch=32768)
ax.axhline(1., color="#bbbbbb", linestyle=":", linewidth=1)
ax.set_title("Exact rank: n=m=16 (NPG, batch=32768 blocks)")

for ax in axes.flat:
    ax.set_xlabel("Primitive transitions (including all overhead)")
    ax.set_ylabel("Median absolute cost gap")
    ax.grid(alpha=.2)
    ax.legend(fontsize=7)
fig.suptitle("Rank truncation pilot: 2 systems x 2 trajectories; all plotted runs stable", fontsize=12)
fig.tight_layout()
output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(output.with_suffix(".png"), dpi=170)
fig.savefig(output.with_suffix(".pdf"))
print(str(output.with_suffix(".png")), flush=True)
