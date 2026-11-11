"""Exact own-job final Slurm occupancy and AMS settlement, outside frozen results."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime,timezone


def read(p):return json.loads(p.read_text())


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    cfg=read(a.manifest);out=Path(cfg['output']);base=out.parent.parent;release=a.manifest.resolve().parents[1]
    dest=base/'accounting'/cfg['experiment']/'final-accounting';dest.mkdir(parents=True,exist_ok=True)
    assert dest.resolve().is_relative_to((base/'accounting'/cfg['experiment']).resolve())
    assert (base/'archives'/cfg['experiment']/'final.json').exists(),'Wait for the final scientific archive'
    pilot=read(out/'pilot_submission.json');formal=read(out/'formal_submission.json')
    ids=[read(out/'preflight.json')['slurm_job_id'],pilot['pilot_array'],pilot['pilot_report'],
         read(out/'common_bundle_submission.json')['common_bundle_job']]
    ids += list(formal['arrays_by_rank'].values())+[formal['formal_report'],formal['identification_audit']]
    ids += [q['job_id'] for q in formal['bundle_jobs']]+[read(out/'final_bundle_submission.json')['final_bundle_job']]
    ids += formal.get('recovery_jobs',[])+formal.get('retired_auxiliary_jobs',[])
    ledger=dest/'own_jobs_final.psv'
    ledger.write_text(subprocess.check_output(['sacct','-j',','.join(ids),'-n','-P',
        '--format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU,NNodes,TimelimitRaw,MaxRSS'],text=True))
    subprocess.run([sys.executable,'-B',str(release/'scripts/account_rank_sweep100.py'),
        '--input',str(ledger),'--output',str(dest/'occupancy.json'),'--cap','60','--cap-unit','allocated_core_hours'],check=True)
    occupancy=read(dest/'occupancy.json');recovery=read(out/'recovery_plan.json')
    cases=[recovery]+recovery.get('additional_cases',[])
    expected=187+formal.get('recovery_attempts',len(formal.get('recovery_jobs',[])))+len(formal.get('retired_auxiliary_jobs',[]))
    assert occupancy['job_records']==expected
    assert {r['job_id_raw'] for r in occupancy['failed_jobs']}=={c['failed_job_id'] for c in cases}
    assert all(r['state']=='TIMEOUT' for r in occupancy['failed_jobs'])
    subprocess.run([sys.executable,'-B',str(release/'scripts/collect_matched_gap_settlement.py'),
        '--account',cfg['resources']['account'],'--start','2026-10-19','--end','2026-10-21',
        '--accounting',str(ledger),'--output',str(dest/'settlement')],check=True)
    settled=read(dest/'settlement/own_settlement_summary.json')
    result=dict(status='complete' if settled['all_measured_jobs_settled'] else 'settlement_pending',
        experiment=cfg['experiment'],collected_UTC=datetime.now(timezone.utc).isoformat(),
        slurm_job_records=occupancy['job_records'],slurm_states=occupancy['states'],
        allocated_core_hours=occupancy['allocated_core_hours'],reported_total_CPU_hours=occupancy['reported_total_cpu_hours'],
        maximum_recorded_step_RSS_bytes=occupancy['maximum_recorded_step_RSS_bytes'],
        AMS_displayed_rounded_settled_SU_sum=settled['displayed_rounded_settled_SU_sum'],
        measured_jobs_settled=settled['matched_own_records'],all_measured_jobs_settled=settled['all_measured_jobs_settled'],
        missing_measured_job_ids=settled['missing_measured_job_ids'],actual_SU_cap=60,
        global_scientific_manifest_sha256=sha(out/'artifact_sha256.json'),
        frozen_final_metadata_archive_sha256=read(base/'archives'/cfg['experiment']/'final.json')['archive_sha256'],
        original_full_audit_retained=True,no_learning_jobs_cancelled_by_agent=True,
        known_resource_timeout_jobs=[c['failed_job_id'] for c in cases],
        recovery_jobs=formal.get('recovery_jobs',[]),retired_zero_runtime_auxiliary_jobs=formal.get('retired_auxiliary_jobs',[]),
        actual_primitive_transition_interval=[read(out/'report-confirm/execution_cost_audit.json')['total_primitive_transitions_lower'],read(out/'report-confirm/execution_cost_audit.json')['total_primitive_transitions_upper']],
        failed_jobs=occupancy['failed_jobs'],account=cfg['resources']['account'],
        note='AMS SUs are displayed rounded per job, distinct from measured allocated core hours. Missing settlement is never zero. Only this campaign exact own IDs were retained; final archive job is included.')
    assert occupancy['allocated_core_hours']<60
    assert result['AMS_displayed_rounded_settled_SU_sum']<60
    (dest/'final_accounting_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    source=dest/'sources';source.mkdir(exist_ok=True)
    for path in [Path(__file__),release/'scripts/account_rank_sweep100.py',release/'scripts/collect_matched_gap_settlement.py']:
        shutil.copyfile(path,source/path.name)
    files={str(f.relative_to(dest)):sha(f) for f in sorted(dest.rglob('*')) if f.is_file() and f.name!='cost_file_sha256.json'}
    (dest/'cost_file_sha256.json').write_text(json.dumps(files,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
