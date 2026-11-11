"""Summarize the predeclared manifest, retaining missing and failed replicates."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

from lqr_experiments import atomic_json, burn_blocks, require_compute


FIELDS = ["mode", "n", "m", "r", "tail", "tail_shape", "horizon", "sigma",
          "a_norm", "k0_norm", "batch_blocks", "stages"]


def expected_grid(task):
    n, m, rank = task["n"], task["m"], task["r"]
    p0 = (1 + task["k0_norm"] ** 2) / (1 - (task["a_norm"] + task["k0_norm"]) ** 2)
    scalar = dict(p0=p0)
    ranks = sorted(set([max(1, rank // 2), rank, min(2 * rank, min(n, m))]))
    if task["mode"] == "actor":
        burn = burn_blocks(scalar, np.full(n, 100 * math.sqrt(2 * p0)), task["horizon"], task["sigma"])
        methods = ["raw", f"rank_{rank}", "oracle_subspace"]
        for method in methods:
            for stage in range(task["stages"] + 1):
                count = stage * task["batch_blocks"]
                transitions = stage * (burn + task["batch_blocks"] + 1) * task["horizon"]
                yield method, count, stage, transitions
    else:
        h = 1 if task["mode"] == "ce" else task["horizon"]
        burn = burn_blocks(scalar, np.zeros(n), h, task["sigma"])
        if task["mode"] == "critic":
            methods = ["raw", *[f"rank_{r}" for r in ranks], "oracle_subspace"]
        else:
            methods = ["raw", *[f"B_rank_{r}" for r in ranks], "oracle_subspace",
                       *[f"K_rank_{r}" for r in ranks]]
        for method in methods:
            for count in task["budgets"]:
                transitions = (burn + count + 1) * h if task["mode"] == "critic" else burn + count
                yield method, count, None, transitions


def cluster_interval(rows, value_fn, draws=2000):
    # Resample systems, then trajectories within each sampled system. This
    # avoids treating 64 trajectories on eight systems as 64 independent systems.
    clusters = defaultdict(list)
    for row in rows:
        clusters[row["system_seed"]].append(float(value_fn(row)))
    rng = np.random.default_rng(61903)
    arrays = [np.asarray(values) for _, values in sorted(clusters.items())]
    if not arrays:
        return None, None
    sampled = rng.integers(len(arrays), size=(draws, len(arrays)))
    cluster_means = np.empty_like(sampled, dtype=float)
    for slot in range(len(arrays)):
        for index, values in enumerate(arrays):
            selected = sampled[:, slot] == index
            cluster_means[selected, slot] = rng.choice(values, size=(int(selected.sum()), len(values)), replace=True).mean(axis=1)
    means = cluster_means.mean(axis=1)
    return tuple(float(x) for x in np.quantile(means, [.025, .975]))


def write_csv(path, rows):
    if not rows:
        return
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def summarize(manifest_path, raw_path, out_path):
    require_compute()
    data = Path(manifest_path).read_bytes()
    manifest = json.loads(data)
    manifest_hash = hashlib.sha256(data).hexdigest()
    output = Path(out_path)
    output.mkdir(parents=True, exist_ok=True)
    groups, rows, task_status, payloads = defaultdict(list), [], [], {}
    for task_id, task in enumerate(manifest["tasks"]):
        path = Path(raw_path) / f"task-{task_id:05d}.json"
        payload = json.loads(path.read_text()) if path.exists() else None
        if payload and (payload["task"] != task or payload["manifest_sha256"] != manifest_hash):
            raise RuntimeError(f"Manifest mismatch: {path}")
        status = payload["status"] if payload else "missing"
        task_status.append(dict(task_id=task_id, status=status, mode=task["mode"]))
        if payload:
            payloads[task_id] = payload
        observed = {(row["method"], row["N"], row.get("stage")): row
                    for row in payload.get("records", [])} if payload else {}
        family = tuple(task.get(field) for field in FIELDS)
        for method, count, stage, transitions in expected_grid(task):
            row = dict(task_id=task_id, **{field: task.get(field) for field in FIELDS},
                       system_seed=task["system_seed"], trial_seed=task["trial_seed"],
                       method=method, N=count, stage=stage, transitions=transitions,
                       task_status=status, observed=False, stable=False, gap=None,
                       relative_gap=None)
            actual = observed.get((method, count, stage))
            if actual:
                if actual["transitions"] != transitions:
                    raise RuntimeError("Unexpected primitive sample count")
                row.update(actual, observed=True)
            elif status == "complete" and task["mode"] != "actor":
                raise RuntimeError("Complete collector is missing a planned budget")
            # Future actor rows after instability remain failures. They do not
            # disappear from later-budget denominators.
            rows.append(row)
            groups[(family, method, count, stage, transitions)].append(row)
    write_csv(output / "all_records.csv", rows)
    write_csv(output / "task_status.csv", task_status)
    aggregate, success_rows = [], []
    for (family, method, count, stage, transitions), replicate_rows in groups.items():
        info = dict(zip(FIELDS, family), method=method, N=count, stage=stage, transitions=transitions)
        info.update(expected=len(replicate_rows), observed=sum(row["observed"] for row in replicate_rows),
                    complete_tasks=sum(row["task_status"] == "complete" for row in replicate_rows),
                    stable_rate=np.mean([row["stable"] for row in replicate_rows]))
        for key in ("error_fro2", "error_op", "gap", "relative_gap", "gain_error_fro2"):
            values = [row[key] for row in replicate_rows if row.get(key) is not None]
            if values:
                info[f"{key}_median_available"] = float(np.median(values))
                info[f"{key}_count"] = len(values)
        aggregate.append(info)
        for criterion, epsilons in (("gap", manifest["absolute_epsilons"]),
                                    ("relative_gap", manifest["relative_epsilons"])):
            for epsilon in epsilons:
                def is_success(row):
                    return bool(row["stable"] and row.get(criterion) is not None and row[criterion] <= epsilon)
                rate = float(np.mean([is_success(row) for row in replicate_rows]))
                lower, upper = cluster_interval(replicate_rows, is_success)
                success_rows.append(dict(info, criterion=criterion, epsilon=epsilon,
                                         success_rate=rate, success_ci_low=lower, success_ci_high=upper))
    write_csv(output / "aggregate.csv", aggregate)
    write_csv(output / "success_rates.csv", success_rows)
    curves = defaultdict(list)
    for row in success_rows:
        key = tuple(row[field] for field in FIELDS) + (row["method"], row["criterion"], row["epsilon"])
        curves[key].append(row)
    thresholds = []
    for key, curve in curves.items():
        curve.sort(key=lambda row: row["transitions"])
        threshold = None
        all_complete = all(row["complete_tasks"] == row["expected"] for row in curve)
        if all_complete:
            for index, row in enumerate(curve):
                if all(point["success_rate"] >= manifest["target_success"] for point in curve[index:]):
                    threshold = row["transitions"]
                    break
        thresholds.append(dict(zip(FIELDS, key[:len(FIELDS)]), method=key[-3],
                               criterion=key[-2], epsilon=key[-1],
                               transitions_to_sustained_pointwise_success=threshold,
                               complete_grid=all_complete,
                               censored=threshold is None,
                               largest_measured_transitions=curve[-1]["transitions"]))
    write_csv(output / "sample_thresholds.csv", thresholds)
    # Paired improvements use the same task, same prefix and same true target.
    paired = []
    for task_id, payload in payloads.items():
        records = payload.get("records", [])
        raw = {(row["N"], row.get("stage")): row for row in records if row["method"] == "raw"}
        for row in records:
            counterpart = raw.get((row["N"], row.get("stage")))
            if not counterpart or row["method"] == "raw":
                continue
            pair = dict(task_id=task_id, method=row["method"], N=row["N"],
                        transitions=row["transitions"], mode=payload["task"]["mode"])
            for key in ("error_fro2", "gap"):
                if row.get(key) is not None and counterpart.get(key) is not None and counterpart[key] > 1e-12:
                    pair[f"{key}_ratio_to_raw"] = row[key] / counterpart[key]
            pair["stable"] = row["stable"]
            pair["raw_stable"] = counterpart["stable"]
            paired.append(pair)
    write_csv(output / "paired.csv", paired)
    counts = {status: sum(row["status"] == status for row in task_status)
              for status in ("complete", "failed", "missing")}
    atomic_json(output / "summary.json", dict(profile=manifest["profile"], counts=counts,
                                             expected=len(task_status), manifest_sha256=manifest_hash))
    text = (f"LQR {manifest['profile']} summary\n\n"
            f"Tasks: {counts['complete']} complete, {counts['failed']} failed, {counts['missing']} missing.\n"
            "Sample counts include burn-in, baseline blocks and every policy stage.\n"
            "Missing tasks and unstable actor continuations remain in success denominators.\n"
            "Sample thresholds use 90% point success sustained at all larger measured budgets.\n"
            "These are empirical grid thresholds, not confidence-certified complexity guarantees.\n"
            "Uncertainty intervals resample systems and trajectories hierarchically; the pilot\n"
            "has only two systems and cannot establish population scaling.\n"
            "Available-only median costs must be interpreted together with success/stability rates.\n"
            "oracle_subspace methods use simulator truth and are diagnostic references.\n")
    (output / "REPORT.txt").write_text(text, encoding="utf-8")
    plot_curves(output, aggregate)
    print(json.dumps(counts), flush=True)


def plot_curves(output, aggregate):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    families = defaultdict(list)
    for row in aggregate:
        families[tuple(row.get(field) for field in FIELDS)].append(row)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    for index, (family, values) in enumerate(families.items()):
        info = dict(zip(FIELDS, family))
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        methods = sorted(set(row["method"] for row in values))
        metric = "error_fro2_median_available" if info["mode"] == "critic" else "gap_median_available"
        for method in methods:
            curve = sorted((row for row in values if row["method"] == method), key=lambda row: row["transitions"])
            valid = [row for row in curve if row["transitions"] > 0 and row.get(metric, 0) > 0]
            if valid:
                axes[0].loglog([row["transitions"] for row in valid], [row[metric] for row in valid], label=method)
            valid = [row for row in curve if row["transitions"] > 0]
            axes[1].semilogx([row["transitions"] for row in valid], [row["stable_rate"] for row in valid], label=method)
        axes[0].set_ylabel("Frobenius error squared" if info["mode"] == "critic" else "Absolute cost gap (available stable runs)")
        axes[1].set_ylabel("Stable fraction (all planned replicates)")
        axes[1].set_ylim(-.02, 1.02)
        for ax in axes:
            ax.set_xlabel("Primitive transitions")
            ax.grid(alpha=.2)
        axes[0].legend(fontsize=7)
        fig.suptitle(f"{info['mode']} n=m={info['n']}, r={info['r']}, tail={info['tail']} {info['tail_shape']}, batch={info['batch_blocks']}")
        fig.tight_layout()
        fig.savefig(figures / f"family-{index:03d}.png", dpi=160)
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    summarize(args.manifest, args.raw, args.output)
