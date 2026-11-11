"""Publish verified local X11 deliverables after actual visual inspection."""
import hashlib,json,os
from pathlib import Path
R=Path(__file__).resolve().parent;C=R.parents[1];SOURCE=R/'report-v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(C/'CLAUDE_TASK.md')==os.environ['X11_ADVANCE_REVIEW_SHA256']
proof=json.loads((SOURCE/'REPORT_GENERATED.json').read_text());assert proof['status']=='REPORT_GENERATED_VISUAL_QA_PENDING'
for name,digest in proof['files'].items():assert sha(SOURCE/name)==digest
render=json.loads((R/'figures-v3/RENDER_RECEIPT.json').read_text());assert render['status']=='LAYOUT_ONLY_NO_STATS_NO_TRAINING'
for name,digest in render['source_csv_hashes'].items():assert sha(SOURCE/name)==digest
for name,digest in render['files'].items():
    if name=='RENDER_RECEIPT.json':
        assert digest==hashlib.sha256(b'').hexdigest() # writer included its empty self before serialization
    else:assert sha(R/'figures-v3'/name)==digest
assert os.environ['X11_VISUAL_QA']=='BOTH_PNGS_INSPECTED_LEGENDS_AXES_LABELS_NO_OVERLAP'
mapping={'new_X6a_sample_cost_derived.csv':'X6a_sample_cost_derived.csv','merged_X6a_sample_cost_derived.csv':'X6a_sample_cost_derived_merged.csv',
    'stability_by_N.csv':'stability_by_N.csv','paired_gap_ratios_by_N.csv':'paired_gap_ratios_by_N.csv',
    'censoring_flags.csv':'censoring_flags.csv','failures.csv':'failures.csv','legacy_rounding_audit.csv':'legacy_rounding_audit.csv'}
for old,new in mapping.items():
    with (R/new).open('xb') as f:f.write((SOURCE/old).read_bytes())
text=(SOURCE/'REPORT.md').read_text()
text+='\nDescriptive interpretation: fixing n48, the new m4..32 cells increase dense requiredN from10528 to56296 while rank2 stays7340..8225; sample-cost ratios rise1.43..6.89. The reused square48 endpoint has ratio10.13. Fixing m16, n16..96 yields ratios3.61..4.05 (n16 reused). Thus the gain grows strongly with redundant input dimension in this family, and stays approximately constant when only state dimension increases. This is an empirical comparison, not proof of dimension scaling.\n\nFinal figures: figures-v3/sample_cost.png and paired_gap_ratios.png, with SVG versions and saved-CSV-only render receipt. Original report-v2 figures and failed report-v1 remain immutable.\n'
with (R/'REPORT.md').open('x',encoding='utf-8') as f:f.write(text)
qa=dict(status='PASS_ACTUAL_VISUAL_INSPECTION',note=os.environ['X11_VISUAL_QA'],
    selected_figures={name:sha(R/'figures-v3'/name) for name in ['sample_cost.png','paired_gap_ratios.png']},
    earlier_layout_preserved=True,layout_only=True,new_transitions=0,
    original_render_receipt_sha256=sha(R/'figures-v3/RENDER_RECEIPT.json'),
    receipt_self_hash_note='Original rendering receipt accidentally included its empty self; all four actual PNG/SVG hashes and input CSV hashes verified separately. Original receipt retained unchanged.')
with (R/'VISUAL_QA_v1.json').open('x') as f:json.dump(qa,f,indent=2)
done=dict(status='REPORT_COMPLETE',new_paths=352,new_cells=11,reused_cells=2,raw_fit_hash_checks=1760,
    arm_prefix_records=3520,failures=0,formal_transitions=184729600,pilot_transitions=1084416,
    total_new_transitions=185814016,formal_wall_seconds=561.6089999999385,Grace_SU=0,Slurm_job_id=None,
    report_sha256=sha(R/'REPORT.md'),config_sha256=sha(R/'config-v1.json'),visual_qa_sha256=sha(R/'VISUAL_QA_v1.json'),
    precision_reconciliation_sha256=sha(R/'REPORT_CORRECTION_v2.json'),original_files_untouched=True,
    files={new:sha(R/new) for new in mapping.values()},review_sha256=sha(C/'CLAUDE_TASK.md'))
with (R/'REPORT_DONE_v1.json').open('x') as f:json.dump(done,f,indent=2)
with (C/'CODEX_REPLY.md').open('a',encoding='utf-8') as f:
    f.write('\n## X11 REPORT\n\nCompleted352new physical paths/11rectangular cells,184729600formal transitions +1084416disjoint pilot validation transitions;0GraceSU. All1760fit archives hash-verified, all3520new arm-prefix records stable (0failures); per-cell/per-N32denominators in stability_by_N.csv. No old cell rerun. New-only sample-cost CSV plus m column and merged reused square48/16 CSV, paired ratios at everyN, failures/censoring/rounding audit delivered under experiments/x11-20261106/. Rawfits/models/checkpoints remain formal-v1/ onE. Both final PNGs actually inspected: axes/ticks/labels/legends readable, no overlap; figures-v3 layout-only from saved CSVs, SVGs alongside. Full REPORT.md and REPORT_DONE_v1.json.\n\nFixed n48: new m4..32 denseN10528..56296, rank2N7340..8225, sample-cost ratio1.43..6.89; reused square48 ratio10.13. Fixedm16,n16..96: ratios3.61..4.05 (n16reused). Input-dimension growth increases this descriptive benefit; state-dimension-only growth keeps ratio roughly constant. No theorem/scaling verification or epsilon-success-probability claim. Old-paper rounding and failed report-v1 retained/disclosed; source precision correction introduces0new training and preserves all original CSV values. Paper/old results untouched.\nSTATUS: REPORT DONE X11\n')
print(json.dumps({k:v for k,v in done.items() if k!='files'}))
