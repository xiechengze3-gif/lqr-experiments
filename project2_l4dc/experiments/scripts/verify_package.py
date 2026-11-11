"""Verify packaged existing records and emit an explicit completeness report."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def readcsv(relative):
    with (ROOT / relative).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def stable(row):
    return row["stable"].lower() == "true"


def main():
    extractions = json.loads((ROOT / "provenance/extractions.json").read_text(encoding="utf-8"))
    checked = 0
    for entry in extractions:
        path = ROOT / entry["target"]
        assert digest(path) == entry.get("target_sha256", entry.get("sha256")), entry["target"]
        checked += 1
    ce = readcsv("02_same_data_decomposition/data/ce_same_data.csv")
    step = readcsv("02_same_data_decomposition/data/npg_same_blocks.csv")
    assert len(ce) == 1008 and len(step) == 96
    assert all(r["algorithm"] == "CE" and r["spectrum"] == "exact" and r["n"] == "24" and r["r"] == "2" for r in ce)
    assert all(r["source_mode"] == "dense" and r["stage"] == "1" for r in step)
    keys = [(r["A_family"], r["system"], r["trial"], r["mode"]) for r in step]
    assert len(set(keys)) == len(keys), "Duplicated first-stage source path"
    assert Counter((r["A_family"], r["mode"]) for r in step) == Counter({(a, m): 24 for a in ("scalar", "dense") for m in ("dense", "truncated")})
    assert all(stable(r) for r in ce + step)
    residual = max(abs(float(r["decomposition_residual"])) / max(1, abs(float(r["cost"]))) for r in ce + step)
    assert residual < 1e-10

    exact = readcsv("appendix/data/exact_rank_npg_endpoints.csv")
    assert len(exact) == 576
    failures = {mode: {"count": sum(r["mode"] == mode for r in exact),
                       "failed": sum(r["mode"] == mode and not stable(r) for r in exact)}
                for mode in ("dense", "truncated")}
    assert failures == {"dense": {"count": 288, "failed": 163}, "truncated": {"count": 288, "failed": 65}}
    full = readcsv("03_fullrank_rank_scan/data/fullrank_all_outputs.csv")
    assert len(full) == 54264
    terminal = {}
    for row in full:
        assert row["spectrum"] in ("gapped", "smooth", "flat")
        if row["algorithm"] == "NPG":
            key = (row["task_id"], row["mode"])
            if key not in terminal or int(row["stage"]) > int(terminal[key]["stage"]):
                terminal[key] = row
    assert len(terminal) == 936 and all(stable(r) for r in terminal.values())
    assert all(stable(r) for r in full)
    flat_modes = sorted({r["mode"] for r in full if r["algorithm"] == "NPG" and r["spectrum"] == "flat"})
    assert flat_modes == ["dense", "k2", "k8"], flat_modes

    source = ROOT / "provenance/original/local_runs/ce-npg-initial-gap-20261028/report/attainment_side_by_side.csv"
    with source.open(encoding="utf-8-sig", newline="") as f:
        rel = [r for r in csv.DictReader(f) if r["algorithm"] == "NPG" and r["n"] == "24" and r["spectrum"] == "exact" and float(r["epsilon"]) == .1]
    assert len(rel) == 16
    assert all(r["relative_right_censored"].lower() == "true" for r in rel)
    display = readcsv("02_same_data_decomposition/plots/main_figure_statistics.csv")
    group_fields = ("algorithm", "A_family", "spectrum", "n", "r", "mode", "N", "transitions", "stage")
    for stat in display:
        data = ce if stat["algorithm"] == "CE" else step
        selected = [r for r in data if all(r.get(key, "") == stat.get(key, "") for key in group_fields)]
        assert len(selected) == 24 and all(stable(r) for r in selected)
        values = [float(r[stat["metric"]]) for r in selected]
        q25, _, q75 = statistics.quantiles(values, n=4, method="inclusive")
        for field, reference in (("median", statistics.median(values)), ("q25", q25), ("q75", q75)):
            assert math.isclose(float(stat[field]), reference, rel_tol=1e-12, abs_tol=1e-12)
    ranks = readcsv("03_fullrank_rank_scan/plots/main_rank_scan_statistics.csv")
    assert len(ranks) == 288 and all(int(s["count"]) == 24 and int(s["failure_count"]) == 0 for s in ranks)
    flat = readcsv("03_fullrank_rank_scan/plots/flat_negative_control_statistics.csv")
    assert len(flat) == 6 and {(s["algorithm"], s["mode"]) for s in flat} == {(a, m) for a in ("CE", "NPG") for m in ("dense", "k2", "k8")}
    plot_status = json.loads((ROOT / "plot_status.json").read_text(encoding="utf-8"))
    group_names = ("01_input_padding", "02_same_data_decomposition", "03_fullrank_rank_scan", "04_ce100_matched_gap_and_high_rank")
    assert all(plot_status["groups"][name]["status"] == "complete" for name in group_names)
    for name in group_names:
        artifacts = plot_status["groups"][name].get("artifacts", [])
        assert artifacts, f"No rendered artifacts: {name}"
        assert all((ROOT / path).is_file() and (ROOT / path).stat().st_size > 0 for path in artifacts)
    from verify_restored_results import verify as verify_restored
    restored = verify_restored(ROOT)
    (ROOT / "restored_validation.json").write_text(json.dumps(restored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    package = json.loads((ROOT / "package_status.json").read_text(encoding="utf-8"))
    retrieval = json.loads((ROOT / "provenance/retrieval_manifest.json").read_text(encoding="utf-8"))
    missing = []
    for item in retrieval["files"]:
        p = ROOT / item["target"]
        if not p.is_file() or digest(p) != item["sha256"]:
            missing.append(item["target"])
    result = {
        "available_data_checks_passed": True,
        "all_four_groups_complete": not missing and all(plot_status["groups"][n]["status"] == "complete" for n in group_names),
        "restored_archived_files_verified": restored["archived_files_verified"],
        "restored_archived_bytes_verified": restored["archived_bytes_verified"],
        "input_padding_checks": restored["input_padding"],
        "matched_gap_npg_trajectories": restored["matched_npg"]["trajectories"],
        "matched_gap_npg_instabilities": restored["matched_npg"]["instabilities"],
        "precision_ce_outputs": restored["precision_ce"]["outputs"],
        "adaptive_ce_unstable_outputs_retained": restored["adaptive_ce_appendix"]["unstable_outputs"],
        "original_or_extracted_files_verified": checked,
        "same_data_ce_outputs": len(ce), "same_blocks_npg_outputs": len(step),
        "same_data_max_normalized_decomposition_residual": residual,
        "exact_rank_npg_failures": failures,
        "selected_fullrank_npg_terminal_count": len(terminal),
        "selected_fullrank_npg_terminal_failures": 0,
        "flat_npg_modes": flat_modes,
        "n24_npg_relative_10pct_conditions": len(rel),
        "n24_npg_relative_10pct_all_censored": True,
        "same_data_figure_statistics_independently_verified": len(display),
        "main_rank_scan_stable_cells": len(ranks),
        "flat_control_cells": len(flat),
        "rendered_figure_count": sum(1 for p in ROOT.rglob("*.png") if "plots" in p.parts),
        "groups": {k: v["status"] for k, v in package["groups"].items()},
        "missing_historical_files": missing,
        "new_learning_runs": 0, "new_control_solves": 0,
    }
    (ROOT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    excluded = {".cache", ".tmp", ".runtime", "__pycache__"}
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name != "SHA256SUMS" and not excluded.intersection(p.relative_to(ROOT).parts))
    (ROOT / "SHA256SUMS").write_text("".join(f"{digest(p)}  {p.relative_to(ROOT).as_posix()}\n" for p in files), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "missing_historical_files"}, indent=2))


if __name__ == "__main__":
    main()
