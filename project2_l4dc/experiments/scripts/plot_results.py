#!/usr/bin/env python3
"""Plot the verified, saved experiment tables; never run learning or control solvers.

Run with an existing environment containing numpy and matplotlib:
    python scripts/plot_results.py --root /path/to/experiments

All statistics use the complete repeat denominator. Failed outputs have +inf
loss. A main panel is drawn only for complete, entirely stable cells; the CSV
tables still retain every cell, including failed and unplotted cells. Repeated
budgets from one trajectory are correlated observations, not new repeats.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path


def configure_paths(root: Path) -> None:
    """Configure caches before importing plotting libraries (no C: defaults)."""
    for key, name in (("MPLCONFIGDIR", "matplotlib"), ("XDG_CACHE_HOME", "cache"),
                      ("TMP", "tmp"), ("TEMP", "tmp"), ("TMPDIR", "tmp")):
        target = root / ".runtime" / name
        target.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(target)


def numeric(value, default=math.nan):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_stable(row):
    return str(row.get("stable", "")).strip().lower() in {"true", "1"}


def read_rows(path: Path):
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows and "stable" not in rows[0]:
        raise ValueError(f"Missing explicit stable flag: {path}")
    return rows


def quantile_extended(values, probability):
    """NumPy's usual linear quantile, extended to +inf without inf-inf NaNs."""
    ordered = sorted(values)
    if not ordered:
        return math.nan
    index = probability * (len(ordered) - 1)
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper or ordered[lower] == ordered[upper]:
        return ordered[lower]
    fraction = index - lower
    if math.isinf(ordered[upper]) and fraction > 0:
        return math.inf
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def metric_stats(rows, metric):
    values = []
    for row in rows:
        value = numeric(row.get(metric))
        if not is_stable(row):
            value = math.inf
        elif not math.isfinite(value):
            raise ValueError(f"Stable output lacks finite {metric}: {row}")
        values.append(value)
    return {
        "count": len(rows),
        "failure_count": sum(not is_stable(row) for row in rows),
        "stable_count": sum(is_stable(row) for row in rows),
        "failure_rate": sum(not is_stable(row) for row in rows) / len(rows),
        "median": quantile_extended(values, .5),
        "q25": quantile_extended(values, .25),
        "q75": quantile_extended(values, .75),
    }


GROUP_FIELDS = ("algorithm", "A_family", "spectrum", "n", "r", "mode", "N",
                "transitions", "stage")


def summarize(rows, metrics):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key, "") for key in GROUP_FIELDS)].append(row)
    records = []
    for key, observations in groups.items():
        repeat_ids = [(row.get("system", ""), row.get("trial", ""))
                      for row in observations]
        if len(repeat_ids) != len(set(repeat_ids)):
            raise ValueError(f"Duplicate system/trial within output cell: {key}")
        for metric in metrics:
            record = dict(zip(GROUP_FIELDS, key))
            record.update(metric=metric, **metric_stats(observations, metric))
            record["median_definition"] = "linear quantile; failed outputs = +inf"
            records.append(record)
    return records


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def family_label(name):
    return {"scalar": "Scalar A", "dense": "Coupled A"}.get(name, name)


def mode_rank(row):
    mode = row["mode"]
    if mode == "adaptive":
        return None
    if mode == "dense":
        return int(numeric(row["n"]))
    if mode.startswith("k") and mode[1:].isdigit():
        return int(mode[1:])
    if mode == "truncated":
        return int(numeric(row.get("k", row.get("r"))))
    return None


def eligible(records, expected=24):
    return bool(records) and all(row["count"] == expected and
                                 row["failure_count"] == 0 for row in records)


def failure_note(records):
    failures = sum(row["failure_count"] for row in records)
    denominator = sum(row["count"] for row in records)
    return f"Failures: {failures}/{denominator} outputs; 24 repeats/cell"


def budget_label(value):
    if value >= 1_000_000:
        return f"M={value / 1_000_000:.3g}M"
    if value >= 1000:
        return f"M={value / 1000:.3g}k"
    return f"M={value:g}"


