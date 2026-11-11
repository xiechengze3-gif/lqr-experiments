"""Simulator-truth references, run separately on Grace, never used for training."""
import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--release", required=True)
parser.add_argument("--manifest", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
sys.path.insert(0, args.release)
from lqr_experiments import (actor_step, atomic_json, evaluate, lqr, make_system,
                             require_compute, residual_targets, spectral, truncate)

require_compute()
manifest = json.loads(Path(args.manifest).read_text())
seen, rows = set(), []
for task in manifest["tasks"]:
    key = tuple(task.get(k) for k in ("n", "m", "r", "tail", "tail_shape", "system_seed"))
    if key in seen:
        continue
    seen.add(key)
    system = make_system(task)
    gain, _ = lqr(system["A"], truncate(system["B"], task["r"]), system["Q"], system["R"])
    quality, _ = evaluate(system, gain)
    row = dict(zip(("n", "m", "r", "tail", "tail_shape", "system_seed"), key),
               ideal_B_truncation_gap=quality["gap"],
               ideal_K_truncation_gap=evaluate(system, truncate(system["Kstar"], task["r"]))[0]["gap"],
               B_tail=system["diagnostics"]["B"], Kstar_tail=system["diagnostics"]["Kstar"])
    for target in ("infinite", "finite_H"):
        k = system["K0"].copy()
        quality = None
        change = None
        for stage in range(200):
            z, zh = residual_targets(system, k, task["horizon"])
            estimate = truncate(z if target == "infinite" else zh, task["r"])
            candidate = k - actor_step(system) * (system["R"] @ k + estimate)
            change = spectral(candidate - k)
            quality, _ = evaluate(system, candidate)
            if stage == 31:
                row[f"ideal_NPG_{target}_stage32_gap"] = quality["gap"]
            k = candidate
            if not quality["stable"]:
                break
        row[f"ideal_NPG_{target}_stage200_gap"] = quality["gap"]
        row[f"ideal_NPG_{target}_last_change_op"] = change
        row[f"ideal_NPG_{target}_stable"] = quality["stable"]
    rows.append(row)
atomic_json(args.output, dict(reference_only=True, description="Exact-parameter, zero-statistical-noise references; no data-complexity credit.", rows=rows))
print(json.dumps({"diagnostic_cases": len(rows)}), flush=True)
