"""Package completed PI results and verified reuse of the earlier NPG/CE reports."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import zipfile

from publish_rank_sweep100_results import read, write, sha

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();out=a.output.resolve()
    assert str(out).lower().startswith('e:\\chatgpt\\results\\lqr_experiments\\')
    cfg=read(out/'resolved_config.json');audit=read(out/'audit.json')
    assert audit['status']=='PASS' and audit['source_tasks']==175
    assert audit['full_rank_paired_task_checks']==35 and audit['first_estimate_pairing_checks']==175
    for phase,expected in (('pilot',25),('confirm',150)):
        d=read(out/f'report-{phase}/summary.json')
        assert d['status']=='complete' and d['completed_tasks']==expected
    summary=read(out/'report-confirm/summary.json')
    qa=read(out/'visual_review.json')
    assert qa['status']=='PASS' and len(qa['reviewed_figures'])==8
    for row in qa['reviewed_figures']:assert sha(out/row['path'])==row['sha256']
    assert read(out/'verification.json')['status']=='PASS'
    assert read(out/'maximum_memory_verification.json')['status']=='PASS'
    assert read(out/'oracle.json')['status']=='PASS'
    assert read(out/'report-confirm/baseline_reuse.json')['original_derived_hashes_verified']
    costs=read(ROOT/'receipts/rank-sweep100-pi-compute-accounting.json')
    plan=read(out/'resource_plan.json')
    assert costs['compute_cap_SU']==plan['planning_cap_core_hours']
    assert costs['allocated_core_hours']<=plan['planning_cap_core_hours']
    counts=read(out/'campaign_transition_accounting.json')
    provenance=read(out/'execution_provenance.json')
    assert provenance['status']=='PASS' and provenance['saved_paired_groups']==175
    receipt=read(ROOT/'receipts/rank-sweep100-pi-20261017.json');archive=receipt['archive']
    assert archive['verified'] and Path(archive['path']).stat().st_size==archive['bytes']
    baseline=Path(receipt['baseline_result'])
    baseline_receipt=read(baseline/'delivery_receipt.json')
    for name in ('reporting_source','documentation','configs','compute_accounting','baseline_reports'):
        (out/name).mkdir(exist_ok=True)
    for name in ('RANK_SWEEP100_PI_FINDINGS_20261018.md','RANK_SWEEP100_PI_PROTOCOL_20261017.md',
                 'RANK_SWEEP100_FINDINGS_20261017.md'):
        shutil.copyfile(ROOT/'docs'/name,out/'documentation'/name)
    for source in (ROOT/'configs').glob('rank_sweep100_pi*20261017.json'):
        shutil.copyfile(source,out/'configs'/source.name)
    shutil.copyfile(ROOT/'configs/rank_sweep100_pi_resources_20261018.json',
                    out/'configs/rank_sweep100_pi_resources_20261018.json')
    for name in ('rank_sweep100_pi_report.py','rank_sweep100_pi_audit.py',
                 'rank_sweep100_pi_transition_accounting.py','rank_sweep100_pi_status.py',
                 'rank_sweep100_pi_execution_provenance.py',
                 'rank_sweep100_pi_progress.py',
                 'write_rank_sweep100_pi_findings.py',
                 'record_rank_sweep100_pi_local_environment.py',
                 'record_rank_sweep100_pi_remote_environment.py',
                 'review_rank_sweep100_pi_pilot.py',
                 'rank_sweep100_pi_submit_guard.py','publish_rank_sweep100_pi_results.py',
                 'publish_rank_sweep100_results.py','rank_sweep100_report.py','account_rank_sweep100.py',
                 'Analyze-RankSweep100PI.ps1','Fetch-RankSweep100PIPilot.ps1','Retrieve-RankSweep100PI.ps1',
                 'Finalize-RankSweep100PI.ps1',
                 'Prepare-RankSweep100PI.ps1','submit_rank_sweep100_pi_confirm.sh'):
        shutil.copyfile(ROOT/'scripts'/name,out/'reporting_source'/name)
    shutil.copyfile(ROOT/'scripts/resume_rank_sweep100_pi_pilot.sh',out/'reporting_source/resume_pilot.sh')
    shutil.copyfile(ROOT/'scripts/resume_rank_sweep100_pi_pilot_final.sh',out/'reporting_source/resume_pilot_final.sh')
    shutil.copyfile(ROOT/'slurm/rank_sweep100_pi_archive.sbatch',out/'reporting_source/archive.sbatch')
    shutil.copyfile(ROOT/'slurm/rank_sweep100_pi_bundle.sbatch',out/'reporting_source/formal_bundle.sbatch')
    write(out/'reporting_source/hashes.json',
          {p.name:sha(p) for p in (out/'reporting_source').iterdir() if p.name!='hashes.json'})
    for pattern in ('rank-sweep100-pi-compute-accounting.*','rank-sweep100-pi-own-jobs*.psv'):
        for source in (ROOT/'receipts').glob(pattern):
            shutil.copyfile(source,out/'compute_accounting'/source.name)
    shutil.copyfile(ROOT/'receipts/rank-sweep100-pi-run-issues.json',out/'run_issues.json')
    shutil.copyfile(ROOT/'receipts/rank-sweep100-pi-pilot-review.json',out/'pilot_review.json')
    baseline_hashes=read(baseline/'derived_reports_sha256.json')
    reused={}
    for phase in ('pilot','confirm'):
        dest=out/'baseline_reports'/f'report-{phase}';dest.mkdir(exist_ok=True)
        for name in ('summary.json','sample_complexity.csv','success_by_budget.csv','systems_and_oracle.csv'):
            source=baseline/f'report-{phase}'/name;relative=source.relative_to(baseline).as_posix()
            assert sha(source)==baseline_hashes[relative]
            shutil.copyfile(source,dest/name);reused[relative]=sha(source)
    for name in ('audit.json','completion.json','delivery_receipt.json','visual_review.json'):
        shutil.copyfile(baseline/name,out/'baseline_reports'/name)
    write(out/'baseline_reports/reuse_provenance.json',dict(original_directory=str(baseline),
        reused_files_sha256=reused,original_delivery=baseline_receipt,no_historical_learning_repeated=True))
    generated=datetime.now(timezone.utc).isoformat()
    completion=dict(status='complete_independently_audited_visually_verified',completed_utc=generated,
        local_result_directory=str(out),formal_seeds=30,pilot_seeds=5,ranks=cfg['ranks'],
        epsilon=cfg['epsilon'],sensitivity_epsilon=cfg['epsilon']/2,
        total_PI_paired_groups=175,formal_PI_paired_groups=150,pilot_PI_paired_groups=25,
        policy_checkpoints_checked=audit['policy_checkpoints_checked'],
        critic_updates_replayed=audit['critic_updates_replayed'],
        full_rank_paired_task_checks=audit['full_rank_paired_task_checks'],
        first_estimate_pairing_checks=audit['first_estimate_pairing_checks'],
        budget_schedule=cfg['batch_schedule'],max_transitions_per_algorithm=3474432,
        learner='Full original-coordinate quadratic average-cost LSTD PI; no whitening',
        allocated_core_hours=costs['allocated_core_hours'],
        elapsed_billing_unit_hours=costs['elapsed_billing_unit_hours'],
        reported_total_cpu_hours=costs['reported_total_cpu_hours'],
        budget_cap_core_hours=plan['planning_cap_core_hours'],initial_planning_cap_core_hours=125,
        operational_resource_plan=plan,
        execution_provenance=provenance,
        cost_note=costs['note'],campaign_transitions=counts,original_remote_archive=archive,
        baseline_directory=str(baseline),historical_NPG_CE_reruns=0,
        audit_sha256=sha(out/'audit.json'),visual_review_sha256=sha(out/'visual_review.json'),
        final_configuration='configs/rank_sweep100_pi_20261017.json',
        findings='documentation/RANK_SWEEP100_PI_FINDINGS_20261018.md',
        new_learning_transitions_during_local_reanalysis=0,
        note='The unchanged remote TAR.GZ contains raw critics, policies, checkpoints, logs and frozen learner/system inputs. The companion ZIP contains the independent local audit, all joined tables/figures, reporting source, findings, accounting and verified historical NPG/CE summary inputs. Inspect run_issues.json for every retained infrastructure/diagnostic failure.')
    write(out/'completion.json',completion)
    (out/'README.txt').write_text(
        '100d LQR rank sweep: full LSTD PI supplement COMPLETE\n'
        '30 fresh seeds per rank/method, plus a separate five-seed pilot.\n'
        'Start: documentation/RANK_SWEEP100_PI_FINDINGS_20261018.md\n'
        'Six-method table: report-confirm/all_algorithms_summary_table.csv\n'
        'All thresholds/CIs/censoring: report-confirm/all_algorithms_sample_complexity.csv\n'
        'All success curves: report-confirm/all_algorithms_success_by_budget.csv\n'
        'Policy/critic replay audit: audit.json; plot review: visual_review.json\n'
        'Samples: campaign_transition_accounting.json; measured resources: compute_accounting/\n'
        'Original numerical files: raw/, policies/, critics/, checkpoints/\n'
        'Frozen learner and exact system inputs: ../source/'+out.name+'/\n'
        'Verified reused NPG/CE summaries: baseline_reports/\n'
        'Original remote archive and supplemental review ZIP: completion.json/delivery_receipt.json\n',encoding='utf-8')
    folders=('report-pilot','report-confirm','reporting_source','documentation','configs',
             'compute_accounting','baseline_reports','progress')
    top=('audit.json','visual_review.json','completion.json','campaign_transition_accounting.json',
         'local_reanalysis_environment.json','run_issues.json','pilot_review.json','README.txt',
         'resolved_config.json','verification.json','maximum_memory_verification.json','oracle.json',
         'archive_coverage.json','preconfirmation_guard.json','confirmation_submission.json',
         'runtime_dependency_metadata.json',
         'resource_plan.json','pilot_resume_guard.json','pilot_resume_submission.json',
         'pilot_final_resume_guard.json','pilot_final_resume_submission.json',
         'formal_sources.sha256',
         'execution_provenance.json','execution_provenance_by_pair.csv',
         'independent_audit.log','report-pilot.log','report-confirm.log')
    paths=[p for folder in folders for p in (out/folder).rglob('*') if p.is_file()]
    paths.extend(out/name for name in top)
    derived={p.relative_to(out).as_posix():sha(p) for p in sorted(paths)}
    write(out/'derived_reports_sha256.json',derived);paths.append(out/'derived_reports_sha256.json')
    zip_path=out.parent/(out.name+'-local-review.zip');temporary=zip_path.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as bundle:
        for path in paths:
            bundle.write(path,'local-review/'+path.relative_to(out).as_posix(),
                compress_type=zipfile.ZIP_STORED if path.suffix.lower() in ('.npz','.png') else zipfile.ZIP_DEFLATED)
    os.replace(temporary,zip_path)
    with zipfile.ZipFile(zip_path) as bundle:assert bundle.testzip() is None
    delivery=dict(status='complete',original_remote_archive=archive,
        local_companion_archive=dict(path=str(zip_path),bytes=zip_path.stat().st_size,
            sha256=sha(zip_path),zip_CRC_verified=True),
        original_archive_SHA256_verified=True,derived_file_hashes=len(derived),completed_utc=generated)
    write(out/'delivery_receipt.json',delivery)
    receipt.update(state=completion['status'],completed_utc=generated,formal_seeds_started=True,
        next_steps=[],all_required_work_complete=True,
        actual_compute=costs,audit=audit,visual_review=qa,campaign_transitions=counts,delivery=delivery)
    write(ROOT/'receipts/rank-sweep100-pi-20261017.json',receipt)
    continuation=read(ROOT/'receipts/rank-sweep100-pi-continue-state.json')
    continuation.update(state='complete',remaining=[],continuation_required=False,
        completed_utc=generated,completion_receipt=str(out/'completion.json'),
        delivery_receipt=str(out/'delivery_receipt.json'))
    write(ROOT/'receipts/rank-sweep100-pi-continue-state.json',continuation)
    print(delivery,flush=True)


if __name__=='__main__':main()
