"""Verify the external final settlement without modifying frozen scientific data."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--bundles',type=Path,required=True)
    a=p.parse_args();costdir=a.bundles/'final-accounting';files=read(costdir/'cost_file_sha256.json')
    for rel,digest in files.items():
        parts=PurePosixPath(rel);assert not parts.is_absolute() and '..' not in parts.parts
        assert sha(costdir/rel)==digest,rel
    cost=read(costdir/'final_accounting_summary.json')
    assert cost['status']=='complete' and cost['all_measured_jobs_settled'] and not cost['missing_measured_job_ids']
    assert cost['slurm_job_records']==194 and cost['slurm_states']==dict(COMPLETED=187,TIMEOUT=3,CANCELLED=4)
    assert cost['measured_jobs_settled']>=190
    assert set(cost['known_resource_timeout_jobs'])=={'20205483','20205931','20205934'}
    assert len(cost['retired_zero_runtime_auxiliary_jobs'])==4
    assert cost['global_scientific_manifest_sha256']==sha(a.output/'artifact_sha256.json')
    assert cost['frozen_final_metadata_archive_sha256']==read(a.bundles/'final.json')['archive_sha256']
    assert cost['actual_primitive_transition_interval']==[183869952,184656384]
    assert 0<cost['AMS_displayed_rounded_settled_SU_sum']<60 and cost['allocated_core_hours']<60
    result=dict(status='PASS',verified_cost_files=len(files),
        AMS_displayed_rounded_settled_SU=cost['AMS_displayed_rounded_settled_SU_sum'],
        allocated_core_hours=cost['allocated_core_hours'],own_job_records=194,
        all190_nonzero_jobs_settled=True,known_timeouts_retained=3,zero_runtime_cancelled_records_retained=4,
        scientific_manifest_sha256=cost['global_scientific_manifest_sha256'],source_sha256=sha(Path(__file__)))
    (a.bundles/'cost-local-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
