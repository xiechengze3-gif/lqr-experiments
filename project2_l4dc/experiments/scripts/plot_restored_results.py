#!/usr/bin/env python3
"""Portable plots for restored groups 01/04; saved tables only, no learning.

Public entrypoint: run(root, plt, np) -> {group_name: status}.
Original tables are checked against the archival SHA-256 retrieval manifest.
Failed observations remain in the complete denominator and have infinite loss.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path

G1 = "01_input_padding"
G4 = "04_ce100_matched_gap_and_high_rank"
COLORS = {"dense": "#426ca6", "raw": "#426ca6", "truncated": "#d97535", "adaptive": "#398859"}
LABELS = {"dense": "Dense", "raw": "Dense", "truncated": "Known-rank truncated", "adaptive": "Empirical adaptive"}


def configure_paths(root):
    for key, folder in (("MPLCONFIGDIR", "matplotlib"), ("XDG_CACHE_HOME", "cache"),
                        ("TEMP", "tmp"), ("TMP", "tmp"), ("TMPDIR", "tmp")):
        target = root / ".runtime" / folder
        target.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(target)


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    if not rows:
        raise ValueError(f"No rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def number(value, default=math.nan):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def yes(value):
    return str(value).lower() in ("true", "1")


def stable(row):
    return yes(row["stable"]) and all(yes(row.get(key, "true")) for key in ("complete", "whole_path_stable", "observed"))


def quantile(values, probability):
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    if low == high or ordered[low] == ordered[high]:
        return ordered[low]
    if math.isinf(ordered[high]):
        return math.inf
    return ordered[low] + (index - low) * (ordered[high] - ordered[low])


def summarize(rows, fields, metrics, repeat_fields, expected):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key, "") for key in fields)].append(row)
    result = []
    for key, observations in groups.items():
        ids = [tuple(row.get(k, "") for k in repeat_fields) for row in observations]
        if len(ids) != len(set(ids)) or len(observations) != expected:
            raise ValueError(f"Incomplete or duplicate repeat denominator: {key}: {len(ids)}")
        failures = sum(not stable(row) for row in observations)
        for metric in metrics:
            vals = [number(row.get(metric)) if stable(row) else math.inf for row in observations]
            if any(math.isnan(value) for value in vals):
                raise ValueError(f"Stable output missing metric {metric}: {key}")
            result.append(dict(zip(fields, key), metric=metric, count=len(vals), failure_count=failures,
                               stable_count=len(vals)-failures, failure_rate=failures/len(vals),
                               median=quantile(vals, .5), q25=quantile(vals, .25), q75=quantile(vals, .75),
                               worst=max(vals), denominator="all repeats; failed outputs=+inf"))
    return result


def verified_sources(root):
    manifest = json.loads((root / "provenance/retrieval_manifest.json").read_text(encoding="utf-8"))
    count = 0
    for entry in manifest["files"]:
        target = root / entry["target"]
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Archival hash mismatch: {target}")
        count += 1
    return count


def save(root, output, stem, fig, plt):
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for extension in ("png", "svg", "pdf"):
        path = output / f"{stem}.{extension}"
        fig.savefig(path, dpi=200, bbox_inches="tight")
        paths.append(path.relative_to(root).as_posix())
    plt.close(fig)
    return paths


def curve(ax, records, xfield, label, color, metric="median", band=True, style="-"):
    ordered = sorted(records, key=lambda r: number(r[xfield]))
    if not ordered or any(r["failure_count"] for r in ordered):
        raise ValueError("A selected main-figure cell is incomplete or unstable; see full statistics")
    x, y = [number(r[xfield]) for r in ordered], [r[metric] for r in ordered]
    ax.plot(x, y, style, color=color, marker="o" if len(x) < 10 else None, markersize=3, label=label)
    if band:
        ax.fill_between(x, [r["q25"] for r in ordered], [r["q75"] for r in ordered], color=color, alpha=.13)


def padding(root, plt, np):
    base, output = root / G1 / "data/report", root / G1 / "plots"
    ce = [r for r in read(base / "ce_all_prefixes.csv") if r["family"] == "E1"]
    actor = [r for r in read(base / "actor_endpoints.csv") if r["family"] == "E1"]
    assert len(ce) == 768 and len(actor) == 384
    ce_stats = summarize(ce, ("algorithm", "mode", "m", "N", "transitions"),
                         ("gap", "redundant_cost"), ("system", "trial"), 24)
    actor_stats = summarize(actor, ("algorithm", "mode", "m", "assigned_transitions"),
                            ("gap", "relative_gap", "redundant_cost"), ("system", "trial"), 24)
    write(output / "ce_all_prefix_statistics.csv", ce_stats)
    write(output / "appendix_actor_endpoint_statistics.csv", actor_stats)
    selected = [r for r in ce_stats if r["N"] == "8192"]
    assert len(selected) == 16 and all(r["transitions"] == "8324" for r in selected)
    write(output / "main_ce_input_padding_statistics.csv", selected)
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.5))
    for ax, metric, ylabel in zip(axes, ("gap", "redundant_cost"), ("Absolute optimality gap", "True redundant action cost D")):
        for mode in ("dense", "truncated"):
            rows = [dict(r, redundant_inputs=int(r["m"])-2) for r in selected if r["metric"] == metric and r["mode"] == mode]
            curve(ax, rows, "redundant_inputs", LABELS[mode], COLORS[mode])
        ax.set(title="CE: each method x input cell, failures 0/24", xlabel="Redundant inputs m-r (r=2)", ylabel=ylabel, yscale="log")
        ax.set_xticks((1, 4, 7, 10)); ax.grid(alpha=.2); ax.legend(frameon=False, fontsize=8)
    fig.suptitle("Input padding: median/IQR at 8,324 total transitions (132 burn + 8,192 regression)", fontsize=10)
    fig.tight_layout()
    artifacts = save(root, output, "main_ce_input_padding", fig, plt)
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.5))
    for ax, algorithm in zip(axes, ("NPG", "PI")):
        for mode in ("dense", "truncated"):
            rows = [dict(r, redundant_inputs=int(r["m"])-2) for r in actor_stats if r["algorithm"] == algorithm and r["mode"] == mode and r["metric"] == "gap"]
            curve(ax, rows, "redundant_inputs", LABELS[mode], COLORS[mode])
        ax.set(title=f"{algorithm}: failures 0/24 per method x input cell", xlabel="Redundant inputs m-r (r=2)", ylabel="Final absolute optimality gap", yscale="log")
        ax.set_xticks((1, 4, 7, 10)); ax.legend(frameon=False, fontsize=8); ax.grid(alpha=.2)
    fig.suptitle("Appendix: nominal-burn variants; median/IQR at 11,805,696 transitions per arm", fontsize=11)
    fig.tight_layout()
    artifacts += save(root, output, "appendix_input_padding_nominal_burn_actors", fig, plt)
    return {"status": "complete", "artifacts": artifacts, "CE_E1_outputs": len(ce), "actor_E1_trajectories": len(actor),
            "main_CE_repeat_denominator": 24, "main_CE_regression_N": 8192, "main_CE_total_transitions": 8324,
            "note": "CE only in main plot; nominal-burn NPG and v4 PI are explicitly appendix variants. All prefixes and complete repeat denominators retained."}


def matched_ce_tables(base, output):
    fixed = read(base / "matched_ce/fixed_budget_gaps.csv")
    rates = read(base / "matched_ce/success_by_budget.csv")
    requirements = read(base / "matched_ce/sample_complexity.csv")
    lookup = {(r["rank"], r["method"], number(r["relative_target"]), number(r["transitions"])): r for r in rates}
    for row in rates:
        assert int(row["instabilities"]) == 0 and int(row["numerical_failures"]) == 0
    augmented = []
    for row in fixed:
        item = dict(row)
        for mode in ("dense", "truncated"):
            rate = lookup[(row["rank"], mode, .1, number(row["transitions"]))]
            item[mode+"_count"] = int(rate["seeds"])
            item[mode+"_instabilities"] = int(rate["instabilities"])
            item[mode+"_numerical_failures"] = int(rate["numerical_failures"])
        augmented.append(item)
    write(output / "matched_ce_fixed_budget_statistics.csv", augmented)
    table = []
    for req in requirements:
        budget = number(req["N_hat_90"])
        if number(req["relative_target"]) != .1:
            continue
        rate = lookup.get((req["rank"], req["method"], .1, budget))
        table.append(dict(study="CE100_matched_initial_gap", rank=req["rank"], method=req["method"],
                          target_metric="absolute gap; requested initial gap=1", epsilon=req["absolute_target"],
                          first_tested_total_transitions=budget if math.isfinite(budget) else "",
                          previous_tested_total_transitions="", right_censored=not math.isfinite(budget),
                          success_requirement="at least 27/30 sampling seeds", successes_at_first_hit=rate["successes"] if rate else "",
                          denominator=30, physical_systems_per_rank=1,
                          instabilities_at_first_hit=rate["instabilities"] if rate else "",
                          numerical_failures_at_first_hit=rate["numerical_failures"] if rate else "",
                          burn_included=256, source="data/matched_ce/sample_complexity.csv + success_by_budget.csv"))
    return augmented, requirements, table


def highrank(base, output):
    endpoints = read(base / "precision_ce/endpoints.csv")
    adaptive = read(base / "adaptive_ce/endpoints.csv")
    stats = summarize(endpoints, ("rank", "method", "budget"), ("absolute_gap",), ("seed",), 2)
    empirical = summarize(adaptive, ("rank", "method", "budget"), ("absolute_gap",), ("seed",), 2)
    assert len(endpoints) == 2880 and len(adaptive) == 4320
    assert sum(not stable(r) for r in endpoints) == 0
    assert sum(not stable(r) for r in adaptive) == 8
    write(output / "high_rank_ce_all_budget_statistics.csv", stats)
    write(output / "appendix_empirical_adaptive_ce_all_budget_statistics.csv", empirical)
    reqs = read(base / "precision_ce/sample_to_accuracy.csv")
    rates = read(base / "precision_ce/success_by_budget.csv")
    lookup = {(r["rank"], r["method"], number(r["budget"])): r for r in rates}
    table = []
    for req in reqs:
        budget = number(req["first_tested_budget"])
        rate = lookup.get((req["rank"], req["method"], budget))
        selected = [r for r in stats if r["rank"] == req["rank"] and r["method"] == req["method"] and number(r["budget"]) == budget]
        table.append(dict(study="CE100_high_rank_precision_zoom", rank=req["rank"], method="dense" if req["method"] == "raw" else req["method"],
                          target_metric="absolute gap", epsilon=req["epsilon"], first_tested_total_transitions=budget if math.isfinite(budget) else "",
                          previous_tested_total_transitions=req["previous_tested_budget"], right_censored=yes(req["right_censored"]),
                          success_requirement="both 2 systems", successes_at_first_hit=rate["successes"] if rate else "",
                          denominator=2, physical_systems_per_rank=2,
                          instabilities_at_first_hit=selected[0]["failure_count"] if selected else "",
                          numerical_failures_at_first_hit=0 if selected else "",
                          burn_included=512, source="data/precision_ce/sample_to_accuracy.csv + endpoints.csv"))
    return stats, empirical, table


def accuracy_bars(ax, rows, study, np):
    records = [r for r in rows if r["study"] == study]
    ranks = sorted({int(r["rank"]) for r in records})
    for index, mode in enumerate(("dense", "truncated")):
        values = [next(r for r in records if int(r["rank"]) == rank and r["method"] == mode) for rank in ranks]
        x = np.arange(len(ranks)) + (index-.5)*.34
        heights = [number(r["first_tested_total_transitions"]) for r in values]
        ax.bar(x, heights, width=.32, color=COLORS[mode], label=LABELS[mode])
    for rank_index, rank in enumerate(ranks):
        pair = [next(r for r in records if int(r["rank"]) == rank and r["method"] == mode) for mode in ("dense", "truncated")]
        if number(pair[0]["first_tested_total_transitions"]) == number(pair[1]["first_tested_total_transitions"]) and pair[0]["successes_at_first_hit"] == pair[1]["successes_at_first_hit"]:
            row = pair[0]; height = number(row["first_tested_total_transitions"])
            ax.text(rank_index, height*1.018, f"{int(height):,} each\n{row['successes_at_first_hit']}/{row['denominator']} each", ha="center", va="bottom", fontsize=6.3)
        else:
            for mode_index, row in enumerate(pair):
                height = number(row["first_tested_total_transitions"])
                ax.text(rank_index+(mode_index-.5)*.34, height*1.018, f"{int(height):,}\n{row['successes_at_first_hit']}/{row['denominator']}", ha="center", va="bottom", fontsize=6.3)
    ax.set_xticks(np.arange(len(ranks)), ranks)
    ax.set(xlabel="True rank r", ylabel="First tested total transitions (burn included)")
    ax.set_ylim(0, max(number(r["first_tested_total_transitions"]) for r in records)*1.26)
    ax.grid(axis="y", alpha=.2); ax.legend(frameon=False, fontsize=7)


def ce100(root, plt, np):
    base, output = root / G4 / "data", root / G4 / "plots"
    fixed, requirements, table = matched_ce_tables(base, output)
    high_stats, empirical_stats, high_table = highrank(base, output)
    table += high_table
    write(output / "table_1_ce_accuracy.csv", table)
    write(output / "matched_ce_all_accuracy_targets.csv", requirements)
    artifacts = []
    palette = ["#426ca6", "#d97535", "#398859", "#8757a6", "#765443"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    ranks = sorted({int(r["rank"]) for r in fixed})
    for ax, mode in zip(axes, ("dense", "truncated")):
        for rank, color in zip(ranks, palette):
            rows = sorted((r for r in fixed if int(r["rank"]) == rank), key=lambda r: number(r["transitions"]))
            x = [number(r["transitions"]) for r in rows]
            ax.plot(x, [number(r[mode+"_gap_median"]) for r in rows], color=color, label=f"r={rank}")
            ax.fill_between(x, [number(r[mode+"_gap_q25"]) for r in rows], [number(r[mode+"_gap_q75"]) for r in rows], color=color, alpha=.12)
        ax.set(title=f"{LABELS[mode]} CE: failures 0/30 per rank x budget", xlabel="Total transitions (includes 256 burn)", ylabel="Absolute optimality gap", xscale="log", yscale="log")
        ax.grid(alpha=.2); ax.legend(frameon=False, fontsize=7, ncol=2)
    fig.suptitle("100d matched initial gap: median/IQR over 30 sampling seeds, one system per rank", fontsize=11)
    fig.tight_layout(); artifacts += save(root, output, "main_matched_ce_learning", fig, plt)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
    for ax, study, title, denominator in zip(axes, ("CE100_matched_initial_gap", "CE100_high_rank_precision_zoom"),
                                ("Matched initial gap: criterion >=27/30 seeds", "High rank: criterion 2/2 systems"), (30, 2)):
        accuracy_bars(ax, table, study, np)
        ax.set_title(title+f"\nInstabilities 0/{denominator} at every first-hit cell", fontsize=9)
    fig.suptitle("CE accuracy table: absolute gap <=0.1; labels show actual successes/denominator", fontsize=11)
    fig.tight_layout(); artifacts += save(root, output, "main_ce_accuracy_budgets", fig, plt)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    ranks = sorted({int(r["rank"]) for r in high_stats})
    for ax, mode in zip(axes, ("raw", "truncated")):
        for rank, color in zip(ranks, palette):
            curve(ax, [r for r in high_stats if int(r["rank"]) == rank and r["method"] == mode], "budget", f"r={rank}", color, metric="worst", band=False)
        ax.axhline(.1, color="0.45", linestyle=":", linewidth=.8)
        ax.set(title=f"{LABELS[mode]} CE: failures 0/2 per rank x budget", xlabel="Total transitions (includes 512 burn)", ylabel="Worst absolute gap across 2 systems", xscale="log", yscale="log")
        ax.grid(alpha=.2); ax.legend(frameon=False, fontsize=7, ncol=2)
    fig.suptitle("High-rank CE precision zoom: all 180 saved prefixes, two systems per rank", fontsize=11)
    fig.tight_layout(); artifacts += save(root, output, "main_high_rank_ce_learning", fig, plt)
    empirical_requirements = read(base / "adaptive_ce/sample_to_accuracy.csv")
    write(output / "appendix_empirical_adaptive_ce_accuracy.csv", empirical_requirements)
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ranks = sorted({int(r["rank"]) for r in empirical_requirements})
    for index, mode in enumerate(("raw", "truncated", "adaptive")):
        vals = [next(r for r in empirical_requirements if int(r["rank"]) == rank and r["method"] == mode) for rank in ranks]
        ax.bar(np.arange(len(ranks))+(index-1)*.25, [number(r["first_tested_budget"]) for r in vals], width=.23, color=COLORS[mode], label=LABELS[mode])
    ax.set_xticks(np.arange(len(ranks)), ranks)
    ax.set(title="First-hit cells: failures 0/2; full adaptive data retain 8 failures at minimum budget", xlabel="True rank r", ylabel="Total transitions to 2/2 systems at gap <=0.1")
    ax.grid(axis="y", alpha=.2); ax.legend(frameon=False, fontsize=8)
    fig.suptitle("Appendix: empirical half-split adaptive CE; not a certified confidence radius", fontsize=10)
    fig.tight_layout(); artifacts += save(root, output, "appendix_empirical_adaptive_ce_budgets", fig, plt)

    npg = read(base / "matched_npg/npg-all-checkpoints.csv")
    assert len(npg) == 13500
    npg_stats = summarize(npg, ("rank", "method", "stage", "transitions"), ("gap", "relative_gap"), ("seed",), 30)
    write(output / "appendix_matched_npg_all_stage_statistics.csv", npg_stats)
    npg_accuracy = [r for r in read(base / "matched_npg/sample_complexity.csv") if r["route"] == "npg"]
    write(output / "appendix_matched_npg_observed_accuracy.csv", npg_accuracy)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    ranks = sorted({int(r["rank"]) for r in npg_stats})
    for ax, mode in zip(axes, ("dense", "truncated")):
        for rank, color in zip(ranks, palette):
            rows = [r for r in npg_stats if int(r["rank"]) == rank and r["method"] == mode and r["metric"] == "relative_gap" and number(r["transitions"]) > 0]
            curve(ax, rows, "transitions", f"r={rank}", color)
        ax.set(title=f"{LABELS[mode]}: failures 0/30 per rank x stage", xlabel="Total transitions (burn/baseline included)", ylabel="Relative optimality gap", xscale="log", yscale="log")
        ax.grid(alpha=.2); ax.legend(frameon=False, fontsize=7, ncol=2)
    fig.suptitle("Appendix: nominal-burn practical NPG; relative comparison, no theorem certification", fontsize=10)
    fig.tight_layout(); artifacts += save(root, output, "appendix_matched_npg_relative_comparison", fig, plt)
    return {"status": "complete", "artifacts": artifacts, "CE_accuracy_table": f"{G4}/plots/table_1_ce_accuracy.csv",
            "matched_CE_sampling_seeds_per_rank": 30, "high_rank_CE_systems_per_rank": 2,
            "high_rank_CE_saved_prefixes": 180, "precision_outputs": 2880,
            "empirical_adaptive_outputs": 4320, "empirical_adaptive_failed_outputs_retained": 8,
            "matched_NPG_saved_stages": len(npg), "note": "Main figures/table use CE. NPG and empirical adaptive CE are appendix-only; historical observed accuracy records are retained without a theorem claim."}


def run(root, plt, np):
    root = Path(root).resolve()
    verified_sources(root)
    results = {}
    for name, handler in ((G1, padding), (G4, ce100)):
        try:
            results[name] = handler(root, plt, np)
        except Exception as error:
            results[name] = {"status": "error", "error": f"{type(error).__name__}: {error}"}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    root = parser.parse_args().root.resolve()
    configure_paths(root)
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.fonttype": "none", "pdf.fonttype": 42})
    result = run(root, plt, np)
    (root / G4 / "plots/restored_plot_status.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(any(v["status"] == "error" for v in result.values()))


if __name__ == "__main__":
    raise SystemExit(main())