def save_figure(fig, directory, stem, plt):
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for extension in ("png", "svg", "pdf"):
        path = directory / f"{stem}.{extension}"
        fig.savefig(path, dpi=200, bbox_inches="tight")
        paths.append(str(path.relative_to(directory.parent.parent)))
    plt.close(fig)
    return paths


def bar_comparison(ax, records, metrics, colors, title, np):
    """Each visible metric has both dense and truncated, with all repeats."""
    modes = ("dense", "truncated")
    plotted = []
    for metric_index, (metric, label) in enumerate(metrics):
        for mode_index, mode in enumerate(modes):
            matches = [row for row in records if row["mode"] == mode and
                       row["metric"] == metric]
            if len(matches) != 1:
                ax.text(.5, .5, "Complete paired cell unavailable", ha="center",
                        va="center", transform=ax.transAxes)
                ax.set_title(title)
                return False
            plotted.extend(matches)
    if not eligible(plotted):
        ax.text(.5, .5, "Cell excluded from main figure:\nnot all 24 repeats stable",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title)
        return False
    positions = np.arange(len(metrics))
    width = .33
    for mode_index, mode in enumerate(modes):
        subset = [next(row for row in plotted if row["mode"] == mode and
                       row["metric"] == metric) for metric, _ in metrics]
        medians = np.array([row["median"] for row in subset])
        low = medians - np.array([row["q25"] for row in subset])
        high = np.array([row["q75"] for row in subset]) - medians
        ax.bar(positions + (mode_index - .5) * width, medians, width,
               yerr=np.array([low, high]), capsize=3, color=colors[mode_index],
               label="Dense" if mode == "dense" else "Truncated")
    ax.set_xticks(positions, [label for _, label in metrics])
    ax.set_title(title)
    ax.grid(axis="y", alpha=.2)
    ax.text(.02, .98, "Each bar: failures 0/24\nMedian and IQR, all repeats",
            va="top", transform=ax.transAxes, fontsize=8,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": .8})
    ax.margins(y=.30)
    return True


def plot_mechanism(root, plt, np):
    folder = root / "02_same_data_decomposition"
    ce = read_rows(folder / "data" / "ce_same_data.csv")
    npg = read_rows(folder / "data" / "npg_same_blocks.csv")
    if not ce or not npg:
        return {"status": "missing_verified_data", "reason": "CE/NPG same-data CSV missing"}
    ce = [row for row in ce if row["mode"] in {"dense", "truncated"}]
    npg = [row for row in npg if row["mode"] in {"dense", "truncated"} and
           row.get("source_mode") == "dense" and numeric(row.get("stage")) == 1]
    ce_stats = summarize(ce, ("gap", "redundant_cost"))
    npg_stats = summarize(npg, ("gap", "redundant_cost", "Z_error_fro2"))
    output = folder / "plots"
    write_csv(output / "ce_all_budgets_statistics.csv", ce_stats)
    write_csv(output / "npg_same_blocks_statistics.csv", npg_stats)
    families = sorted({row["A_family"] for row in ce}, key=lambda x: x != "scalar")
    fig, axes = plt.subplots(len(families), 3, figsize=(12.2, 3.7 * len(families)),
                             squeeze=False)
    selections = []
    complete = True
    for index, family in enumerate(families):
        ce_cell = [row for row in ce_stats if row["A_family"] == family and
                   numeric(row["N"]) == 3072]
        npg_cell = [row for row in npg_stats if row["A_family"] == family]
        selections.extend(ce_cell + npg_cell)
        complete &= bar_comparison(axes[index, 0], ce_cell,
                                  (("gap", "Total gap"), ("redundant_cost", "True redundant D")),
                                  ("#5476a6", "#dd8757"),
                                  f"{family_label(family)}: CE, N=3072", np)
        complete &= bar_comparison(axes[index, 1], npg_cell,
                                  (("redundant_cost", "True redundant D"),),
                                  ("#5476a6", "#dd8757"),
                                  f"{family_label(family)}: NPG first update", np)
        complete &= bar_comparison(axes[index, 2], npg_cell,
                                  (("Z_error_fro2", "Critic squared Frobenius error"),),
                                  ("#5476a6", "#dd8757"),
                                  f"{family_label(family)}: shared Stein estimate", np)
    axes[0, 0].legend(loc="upper right", frameon=False, fontsize=9)
    fig.suptitle("Same-data mechanism, n=24, r=2: complete paired repeats", fontsize=13)
    fig.tight_layout()
    artifacts = save_figure(fig, output, "same_data_mechanism", plt)
    write_csv(output / "main_figure_statistics.csv", selections)
    return {"status": "complete" if complete else "partial_cells_unavailable",
            "artifacts": artifacts, "CE_regression_samples": 3072,
            "note": "NPG source_mode=dense, stage=1 only; no duplicated source arms"}


def choose_four(budgets):
    budgets = sorted(set(budgets))
    if len(budgets) <= 4:
        return budgets
    indices = [round((len(budgets) - 1) * fraction) for fraction in (0, 1/3, 2/3, 1)]
    return [budgets[index] for index in indices]


def plot_fullrank(root, plt, np):
    folder = root / "03_fullrank_rank_scan"
    observations = read_rows(folder / "data" / "fullrank_all_outputs.csv")
    if not observations:
        return {"status": "missing_verified_data", "reason": "Full-rank output CSV missing"}
    # Redundant-direction decomposition is not recorded for these full-rank
    # systems. Blank source fields must not be converted to invented zeros.
    stats = summarize(observations, ("gap", "relative_gap"))
    output = folder / "plots"
    write_csv(output / "all_budgets_statistics.csv", stats)
    gap_stats = [row for row in stats if row["metric"] == "gap"]
    families = sorted({row["A_family"] for row in observations}, key=lambda x: x != "scalar")
    artifacts, selections = [], []
    curve_info = []
    for family in families:
        fig, axes = plt.subplots(2, 2, figsize=(10.8, 7.5), squeeze=False)
        for i, algorithm in enumerate(("CE", "NPG")):
            for j, spectrum in enumerate(("gapped", "smooth")):
                ax = axes[i, j]
                cell = [row for row in gap_stats if row["A_family"] == family and
                        row["algorithm"] == algorithm and row["spectrum"] == spectrum and
                        row["mode"] != "adaptive" and numeric(row["transitions"]) > 0]
                by_budget = defaultdict(list)
                for row in cell:
                    by_budget[numeric(row["transitions"])].append(row)
                # Use only a common budget whose *entire* fixed-k scan is stable.
                # All other cells remain in all_budgets_statistics.csv.
                all_ranks = {mode_rank(row) for row in cell}
                good_budgets = [budget for budget, records in by_budget.items()
                                if eligible(records) and
                                {mode_rank(row) for row in records} == all_ranks]
                if algorithm == "NPG":
                    stages = {int(numeric(row["stage"], -1)): numeric(row["transitions"])
                              for row in cell}
                    requested = [stages[s] for s in (12, 24, 36, 48)
                                 if s in stages and stages[s] in good_budgets]
                    chosen = requested if requested else choose_four(good_budgets)
                else:
                    chosen = choose_four(good_budgets)
                displayed = []
                for budget in chosen:
                    records = sorted(by_budget[budget], key=mode_rank)
                    ranks = [mode_rank(row) for row in records]
                    medians = np.array([row["median"] for row in records])
                    line, = ax.plot(ranks, medians, marker="o", markersize=3,
                                    label=budget_label(budget))
                    ax.fill_between(ranks, [row["q25"] for row in records],
                                    [row["q75"] for row in records],
                                    color=line.get_color(), alpha=.10)
                    displayed.extend(records)
                    curve_info.append({"algorithm": algorithm, "A_family": family,
                                       "spectrum": spectrum, "transitions": budget,
                                       "failure_count": 0, "output_count": sum(r["count"] for r in records),
                                       "ranks": ";".join(map(str, ranks))})
                if displayed:
                    selections.extend(displayed)
                    ax.set_yscale("log")
                    ax.legend(frameon=False, fontsize=8)
                    note = "Each k x budget cell: failures 0/24"
                else:
                    note = "No complete stable cell displayed"
                    ax.text(.5, .5, "No complete stable rank-scan cell", ha="center",
                            transform=ax.transAxes)
                ax.set(title=f"{algorithm}, {spectrum} spectrum, {family_label(family)}\n{note}",
                       xlabel="Retained rank k (dense = 16)", ylabel="Absolute optimality gap")
                ax.grid(alpha=.2)
        fig.suptitle("Full-rank systems: finite-budget rank tradeoff (median and IQR)", fontsize=12)
        fig.tight_layout()
        artifacts.extend(save_figure(fig, output, f"fullrank_rank_scan_{family}", plt))
    write_csv(output / "main_rank_scan_statistics.csv", selections)
    write_csv(output / "main_rank_scan_budgets.csv", curve_info)
    artifacts.extend(plot_flat(gap_stats, output, plt, np))
    artifacts.extend(plot_adaptive_ce(gap_stats, output, plt))
    return {"status": "complete", "artifacts": artifacts,
            "note": "NPG has fixed k only; adaptive CE is an explicitly empirical supplement. "
                    "Flat NPG uses only the observed k2/k8/dense arms, not a nine-rank scan."}


def plot_flat(gap_stats, output, plt, np):
    artifacts, selected = [], []
    families = sorted({row["A_family"] for row in gap_stats if row["spectrum"] == "flat"})
    for family in families:
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), squeeze=False)
        for index, algorithm in enumerate(("CE", "NPG")):
            ax = axes[0, index]
            cell = [row for row in gap_stats if row["spectrum"] == "flat" and
                    row["A_family"] == family and row["algorithm"] == algorithm and
                    row["mode"] in {"k2", "k8", "dense"}]
            maximum = max((numeric(row["transitions"]) for row in cell), default=0)
            records = sorted([row for row in cell if numeric(row["transitions"]) == maximum],
                             key=mode_rank)
            if len(records) == 3 and eligible(records):
                selected.extend(records)
                median = np.array([row["median"] for row in records])
                error = np.array([median - np.array([row["q25"] for row in records]),
                                  np.array([row["q75"] for row in records]) - median])
                ax.bar(range(3), median, yerr=error, capsize=3,
                       color=("#dd8757", "#71a190", "#5476a6"))
                ax.set_xticks(range(3), ("k=2", "k=8", "Dense (k=16)"))
                ax.set_yscale("log")
                note = "Each method: failures 0/24; median and IQR"
            else:
                note = "No complete stable cell displayed"
                ax.text(.5, .5, "Complete stable negative-control cell unavailable",
                        ha="center", transform=ax.transAxes, fontsize=8)
            ax.set(title=f"{algorithm}: flat spectrum, {budget_label(maximum)}\n{note}",
                   ylabel="Absolute optimality gap")
            ax.grid(axis="y", alpha=.2)
        fig.suptitle(f"Flat-spectrum negative control: {family_label(family)}", fontsize=12)
        fig.tight_layout()
        artifacts.extend(save_figure(fig, output, f"flat_negative_control_{family}", plt))
    write_csv(output / "flat_negative_control_statistics.csv", selected)
    return artifacts


