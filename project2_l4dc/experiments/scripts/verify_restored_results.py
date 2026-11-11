"""Independent checks on recovered CSVs; no learning or policy evaluation."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def yes(value):
    return str(value).lower() == "true"


def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-11, abs_tol=1e-11), (a, b)


def grouped(data, keys):
    groups = defaultdict(list)
    for row in data:
        groups[tuple(row[k] for k in keys)].append(row)
    return groups


def check_high_rank(folder, adaptive=False):
    data = rows(folder / "endpoints.csv")
    assert len(data) == (4320 if adaptive else 2880)
    failed = [r for r in data if not yes(r["stable"])]
    assert len(failed) == (8 if adaptive else 0)
    if adaptive:
        assert all(r["method"] == "adaptive" and int(r["budget"]) == 1024 for r in failed)
    for row in data:
        assert yes(row["success"]) == (yes(row["stable"]) and float(row["absolute_gap"] or "inf") <= .1)
    cells = grouped(data, ("rank", "method", "budget"))
    assert all(len(cell) == 2 and len({r["seed"] for r in cell}) == 2 for cell in cells.values())
    budget_maps = defaultdict(dict)
    for (rank, method, budget), cell in cells.items():
        budget_maps[(int(rank), method)][int(budget)] = all(yes(r["success"]) for r in cell)
    results = []
    for summary in rows(folder / "sample_to_accuracy.csv"):
        rank, method = int(summary["rank"]), summary["method"]
        budgets = budget_maps[(rank, method)]
        success = [b for b, good in budgets.items() if good]
        first = min(success) if success else None
        assert not yes(summary["right_censored"])
        assert first == int(summary["first_tested_budget"])
        sustained = min(b for b in success if all(good for later, good in budgets.items() if later >= b))
        assert sustained == int(summary["sustained_tested_budget"])
        results.append({"rank": rank, "method": method, "first_transitions": first,
                        "first_successes": 2, "denominator": 2})
    return {"outputs": len(data), "unstable_outputs": len(failed), "system_count_per_cell": 2,
            "budgets_already_include_burn": 512, "first_attainment": results}


def check_plot_statistics(path, source, fields):
    cells = grouped(source, fields)
    table = rows(path)
    for stat in table:
        cell = cells[tuple(stat[k] for k in fields)]
        assert int(stat["count"]) == len(cell)
        failed = sum(not yes(r["stable"]) for r in cell)
        assert int(stat["failure_count"]) == failed
        values = [float(r[stat["metric"]]) if yes(r["stable"]) else math.inf for r in cell]
        close(stat["median"], statistics.median(values))
        if all(math.isfinite(v) for v in values):
            qs = statistics.quantiles(values, n=4, method="inclusive")
            close(stat["q25"], qs[0]); close(stat["q75"], qs[2])
        if "worst" in stat:
            close(stat["worst"], max(values))
    return len(table)


def verify(root, with_plots=True):
    retrieval = json.loads((root / "provenance/retrieval_manifest.json").read_text(encoding="utf-8"))
    for entry in retrieval["files"]:
        path = root / entry["target"]
        assert path.stat().st_size == entry["size"], entry["target"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], entry["target"]
    padding = root / "01_input_padding/data/report"
    actors = [r for r in rows(padding / "actor_endpoints.csv") if r["family"] == "E1"]
    ce = [r for r in rows(padding / "ce_all_prefixes.csv") if r["family"] == "E1"]
    assert len(actors) == 384 and len(ce) == 768
    assert all(yes(r["stable"]) and yes(r["complete"]) for r in actors + ce)
    assert Counter(r["algorithm"] for r in actors) == {"NPG": 192, "PI": 192}
    assert all(int(r["actual_transitions"]) == int(r["assigned_transitions"]) == 11805696 for r in actors)
    cells = grouped(actors, ("algorithm", "mode", "m"))
    assert len(cells) == 16 and all(len(cell) == 24 for cell in cells.values())
    for summary in rows(padding / "e1_summary.csv"):
        cell = cells[(summary["algorithm"], summary["mode"], summary["m"])]
        values = [float(r["gap"]) for r in cell]
        close(summary["median"], statistics.median(values))
        qs = statistics.quantiles(values, n=4, method="inclusive")
        close(summary["q25"], qs[0]); close(summary["q75"], qs[2])
        assert int(summary["n"]) == 24 and int(summary["failures"]) == 0
    ce_main = [r for r in ce if int(r["N"]) == 8192]
    assert len(ce_main) == 192 and all(int(r["transitions"]) == 8324 for r in ce_main)
    ce_cells = grouped(ce_main, ("mode", "m"))
    for summary in rows(padding / "e1_ce_redundant_summary.csv"):
        cell = ce_cells[(summary["mode"], summary["m"])]
        close(summary["median"], statistics.median(float(r["redundant_cost"]) for r in cell))

    base = root / "04_ce100_matched_gap_and_high_rank/data"
    ce_rates = rows(base / "matched_ce/success_by_budget.csv")
    ce_first = []
    for summary in rows(base / "matched_ce/sample_complexity.csv"):
        rank, method, target = int(summary["rank"]), summary["method"], float(summary["relative_target"])
        rates = [r for r in ce_rates if int(r["rank"]) == rank and r["method"] == method and float(r["relative_target"]) == target]
        assert rates and all(int(r["seeds"]) == 30 for r in rates)
        assert all(int(r["instabilities"]) == 0 and int(r["numerical_failures"]) == 0 for r in rates)
        hits = [r for r in rates if int(r["successes"]) >= 27]
        first = min(hits, key=lambda r: int(r["transitions"])) if hits else None
        assert first is not None and summary["status"] == "reached"
        assert int(first["transitions"]) == int(float(summary["N_hat_90"]))
        ce_first.append({"rank": rank, "method": method, "relative_target": target,
                         "transitions": int(first["transitions"]), "successes": int(first["successes"]), "denominator": 30})
    selected = {(r["rank"], r["method"]): r for r in ce_first if r["relative_target"] == .1}
    assert [selected[(r, "dense")]["transitions"] for r in (2, 8, 32, 64, 100)] == [14592, 16640, 24832, 20736, 14592]
    assert [selected[(r, "truncated")]["transitions"] for r in (2, 8, 32, 64, 100)] == [3328, 8448, 16640, 20736, 14592]
    assert [selected[(r, "truncated")]["successes"] for r in (2, 8, 32, 64, 100)] == [29, 30, 27, 30, 30]

    npg = rows(base / "matched_npg/npg-all-checkpoints.csv")
    assert len(npg) == 13500 and all(yes(r["stable"]) and yes(r["whole_path_stable"]) and yes(r["observed"]) for r in npg)
    paths = grouped(npg, ("rank", "method", "seed"))
    assert len(paths) == 300 and all(len(path) == 45 for path in paths.values())
    endpoints = [max(path, key=lambda r: int(r["stage"])) for path in paths.values()]
    assert Counter(r["method"] for r in endpoints) == {"dense": 150, "truncated": 150}
    gaps = {m: statistics.median(float(r["gap"]) for r in endpoints if r["rank"] == "2" and r["method"] == m) for m in ("dense", "truncated")}
    close(gaps["dense"], .13215756970074466); close(gaps["truncated"], .017391795159277024)
    npg_first = []
    for method in ("dense", "truncated"):
        cell = [r for r in npg if r["rank"] == "2" and r["method"] == method]
        by_budget = grouped(cell, ("transitions",))
        for target in (.1, .05):
            hits = [(int(budget[0]), sum(float(r["relative_gap"]) <= target for r in records))
                    for budget, records in by_budget.items() if sum(float(r["relative_gap"]) <= target for r in records) >= 27]
            first = min(hits) if hits else None
            summary = next(r for r in rows(base / "matched_npg/sample_complexity.csv") if r["route"] == "npg" and r["rank"] == "2" and r["method"] == method and float(r["epsilon"]) == target)
            assert (first is None) == (summary["N_hat_epsilon_90"] == "")
            if first:
                assert first[0] == int(float(summary["N_hat_epsilon_90"]))
                assert first == (27794544 if target == .1 else 94905228, 30)
            npg_first.append({"rank": 2, "method": method, "target": target,
                              "first_transitions": first[0] if first else None,
                              "successes": first[1] if first else None,
                              "denominator": 30, "max_tested_transitions": max(int(b[0]) for b in by_budget)})
    result = {
        "archived_files_verified": len(retrieval["files"]),
        "archived_bytes_verified": sum(r["size"] for r in retrieval["files"]),
        "input_padding": {"actor_endpoints": len(actors), "NPG": 192, "PI": 192,
                          "actor_instabilities": 0, "ce_outputs": len(ce), "ce_instabilities": 0,
                          "main_ce_outputs": len(ce_main), "main_ce_total_transitions": 8324},
        "matched_ce_first_attainment": ce_first,
        "matched_npg": {"stages": len(npg), "trajectories": len(paths), "instabilities": 0,
                        "rank2_endpoint_gap_medians": gaps, "rank2_within_system_gap_ratio": gaps["dense"] / gaps["truncated"],
                        "rank2_attainment_appendix_only": npg_first},
        "precision_ce": check_high_rank(base / "precision_ce"),
        "adaptive_ce_appendix": check_high_rank(base / "adaptive_ce", adaptive=True),
    }
    if with_plots:
        plot1 = root / "01_input_padding/plots"
        plot4 = root / "04_ce100_matched_gap_and_high_rank/plots"
        verified_stats = {}
        definitions = [
            (plot1 / "main_ce_input_padding_statistics.csv", ce_main, ("algorithm", "mode", "m", "N", "transitions")),
            (plot1 / "appendix_actor_endpoint_statistics.csv", actors, ("algorithm", "mode", "m", "assigned_transitions")),
            (plot4 / "high_rank_ce_all_budget_statistics.csv", rows(base / "precision_ce/endpoints.csv"), ("rank", "method", "budget")),
            (plot4 / "appendix_empirical_adaptive_ce_all_budget_statistics.csv", rows(base / "adaptive_ce/endpoints.csv"), ("rank", "method", "budget")),
            (plot4 / "appendix_matched_npg_all_stage_statistics.csv", npg, ("rank", "method", "stage", "transitions")),
        ]
        for path, data, fields in definitions:
            verified_stats[path.relative_to(root).as_posix()] = check_plot_statistics(path, data, fields)
        table = rows(plot4 / "table_1_ce_accuracy.csv")
        assert len(table) == 18
        for row in table:
            rank, method = int(row["rank"]), row["method"]
            assert not yes(row["right_censored"]) and int(row["instabilities_at_first_hit"]) == 0
            if row["study"] == "CE100_matched_initial_gap":
                reference = selected[(rank, method)]
                assert int(row["denominator"]) == 30 and int(row["physical_systems_per_rank"]) == 1
                assert int(row["successes_at_first_hit"]) == reference["successes"]
                close(row["first_tested_total_transitions"], reference["transitions"])
            else:
                assert row["study"] == "CE100_high_rank_precision_zoom"
                ref_method = "raw" if method == "dense" else method
                reference = next(r for r in result["precision_ce"]["first_attainment"] if r["rank"] == rank and r["method"] == ref_method)
                assert int(row["denominator"]) == 2 and int(row["successes_at_first_hit"]) == 2
                close(row["first_tested_total_transitions"], reference["first_transitions"])
        empirical = rows(plot4 / "appendix_empirical_adaptive_ce_all_budget_statistics.csv")
        assert sum(int(r["failure_count"]) for r in empirical) == 8
        result["restored_plot_statistics_independently_verified"] = verified_stats
        result["ce_table_1_rows_verified"] = len(table)
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = verify(root)
    (root / "restored_validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
