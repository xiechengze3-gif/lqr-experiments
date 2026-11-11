"""Assemble audited existing records. No sampling or control solves are run."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
SNAPSHOT = "/scratch/user/changze/lqr_experiments/local-archives/20261025/snapshot/"
GROUPS = {
    "01_input_padding": "input-padding CE/NPG; PI retained for appendix only",
    "02_same_data_decomposition": "shared-data CE and first-step NPG mechanism",
    "03_fullrank_rank_scan": "gapped/smooth full-rank k scans and flat negative control",
    "04_ce100_matched_gap_and_high_rank": "CE100 matched gap and high-rank CE; NPG supplemental",
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def readcsv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def writecsv(path, rows):
    if not rows:
        raise ValueError(f"Empty extraction: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def writejson(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def retrieve_set(manifest):
    rules = [
        (r"^results/final-story-20261024/report/(actor_endpoints|ce_all_prefixes|e1_ce_redundant_summary|e1_paired_gap_ratios|e1_summary|output_coverage|summary|system_tails_certificates)\.(csv|json)$", "01_input_padding", "report"),
        (r"^results/matched-gap-npg-pi-v2-20261019/report-confirm/(npg-(all-checkpoints|summary)|sample_complexity|success_by_budget|summary)\.(csv|json)$", "04_ce100_matched_gap_and_high_rank", "matched_npg"),
        (r"^results/matched-gap-npg-pi-v2-20261019/historical_CE_reference/report-confirm/[^/]+\.(csv|json)$", "04_ce100_matched_gap_and_high_rank", "matched_ce"),
        (r"^results/grace-ce-adaptive-zoom[^/]+/results/ce-adaptive-zoom[^/]+/report/[^/]+\.(csv|json)$", "04_ce100_matched_gap_and_high_rank", "adaptive_ce"),
        (r"^results/grace-ce-precision-zoom[^/]+/results/ce-precision-zoom[^/]+/report/[^/]+\.(csv|json)$", "04_ce100_matched_gap_and_high_rank", "precision_ce"),
    ]
    selected = []
    for item in manifest["files"]:
        for regex, group, subdir in rules:
            if re.match(regex, item["id"]):
                target = f"{group}/data/{subdir}/{Path(item['id']).name}"
                local = ROOT / target
                selected.append({
                    "id": item["id"], "remote": SNAPSHOT + item["id"],
                    "target": target, "size": item["size"], "sha256": item["sha256"],
                    "available_and_verified": local.is_file() and digest(local) == item["sha256"],
                })
                break
    assert len(selected) == 32, len(selected)
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=PROJECT)
    args = parser.parse_args()
    project = args.project.resolve()
    provenance = []
    for group in GROUPS:
        (ROOT / group / "data").mkdir(parents=True, exist_ok=True)
    report = project / "local_runs/ce-npg-arguments-20261028/report"
    allrows = readcsv(report / "all_records.csv")
    assert len(allrows) == 96600
    sums = {}
    for line in (report / "SHA256SUMS").read_text().splitlines():
        value, name = line.split(maxsplit=1)
        sums[Path(name.lstrip("*")).name] = value
    for name in ("all_records.csv", "same_blocks_diagnostic.csv", "endpoint_all_denominators.csv"):
        assert digest(report / name) == sums[name], f"Historical hash mismatch: {name}"

    def extract(name, rows, source, selection):
        output = ROOT / name
        writecsv(output, rows)
        provenance.append({"target": name, "rows": len(rows), "source": str(source),
                           "source_sha256": digest(source), "selection": selection,
                           "target_sha256": digest(output)})

    extract("02_same_data_decomposition/data/ce_same_data.csv",
            [r for r in allrows if r["algorithm"] == "CE" and r["spectrum"] == "exact" and r["n"] == "24" and r["r"] == "2"],
            report / "all_records.csv", "CE, exact, n=24, r=2; both A families; every saved prefix/mode")
    extract("02_same_data_decomposition/data/npg_same_blocks.csv",
            [r for r in readcsv(report / "same_blocks_diagnostic.csv")
             if r["spectrum"] == "exact" and r["n"] == "24" and r["r"] == "2"
             and r["source_mode"] == "dense" and r["stage"] == "1"],
            report / "same_blocks_diagnostic.csv", "exact, n=24,r=2, stage=1, source_mode=dense; one source per repeat, dense/truncated counterfactuals")
    extract("03_fullrank_rank_scan/data/fullrank_all_outputs.csv",
            [r for r in allrows if r["spectrum"] in ("gapped", "smooth", "flat")],
            report / "all_records.csv", "gapped/smooth/flat; all algorithms, A families, k and saved budgets; no survivor selection")
    extract("appendix/data/tail_strength_all_outputs.csv",
            [r for r in allrows if r["spectrum"] in ("gapped001", "gapped02")],
            report / "all_records.csv", "additional tail-strength negative controls, all saved records")
    endpoints = {}
    for row in allrows:
        if row["algorithm"] == "NPG" and row["spectrum"] == "exact":
            key = (row["task_id"], row["mode"])
            if key not in endpoints or int(row["stage"]) > int(endpoints[key]["stage"]):
                endpoints[key] = row
    assert len(endpoints) == 576
    extract("appendix/data/exact_rank_npg_endpoints.csv", list(endpoints.values()),
            report / "all_records.csv", "all 576 exact-rank NPG endpoints, including absorbing failure outputs")

    copy_paths = [
        "local_runs/ce-npg-arguments-20261028/report/endpoint_all_denominators.csv",
        "local_runs/ce-npg-arguments-20261028/report/failed_outputs.csv",
        "local_runs/ce-npg-arguments-20261028/report/system_certificates.json",
        "local_runs/ce-npg-arguments-20261028/report/SHA256SUMS",
        "local_runs/ce-npg-initial-gap-20261028/report/attainment_side_by_side.csv",
        "local_runs/ce-npg-initial-gap-20261028/report/initial_gap_by_task.csv",
        "receipts/ce-npg-arguments-20261028-complete.json",
        "receipts/ce-npg-arguments-20261028-delivery-audit.json",
        "receipts/ce-npg-arguments-20261028-local-verification.json",
        "receipts/final-story-20261024-complete.json",
        "receipts/matched-gap-npg-pi-20261019.json",
        "receipts/ce-matched-initial-gap-20261018.json",
        "receipts/ce-precision-zoom.json", "receipts/ce-adaptive-zoom.json",
        "docs/FINAL_STORY_FINDINGS_20261024.md",
        "docs/CE_NPG_ARGUMENT_FINDINGS_20261028.md",
        "docs/CE_NPG_INITIAL_GAP_FINDINGS_20261028.md",
        "docs/MATCHED_GAP_NPG_PI_FINDINGS_20261019.md",
        "docs/CE_MATCHED_INITIAL_GAP_FINDINGS_20261018.md",
        "docs/CE_PRECISION_ZOOM_FINDINGS.md", "docs/CE_ADAPTIVE_ZOOM_FINDINGS.md",
        "docs/PROJECT2_K0_A_B_CONSTRUCTION_AUDIT_20261022.md",
        "docs/PROJECT2_EXPERIMENT_FAIRNESS_AUDIT_20261022.md",
        "configs/ce_npg_argument_revision_20261027.json",
        "configs/ce_matched_initial_gap_20261018.json",
        "configs/matched_gap_npg_pi_v2_20261019.json",
        "configs/ce_adaptive_zoom.json", "configs/ce_precision_zoom.json",
    ]
    scripts = ["ce_npg_argument_run", "ce_npg_argument_grid", "ce_npg_argument_report",
               "ce_npg_initial_gap_postprocess", "final_story", "final_story_report_v4",
               "final_story_robustness", "matched_gap_npg_pi", "matched_gap_npg_pi_report",
               "plot_matched_gap_final_review", "ce_matched_initial_gap", "ce_matched_initial_gap_report",
               "ce_precision_zoom", "ce_adaptive_zoom"]
    seen = set()
    while scripts:
        name = scripts.pop()
        source = project / "scripts" / (name + ".py")
        if name in seen or not source.is_file():
            continue
        seen.add(name)
        copy_paths.append(source.relative_to(project).as_posix())
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
            for module in modules:
                if module and (project / "scripts" / (module.split(".")[0] + ".py")).is_file():
                    scripts.append(module.split(".")[0])
    for rel in copy_paths:
        source, target = project / rel, ROOT / "provenance/original" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        assert digest(source) == digest(target)
        provenance.append({"target": target.relative_to(ROOT).as_posix(), "source": str(source), "sha256": digest(source), "selection": "byte-identical archival copy"})

    paper = Path("E:/ChatGPT/Temp/project2_l4dc_round13final_d9716c69/project")
    for rel in ("sections/04-upper.tex", "sections/app/C-statistics.tex", "sections/06-experiments.tex", "AGENTS.md"):
        source = paper / rel
        if source.is_file():
            target = ROOT / "provenance/paper_snapshot" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            provenance.append({"target": target.relative_to(ROOT).as_posix(), "source": str(source), "sha256": digest(source), "selection": "read-only theory comparison snapshot; not edited"})
    manifest_source = project / "receipts/grace-storage-20261025/manifest.json"
    retrieval = retrieve_set(json.loads(manifest_source.read_text(encoding="utf-8-sig")))
    writejson(ROOT / "provenance/retrieval_manifest.json", {
        "source": str(manifest_source), "source_sha256": digest(manifest_source),
        "files": retrieval, "count": len(retrieval), "total_bytes": sum(f["size"] for f in retrieval),
    })
    writejson(ROOT / "provenance/extractions.json", provenance)
    state = {}
    for group, description in GROUPS.items():
        required = [f for f in retrieval if f["target"].startswith(group + "/")]
        missing = [f["target"] for f in required if not f["available_and_verified"]]
        state[group] = {"description": description, "status": "READY" if not missing else "AWAITING_GRACE_RESTORE",
                        "missing_verified_files": missing}
    writejson(ROOT / "package_status.json", {
        "new_learning_runs": 0, "new_control_solves": 0,
        "numbers_from_markdown_used_as_data": False, "groups": state,
        "figure_mapping": "proposed only; inspected paper experiments section remains TODO",
    })
    print(json.dumps({"groups": {k: v["status"] for k, v in state.items()},
                      "extracted_rows": {p["target"]: p["rows"] for p in provenance if "rows" in p},
                      "retrieval_files": len(retrieval), "retrieval_bytes": sum(f["size"] for f in retrieval)}, indent=2))


if __name__ == "__main__":
    main()
