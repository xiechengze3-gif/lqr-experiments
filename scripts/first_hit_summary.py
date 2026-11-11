"""Distinguish first observed success from sustained success, without new runs."""
import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path

if not os.environ.get("SLURM_JOB_ID"):
    raise RuntimeError("Run reporting on Grace compute nodes")
parser = argparse.ArgumentParser()
parser.add_argument("--root", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
fields = ["mode", "n", "m", "r", "tail", "tail_shape", "horizon", "sigma",
          "a_norm", "k0_norm", "batch_blocks", "stages", "method", "criterion", "epsilon"]
output = []
for name in ("pilot-5d78e80516eb6812", "actor-refinement-197699f5", "tail-controls-47965418"):
    groups = defaultdict(list)
    report = Path(args.root) / name / "report"
    for row in csv.DictReader((report / "success_rates.csv").open()):
        groups[tuple(row[field] for field in fields)].append(row)
    for key, rows in groups.items():
        rows.sort(key=lambda row: int(row["transitions"]))
        complete = all(row["complete_tasks"] == row["expected"] for row in rows)
        hits = [row for row in rows if float(row["success_rate"]) >= .9] if complete else []
        sustained = None
        if complete:
            for index, row in enumerate(rows):
                if all(float(point["success_rate"]) >= .9 for point in rows[index:]):
                    sustained = int(row["transitions"])
                    break
        output.append(dict(experiment=name, **dict(zip(fields, key)),
                           first_pointwise_success_transitions=int(hits[0]["transitions"]) if hits else None,
                           first_pointwise_success_stage=hits[0]["stage"] if hits else None,
                           sustained_success_transitions=sustained,
                           largest_measured_transitions=int(rows[-1]["transitions"]),
                           complete_grid=complete))
path = Path(args.output)
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(output[0]))
    writer.writeheader()
    writer.writerows(output)
print(f"First-hit comparison rows: {len(output)}")