def plot_adaptive_ce(gap_stats, output, plt):
    artifacts, selected = [], []
    families = sorted({row["A_family"] for row in gap_stats if row["algorithm"] == "CE"})
    for family in families:
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), squeeze=False)
        for index, spectrum in enumerate(("gapped", "smooth")):
            ax = axes[0, index]
            cell = [row for row in gap_stats if row["algorithm"] == "CE" and
                    row["A_family"] == family and row["spectrum"] == spectrum]
            by_budget = defaultdict(list)
            for row in cell:
                by_budget[numeric(row["transitions"])].append(row)
            display = []
            lines = {"Dense": [], "Empirical adaptive CE": [], "Best fixed-k median (post hoc)": []}
            for budget, records in sorted(by_budget.items()):
                if not eligible(records):
                    continue
                dense = [row for row in records if row["mode"] == "dense"]
                adaptive = [row for row in records if row["mode"] == "adaptive"]
                fixed = [row for row in records if row["mode"] != "adaptive"]
                if len(dense) != 1 or len(adaptive) != 1 or not fixed:
                    continue
                best = min(fixed, key=lambda row: row["median"])
                for label, record in (("Dense", dense[0]), ("Empirical adaptive CE", adaptive[0]),
                                      ("Best fixed-k median (post hoc)", best)):
                    lines[label].append((budget, record["median"]))
                    selected.append(dict(record, displayed_series=label))
                display.extend(records)
            for label, pairs in lines.items():
                if pairs:
                    ax.plot([pair[0] for pair in pairs], [pair[1] for pair in pairs],
                            marker="o", markersize=3, label=label)
            if display:
                ax.set_xscale("log")
                ax.set_yscale("log")
                ax.legend(frameon=False, fontsize=7)
                note = "Each method x budget cell: failures 0/24"
            else:
                note = "No complete stable cell displayed"
                ax.text(.5, .5, "Complete stable CE cells unavailable", ha="center",
                        transform=ax.transAxes)
            ax.set(title=f"{family_label(family)}, {spectrum} spectrum\n{note}",
                   xlabel="Cumulative transitions (burn-in included)", ylabel="Absolute optimality gap")
            ax.grid(alpha=.2)
        fig.suptitle("Supplement: empirical adaptive CE, not a certified confidence radius", fontsize=12)
        fig.tight_layout()
        artifacts.extend(save_figure(fig, output, f"supplement_adaptive_ce_{family}", plt))
    write_csv(output / "supplement_adaptive_ce_statistics.csv", selected)
    return artifacts


