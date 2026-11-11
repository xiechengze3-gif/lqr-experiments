"""Package completed, independently audited rank-sweep artifacts on E:."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from datetime import datetime, timezone
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();out=a.output.resolve()
    assert str(out).lower().startswith('e:\\chatgpt\\results\\lqr_experiments\\')
    audit=read(out/'audit.json');assert audit['status']=='PASS' and audit['source_tasks']==350
    assert audit['stable_policies_checked']==19600 and audit['unstable_policies_checked']==0
    assert audit['full_rank_paired_task_checks']==70 and audit['first_estimate_pairing_checks']==175
    summary=read(out/'report-confirm/summary.json');assert summary['status']=='complete' and summary['completed_tasks']==300
    qa=read(out/'visual_review.json');assert qa['status']=='PASS' and len(qa['reviewed_figures'])==6
    for row in qa['reviewed_figures']:assert sha(out/row['path'])==row['sha256']
    assert read(out/'endpoint_oracle_diagnostic.json')['status']=='PASS'
    costs=read(ROOT/'receipts/rank-sweep100-compute-accounting.json')
    assert costs['allocated_core_hours']<costs['compute_cap_SU']
    transition_counts=read(out/'campaign_transition_accounting.json')
    receipt=read(ROOT/'receipts/rank-sweep100-20261016.json')
    archive=receipt['archive'];assert archive['verified'] and Path(archive['path']).stat().st_size==archive['bytes']
    for relative in ('reporting_source','documentation','configs','compute_accounting'):
        (out/relative).mkdir(exist_ok=True)
    for name in ('RANK_SWEEP100_FINDINGS_20261017.md','RANK_SWEEP100_PROTOCOL_20261016.md'):
        shutil.copyfile(ROOT/'docs'/name,out/'documentation'/name)
    for source in (ROOT/'configs').glob('rank_sweep100*20261016.json'):
        shutil.copyfile(source,out/'configs'/source.name)
    for name in ('rank_sweep100_report.py','finalize_rank_sweep100.py','rank_sweep100_endpoint_oracle.py',
                 'account_rank_sweep100.py','publish_rank_sweep100_results.py','test_rank_sweep100_resume.py',
                 'rank_sweep100_migrate.py','fix_rank_sweep100_provenance.py',
                 'rank_sweep100_checkpoint_progress.py','record_rank_sweep100_environment.py',
                 'Finalize-RankSweep100.ps1','Retrieve-RankSweep100.ps1','Invoke-RankSweep100.ps1'):
        shutil.copyfile(ROOT/'scripts'/name,out/'reporting_source'/name)
    write(out/'reporting_source/hashes.json',{p.name:sha(p) for p in (out/'reporting_source').iterdir() if p.name!='hashes.json'})
    for pattern in ('rank-sweep100-compute-accounting.*','rank-sweep100-own-jobs*.psv','rank-sweep100-time-padding*'):
        for source in (ROOT/'receipts').glob(pattern):
            shutil.copyfile(source,out/'compute_accounting'/source.name)
    shutil.copyfile(ROOT/'receipts/rank-sweep100-run-issues.json',out/'run_issues.json')
    generated=datetime.now(timezone.utc).isoformat()
    completion=dict(status='complete_independently_audited_visually_verified',completed_utc=generated,
        local_result_directory=str(out),formal_seeds=30,pilot_seeds=5,ranks=summary['ranks'],
        epsilon=summary['epsilon'],formal_paired_groups=300,total_paired_groups_including_pilot=350,
        stable_saved_policy_checkpoints=19600,full_rank_paired_checks=70,
        new_learning_samples_during_local_reanalysis=0,infrastructure_sampling_restarts=0,
        allocated_core_hours=costs['allocated_core_hours'],reported_total_cpu_hours=costs['reported_total_cpu_hours'],
        budget_cap_SU=costs['compute_cap_SU'],cost_note=costs['note'],
        campaign_transitions=transition_counts,original_remote_archive=archive,
        audit_sha256=sha(out/'audit.json'),visual_review_sha256=sha(out/'visual_review.json'),
        final_configuration='configs/rank_sweep100_confirm_20261016.json',
        findings='documentation/RANK_SWEEP100_FINDINGS_20261017.md',
        original_local_exploratory_pilot=str(out.parent/'rank-sweep100-pilot-20261016'),
        note='Original remote archive remains unchanged. The companion ZIP carries local audit/statistics/plots/docs and the complete local exploratory pilot. Neither archive is needed to browse the extracted E: result directories.')
    write(out/'completion.json',completion)
    (out/'README.txt').write_text(
        '100d LQR rank sweep: COMPLETE\n'
        '30 fresh paired seeds per cell; pilot seeds are separate.\n'
        'Start: documentation/RANK_SWEEP100_FINDINGS_20261017.md\n'
        'Main numeric table: report-confirm/summary_table.csv\n'
        'Thresholds, Wilson CIs and censoring: report-confirm/sample_complexity.csv\n'
        'All measured success curves: report-confirm/success_by_budget.csv\n'
        'Numerical audit: audit.json; plot review: visual_review.json\n'
        'Physical vs per-algorithm transition counts: campaign_transition_accounting.json\n'
        'Compute occupancy and original Slurm counters: compute_accounting/\n'
        'Raw data/policies/checkpoints/frozen learner: raw/, policies/, checkpoints/, frozen/\n'
        'The companion ZIP supplements the unchanged remote TAR.GZ; details: completion.json\n',encoding='utf-8')
    folders=('report-pilot','report-confirm','reporting_source','documentation','configs','compute_accounting','diagnostics')
    top_files=('audit.json','visual_review.json','completion.json','campaign_transition_accounting.json',
        'local_reanalysis_environment.json','endpoint_oracle_diagnostic.json','run_issues.json',
        'local_finalization.log','endpoint_oracle.log','README.txt')
    paths=[p for folder in folders for p in (out/folder).rglob('*') if p.is_file()]
    paths += [out/name for name in top_files]
    derived={p.relative_to(out).as_posix():sha(p) for p in sorted(paths)}
    write(out/'derived_reports_sha256.json',derived)
    paths.append(out/'derived_reports_sha256.json')
    zip_path=out.parent/(out.name+'-local-review.zip');temporary=zip_path.with_suffix('.zip.partial')
    pilot=out.parent/'rank-sweep100-pilot-20261016'
    pilot_files=sorted(p for p in pilot.rglob('*') if p.is_file())
    pilot_hashes={p.relative_to(pilot).as_posix():sha(p) for p in pilot_files}
    write(out/'exploratory_pilot_sha256.json',pilot_hashes);paths.append(out/'exploratory_pilot_sha256.json')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as bundle:
        for path,relative in [(p,'local-review/'+p.relative_to(out).as_posix()) for p in paths]+[(p,'exploratory-pilot-v1/'+p.relative_to(pilot).as_posix()) for p in pilot_files]:
            bundle.write(path,relative,compress_type=zipfile.ZIP_STORED if path.suffix.lower() in ('.npz','.png') else zipfile.ZIP_DEFLATED)
    os.replace(temporary,zip_path)
    with zipfile.ZipFile(zip_path) as bundle:assert bundle.testzip() is None
    delivery=dict(status='complete',original_remote_archive=archive,
                  local_companion_archive=dict(path=str(zip_path),bytes=zip_path.stat().st_size,sha256=sha(zip_path),zip_CRC_verified=True),
                  original_archive_SHA256_verified=True,derived_file_hashes=len(derived),
                  exploratory_pilot_files=len(pilot_files),completed_utc=generated)
    write(out/'delivery_receipt.json',delivery)
    receipt['earlier_40_update_plan']={key:receipt.pop(key) for key in ('final_configuration','final_max_transitions_per_algorithm','estimated_final_total_SU','final_submission') if key in receipt}
    receipt.update(state=completion['status'],completed_utc=generated,final_configuration=receipt['confirmation_configuration'],
        final_max_transitions_per_algorithm=245902512,actual_compute=costs,audit=read(out/'audit.json'),
        visual_review=qa,campaign_transitions=transition_counts,delivery=delivery,
        latest_checkpoint_snapshot=dict(phase='confirm',pairs=150,min_stage=44,max_stage=44,
                                        min_transitions=245902512,max_transitions=245902512))
    if 'held_unstarted_npg_array' in receipt:receipt['retired_unstarted_npg_array']=receipt.pop('held_unstarted_npg_array')
    write(ROOT/'receipts/rank-sweep100-20261016.json',receipt)
    continuation=read(ROOT/'receipts/rank-sweep100-continue-state.json')
    continuation.update(state='complete',completed_utc=generated,remaining=[],continuation_required=False,
                        completion_receipt=str(out/'completion.json'),delivery_receipt=str(out/'delivery_receipt.json'))
    write(ROOT/'receipts/rank-sweep100-continue-state.json',continuation)
    print(json.dumps(delivery,indent=2),flush=True)


if __name__=='__main__':main()
