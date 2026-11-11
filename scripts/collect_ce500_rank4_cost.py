"""Exact own-job Slurm and actual AMS cost for the rank-4 extension."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    cfg=json.loads(a.manifest.read_text());out=Path(cfg['output']);release=a.manifest.resolve().parents[1]
    dest=out.parent.parent/'accounting'/cfg['experiment'];dest.mkdir(parents=True,exist_ok=True)
    first=json.loads((out/'submission-initial.json').read_text());formal=json.loads((out/'submission-formal.json').read_text())
    ids=list(first['jobs'].values())+list(formal['jobs'].values())
    ids+=formal.get('manual_recovery_jobs',[])
    ids+=formal.get('auxiliary_transfer_jobs',[])
    ledger=dest/'own_jobs.psv';ledger.write_text(subprocess.check_output(['sacct','-j',','.join(ids),'-n','-P',
        '--format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU,NNodes,TimelimitRaw,MaxRSS'],text=True))
    subprocess.run([sys.executable,'-B',str(release/'scripts/account_rank_sweep100.py'),'--input',str(ledger),
        '--output',str(dest/'occupancy.json'),'--cap','20','--cap-unit','allocated_core_hours'],check=True)
    subprocess.run([sys.executable,'-B',str(release/'scripts/collect_matched_gap_settlement.py'),
        '--account',cfg['resources']['account'],'--start','2026-10-20','--end','2026-10-22',
        '--accounting',str(ledger),'--output',str(dest/'settlement')],check=True)
    occupancy=json.loads((dest/'occupancy.json').read_text());settlement=json.loads((dest/'settlement/own_settlement_summary.json').read_text())
    result=dict(status='complete' if settlement['all_measured_jobs_settled'] else 'settlement_pending',
        experiment=cfg['experiment'],SU_cap=20,states=occupancy['states'],jobs=occupancy['job_records'],
        allocated_core_hours=occupancy['allocated_core_hours'],maximum_RSS_bytes=occupancy['maximum_recorded_step_RSS_bytes'],
        actual_AMS_settled_rounded_SU=settlement['displayed_rounded_settled_SU_sum'],
        all_measured_jobs_settled=settlement['all_measured_jobs_settled'],
        missing_measured_job_ids=settlement['missing_measured_job_ids'],failed_jobs=occupancy['failed_jobs'])
    assert occupancy['allocated_core_hours']<20 and result['actual_AMS_settled_rounded_SU']<20
    (dest/'cost-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    manifest={str(f.relative_to(dest)):hashlib.sha256(f.read_bytes()).hexdigest() for f in dest.rglob('*')
        if f.is_file() and f.name!='cost-file-sha256.json'}
    (dest/'cost-file-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
