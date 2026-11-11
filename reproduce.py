"""Verify and rerender the saved LQR experiment results."""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
from collections import defaultdict

ROOT = Path(__file__).resolve().parent
EXPERIMENTS = ROOT / "project2_l4dc/experiments"
CORE = (
    "01_input_padding", "02_same_data_decomposition", "03_fullrank_rank_scan",
    "04_ce100_matched_gap_and_high_rank", "appendix", "provenance", "scripts",
    "package_status.json",
)


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def verify_manifest():
    seen = set()
    for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT) and path not in seen, f"Invalid manifest path: {name}")
        seen.add(path)
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        require(actual == expected, f"SHA-256 mismatch: {name}")
    print(f"Verified SHA-256 for {len(seen)} files.")


def verify_x13():
    folder = EXPERIMENTS / "x13-20261108/formal"
    groups = defaultdict(list)
    for row in read_csv(folder / "records.csv"):
        groups[row["m_minus_r"], row["N"], row["arm"]].append(row)
    cells = read_csv(folder / "X1_normalized_statistics.csv")
    require(len(cells) == len(groups) == 24, "X13 cell coverage")
    for cell in cells:
        key = cell["m_minus_r"], cell["N"], cell["mode"]
        rows = groups.pop(key)
        values = [float(row["N_D_over_v_star"]) for row in rows]
        failures = sum(row["stable"] == "False" for row in rows)
        require(len({(row["system"], row["seed"]) for row in rows}) == len(rows) == int(cell["count"]) == 32,
                f"X13 denominator {key}")
        require(failures == sum(math.isinf(value) for value in values) == int(cell["failures"]),
                f"X13 failures {key}")
        q25, median, q75 = statistics.quantiles(values, n=4, method="inclusive")
        for column, computed in (("q25", q25), ("median", median), ("q75", q75)):
            require(math.isclose(float(cell[column]), computed, rel_tol=1e-12), f"X13 {column} {key}")
    print("Recomputed all 24 X13 CE cells from 768 arm outputs.")


def verify_actor_grid(path, *, tail):
    rows = read_csv(path)
    expected = {(algorithm, alpha, 2.0 ** -j)
                for algorithm in ("NPG", "PI")
                for alpha in ((0, .02, .05, .1, .2, .4) if tail else (None,))
                for j in range(9)}
    for ratio_kind in {row["ratio_kind"] for row in rows}:
        selected = [row for row in rows if row["ratio_kind"] == ratio_kind]
        actual = {(row["algorithm"], float(row["alpha"]) if tail else None, float(row["rung"]))
                  for row in selected}
        require(len(selected) == len(expected) and actual == expected,
                f"{path.name}: coverage for {ratio_kind}")
    require({row["ratio_kind"] for row in rows} == {"both_stable", "failure_inclusive"},
            f"{path.name}: missing ratio convention")
    for row in rows:
        both, neither, dense_failed, truncated_failed = (
            int(row[key]) for key in ("both_stable", "both_failed", "dense_only_failed", "truncated_only_failed")
        )
        require(both + neither + dense_failed + truncated_failed == int(row["full_pairs"]) == 32,
                f"{path.name}: pair denominator")
        require(both + truncated_failed == int(row["dense_stable"])
                and both + dense_failed == int(row["truncated_stable"]), f"{path.name}: stability counts")
    print(f"Verified {len(expected)} paired cells in {path.name}.")


def run_python(script, *args, env):
    subprocess.run([sys.executable, "-B", str(script), *map(str, args)], cwd=ROOT, env=env, check=True)


def stage(output, source, names):
    output.mkdir()
    for name in names:
        original = source / name
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if original.is_dir():
            shutil.copytree(original, dest)
        else:
            shutil.copyfile(original, dest)


def render_figures(output, env):
    core = output / "core"
    stage(core, EXPERIMENTS, CORE)
    run_python(core / "scripts/plot_results.py", "--root", core, env=env)
    run_python(core / "scripts/verify_package.py", env=env)
    supplement = output / "supplement"
    stage(supplement, EXPERIMENTS / "supplement-20261101", (
        "plot_saved_figures.py", "X1/report-ce-v2/normalized_statistics.csv",
        "X1/report-ce/all_statistics.csv", "X2/report-ce/fixed_budget_ratios.csv",
        "X3/report-ce/fixed_k_envelope.csv", "X1/report-actors/endpoint_statistics.csv",
        "X2/report-actors/endpoint_statistics.csv", "X4/report/robustness_statistics.csv",
        "analysis-P1-P2-v1/REPORT.json", "analysis-P1-P2-v1/decomposition_statistics.csv",
        "X3/report-actors-order-envelope-v2/REPORT.json",
        "X3/report-actors-order-envelope-v2/fixed_order_median_envelope.csv",
        "X3/report-actors/endpoint_statistics.csv", "X3/report-npg-last-estimator-v1/REPORT.json",
        "X3/report-npg-last-estimator-v1/last_estimator_statistics.csv",
    ))
    run_python(supplement / "plot_saved_figures.py", "--output", output / "supplement-figures", env=env)
    tail = output / "tail-x14"
    stage(tail, EXPERIMENTS / "x14-20261108", ("plot_x14.py", "X9_summary_merged_nine_rungs.csv"))
    run_python(tail / "plot_x14.py", env=env)


def run_smoke(env):
    for test in ("test_direct_stein_final.py", "test_final_failure_paths.py"):
        run_python(ROOT / "scripts" / test, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    for command in ("figures", "smoke"):
        commands.add_parser(command).add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        verify_manifest()
        verify_x13()
        x14 = EXPERIMENTS / "x14-20261108"
        verify_actor_grid(x14 / "X9_summary_merged_nine_rungs.csv", tail=True)
        verify_actor_grid(x14 / "delivery-f-full-report/B60_summary.csv", tail=False)
        return

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime = output / ".runtime"
    runtime.mkdir()
    env = os.environ.copy()
    for key in ("MPLCONFIGDIR", "TMP", "TEMP", "TMPDIR", "XDG_CACHE_HOME", "NUMBA_CACHE_DIR"):
        env[key] = str(runtime)
    for key in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        env[key] = "1"
    if args.command == "figures":
        render_figures(output, env)
    else:
        run_smoke(env)


if __name__ == "__main__":
    main()