def appendix_tables(root):
    data = root / "appendix" / "data"
    records = read_rows(data / "exact_rank_npg_endpoints.csv")
    if records:
        write_csv(root / "appendix" / "plots" / "exact_rank_npg_endpoint_statistics.csv",
                  summarize(records, ("gap", "relative_gap")))
    tail = read_rows(data / "tail_strength_all_outputs.csv")
    if tail:
        write_csv(root / "appendix" / "plots" / "tail_strength_statistics.csv",
                  summarize(tail, ("gap", "relative_gap")))
    return {"status": "complete" if records else "missing_verified_data",
            "exact_endpoint_records": len(records), "tail_output_records": len(tail),
            "note": "All failure-inclusive cells retained; these are not main-figure survivor statistics."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"Experiment package does not exist: {root}")
    configure_paths(root)
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "pdf.fonttype": 42})
    status = {
        "operation": "saved-data postprocessing only; no learning/control solves",
        "statistics": "Full repeat denominators; failures=+inf; linear median/IQR where used; "
                      "main plots use complete stable cells with the actual 24/30/2 denominator. "
                      "High-rank CE uses two systems, not 30 repeats.",
        "groups": {},
    }
    for name, handler in (("02_same_data_decomposition", plot_mechanism),
                          ("03_fullrank_rank_scan", plot_fullrank)):
        try:
            status["groups"][name] = handler(root, plt, np)
        except Exception as error:
            status["groups"][name] = {"status": "error", "error": f"{type(error).__name__}: {error}"}
    try:
        from plot_restored_results import run as plot_restored
        status["groups"].update(plot_restored(root, plt, np))
    except Exception as error:
        for name in ("01_input_padding", "04_ce100_matched_gap_and_high_rank"):
            status["groups"][name] = {"status": "error", "error": f"{type(error).__name__}: {error}"}
    try:
        status["appendix"] = appendix_tables(root)
    except Exception as error:
        status["appendix"] = {"status": "error", "error": f"{type(error).__name__}: {error}"}
    status["runtime_directories"] = {key: os.environ[key] for key in
                                     ("MPLCONFIGDIR", "XDG_CACHE_HOME", "TMP", "TEMP", "TMPDIR")}
    (root / "plot_status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return int(any(result.get("status") == "error" for result in
                   list(status["groups"].values()) + [status["appendix"]]))


if __name__ == "__main__":
    raise SystemExit(main())
