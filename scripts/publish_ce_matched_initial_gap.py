"""Publish the completed CE review bundle after actual visual inspection."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def write(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace-review',action='store_true');args=parser.parse_args()
    cfg=read(ROOT/'configs/ce_matched_initial_gap_20261018.json');out=Path(cfg['local_output'])
    original_out=out
    if args.workspace_review:
        # Keep all archived numerical results in their existing E: result directory.
        # Only the supplemental review is copied into the explicitly writable workspace.
        out=ROOT/'analysis'/cfg['experiment'];out.mkdir(parents=True,exist_ok=True)
        assert out.resolve().is_relative_to((ROOT/'analysis').resolve())
        for folder in ('report-pilot','report-confirm','documentation','compute_accounting'):
            shutil.copytree(original_out/folder,out/folder,dirs_exist_ok=True)
        for name in ('delivery_receipt.json','verification.json','preflight.json','resolved_config.json',
                     'campaign_transition_accounting.json','confirmation_guard.json',
                     'confirmation_submission.json','pilot_submission.json','execution_provenance.json'):
            shutil.copyfile(original_out/name,out/name)
        shutil.copytree(original_out/'frozen/release',out/'frozen/release',dirs_exist_ok=True)
        shutil.copytree(ROOT/'analysis/ce-matched-initial-gap-reviewed-figures',out/'reviewed_figures',dirs_exist_ok=True)
        shutil.copyfile(ROOT/'receipts/ce-matched-initial-gap-visual-review.json',out/'visual_review.json')
        shutil.copyfile(ROOT/'docs/CE_MATCHED_INITIAL_GAP_FINDINGS_20261018.md',out/'documentation/CE_MATCHED_INITIAL_GAP_FINDINGS_20261018.md')
    receipt=read(ROOT/'receipts/ce-matched-initial-gap-20261018.json')
    delivery=read(out/'delivery_receipt.json');qa=read(out/'visual_review.json')
    if not (out/'retrieval_receipt.json').exists():write(out/'retrieval_receipt.json',delivery)
    assert qa['status']=='PASS' and len(qa['reviewed_figures'])==4
    for q in qa['reviewed_figures']:assert sha(out/q['path'])==q['sha256']
    assert delivery['archive']['verified'] and delivery['cost']['allocated_core_hours']<=8
    for phase,n in [('pilot',25),('confirm',150)]:
        s=read(out/f'report-{phase}/summary.json')
        assert s['status']=='complete' and s['audit']['paired_tasks']==n
    review_source=out/'review_source';review_source.mkdir(exist_ok=True)
    names=['ce_matched_initial_gap.py','ce_matched_initial_gap_report.py',
        'finalize_ce_matched_initial_gap.py','publish_ce_matched_initial_gap.py',
        'Prepare-CEMatchedInitialGap.ps1','Finalize-CEMatchedInitialGap.ps1',
        'Publish-CEMatchedInitialGap.ps1',
        'submit_ce_matched_initial_gap_pilot.sh','submit_ce_matched_initial_gap_confirm.sh',
        'account_rank_sweep100.py','plot_ce_matched_initial_gap_review.py']
    for name in names:shutil.copyfile(ROOT/'scripts'/name,review_source/name)
    shutil.copyfile(ROOT/'slurm/ce_matched_initial_gap_archive.sbatch',review_source/'archive.sbatch')
    issues=ROOT/'receipts/ce-matched-initial-gap-run-issues.json'
    if issues.exists():shutil.copyfile(issues,out/'run_issues.json')
    completion=dict(status='complete_audited_visually_verified',completed_utc=datetime.now(timezone.utc).isoformat(),
        original_result_directory=str(original_out),local_review_directory=str(out),
        supplemental_review_in_authorized_workspace=args.workspace_review,
        formal_seeds=30,pilot_seeds=5,ranks=cfg['ranks'],common_initial_gap=1.,relative_targets=cfg['relative_targets'],
        original_archive=delivery['archive'],original_artifact_hashes_verified=delivery['original_artifact_hashes_verified'],
        formal_policy_audit=read(out/'report-confirm/audit.json'),cost=delivery['cost'],transitions=delivery['transitions'],
        maximum_initial_gap_error=max(abs(q['initial_gap']-1) for q in read(out/'verification.json')['systems']),
        full_rank_paired_budget_checks=675,new_learning_transitions_during_local_reanalysis=0,
        interpretation='Compare low-rank truncated versus full-rank dense at matched gap and target; one physical system, rank-dependent exploration states.')
    write(out/'completion.json',completion)
    (out/'README.txt').write_text(
        'CE matched-initial-gap experiment COMPLETE.\n'
        'Common initial gap=1. Relative target0.1/0.05 equals absolute target0.1/0.05.\n'
        'Start: documentation/CE_MATCHED_INITIAL_GAP_FINDINGS_20261018.md\n'
        'Primary comparison: report-confirm/low_rank_vs_full_rank.csv\n'
        'Full threshold table: report-confirm/sample_complexity.csv\n'
        'Curve data: report-confirm/fixed_budget_gaps.csv and success_by_budget.csv\n'
        'Frozen scientific sources/inputs: frozen/release/\n'
        'Original raw results/policies/checkpoints/final OLS estimates: '+str(original_out)+'\n'
        'Actual allocated core-hours: compute_accounting/; primitive counts: campaign_transition_accounting.json\n'
        'The original TAR.GZ is unchanged. The review ZIP adds local findings, visual QA and final accounting.\n',encoding='utf-8')
    folders=['report-pilot','report-confirm','documentation','compute_accounting','review_source','reviewed_figures','frozen/release']
    top=['completion.json','README.txt','verification.json','preflight.json','resolved_config.json',
        'campaign_transition_accounting.json','visual_review.json','retrieval_receipt.json',
        'confirmation_guard.json','confirmation_submission.json','pilot_submission.json','execution_provenance.json']
    if (out/'run_issues.json').exists():top.append('run_issues.json')
    paths=[p for folder in folders for p in (out/folder).rglob('*') if p.is_file()]+[out/p for p in top]
    hashes={p.relative_to(out).as_posix():sha(p) for p in paths}
    write(out/'local_review_sha256.json',hashes);paths.append(out/'local_review_sha256.json')
    bundle=out.parent/(out.name+'-review.zip')
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths:z.write(p,'review/'+p.relative_to(out).as_posix())
    with zipfile.ZipFile(bundle) as z:assert z.testzip() is None
    delivery.update(state='complete',review_archive=dict(path=str(bundle),bytes=bundle.stat().st_size,sha256=sha(bundle),zip_CRC_verified=True))
    # delivery_receipt was bundled as the original retrieval record. This final
    # receipt additionally records the companion hash, outside the companion.
    write(out/'delivery_receipt.json',delivery)
    receipt.update(state=completion['status'],all_required_work_complete=True,next_steps=[],delivery=delivery,
                   completion_path=str(out/'completion.json'),local_review_directory=str(out),completed_utc=completion['completed_utc'])
    write(ROOT/'receipts/ce-matched-initial-gap-20261018.json',receipt)
    print(json.dumps(dict(status=completion['status'],output=str(out),review_archive=delivery['review_archive']),ensure_ascii=False))


if __name__=='__main__':main()
