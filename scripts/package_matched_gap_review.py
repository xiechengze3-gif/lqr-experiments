"""Freeze and verify the small post-archive delivery supplement."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--review',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
    a=p.parse_args();review=a.review.resolve();destination=a.destination.resolve();archive=a.archive.resolve()
    assert review.drive.upper()==destination.drive.upper()==archive.drive.upper()=='E:'
    assert destination.name=='delivery-review' and destination.parent.name=='matched-gap-npg-pi-v2-20261019'
    assert not archive.is_relative_to(review) and not archive.is_relative_to(destination)
    root=Path(__file__).resolve().parents[1];sources=review/'sources';sources.mkdir(exist_ok=True)
    names=['plot_matched_gap_final_review.py','write_matched_gap_findings.py','audit_matched_gap_delivery.py',
        'account_rank_sweep100.py','collect_matched_gap_settlement.py','reconcile_matched_gap_billing.py',
        'verify_extract_matched_gap.py','prepare_matched_gap_npg_recovery.py','matched_gap_npg_pi_report.py',
        'matched_gap_npg_pi.py','package_matched_gap_review.py']
    for name in names:shutil.copy2(root/'scripts'/name,sources/name)
    execution=read(review/'transition_and_execution_audit.json');verification=read(review/'local_archive_verification.json')
    visual=read(review/'visual_review.json');settlement=read(review/'settlement/own_settlement_summary.json')
    ratios=read(review/'reviewed_low_truncated_vs_full_dense.json');billing=read(review/'billing_reconciliation.json')
    assert execution['status']==verification['status']==visual['status']=='PASS'
    assert settlement['all_measured_jobs_settled'] and settlement['matched_own_records']==245
    assert all(q['unchanged_under_discarded_work_bound'] for q in execution['execution_aware_sample_requirement_bounds'])
    assert ratios['invalid_finite_ratio_CI_entries_corrected']==2
    assert billing['actual_displayed_settled_SU_sum']==settlement['displayed_rounded_settled_SU_sum']
    for name,expected in visual['visually_inspected_files'].items():assert sha(Path(name))==expected
    status=dict(status='complete',formal_seeds_per_rank=30,pilot_seeds_per_rank=5,initial_gap=1,
        relative_equals_absolute_targets=[.1,.05],main_comparison='rank2 truncated versus rank100 dense',
        original_archive_sha256=verification['sha256'],original_archive_hashed_files=verification['verified_hashed_files'],
        paired_learning_groups=execution['paired_learning_tasks'],learning_records=execution['learning_records_checked'],
        whole_campaign_physical_transitions_bounds=execution['entire_campaign_physical_transitions_bounds'],
        all40_NPG_PI_sample_thresholds_robust_to_discarded_work=True,
        auxiliary_censored_ratio_CI_entries_corrected=2,
        AMS_displayed_settled_SU=settlement['displayed_rounded_settled_SU_sum'],all245_measured_jobs_settled=True,
        SU_estimate_error_explicitly_recorded=True,new_postprocessing_primitive_transitions=0,new_postprocessing_model_evaluations=0,
        supplementary_sources_include_future_report_censoring_fix=True)
    (review/'delivery_status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
    (review/'README_REVIEW.txt').write_text(
        'Matched initial-gap1 final review supplement.\n'
        'Start with MATCHED_GAP_FINDINGS_ZH.md and all_algorithms_sample_complexity_review.png.\n'
        'The original3.62GB tar is immutable; its SHA and all2131 file hashes passed local verification.\n'
        'CE production data remains in the separate, previously verified ce-matched-initial-gap-20261018 directory.\n'
        'reviewed_low_truncated_vs_full_dense corrects two invalid finite ratio CIs for censored comparators. All original N estimates, seed data and finite comparisons are preserved.\n'
        'execution_cost_success_envelopes.csv additionally includes the bounded discarded collection from two genuine timeout recoveries. Every N90 conclusion is unchanged; one rank8 NPG success count is29..30 rather than exact30 at that execution budget.\n'
        'Billing:216.047222 allocated core-hours is NOT216SU. All245 measured jobs settled to326.99 displayedSU;55 high-memory PI jobs charged2SU per elapsed hour despiteSlurm billing=1. The prior implicit SU conversion was wrong. Read billing_reconciliation.json and raw settlement/.\n'
        'remote-accounting/ and billing-probes/ retain historical query snapshots; each README identifies superseded metadata. The canonical final settlement is settlement/.\n'
        'sources/ includes the actual postprocessing generators and the future report censoring fix; the immutable tar retains the original report source. No simulation or true-system policy evaluation was repeated for this supplement.\n',encoding='utf-8')
    manifest={}
    for f in sorted(review.rglob('*')):
        if not f.is_file() or f.name=='REVIEW_FILE_MANIFEST.json':continue
        assert not f.is_symlink()
        manifest[f.relative_to(review).as_posix()]=dict(bytes=f.stat().st_size,sha256=sha(f))
    mf=review/'REVIEW_FILE_MANIFEST.json';mf.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    destination.mkdir(parents=True,exist_ok=True)
    for name in list(manifest)+['REVIEW_FILE_MANIFEST.json']:
        src=review/name;dst=(destination/name).resolve();assert dst.is_relative_to(destination)
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    for name,q in manifest.items():
        target=destination/name;assert target.stat().st_size==q['bytes'] and sha(target)==q['sha256'],name
    assert sha(mf)==sha(destination/mf.name)
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in list(manifest)+['REVIEW_FILE_MANIFEST.json']:
            z.write(review/name,review.name+'/'+name)
    digest=sha(archive)
    archive.with_name(archive.name+'.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    result=dict(status='PASS',copied_review=str(destination),verified_review_files=len(manifest),
        review_manifest_sha256=sha(mf),supplement_archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_sha256=digest,original_archive_unchanged=True)
    (destination.parent/'local_review_copy_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    archive.with_name(archive.stem+'.receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
