"""Reuse existing own-job occupancy and AMS accounting for the equal-mode campaign."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    cfg=read(a.manifest);release=a.manifest.resolve().parents[1];out=Path(cfg['output'])
    dest=out.parents[1]/'accounting'/cfg['experiment'];dest.mkdir(parents=True,exist_ok=True)
    ids=[read(out/'submission-preflight.json')['job']]
    for name in ('submission-pilot.json','submission-formal.json'):
        receipt=read(out/name);ids+=list(receipt['jobs'].values())
        ids+=receipt.get('manual_recovery_jobs',[])
    for path in out.glob('submission-recovery*.json'):
        receipt=read(path);ids+=list(receipt.get('jobs',{}).values())
    ids=list(dict.fromkeys(ids))
    ledger=dest/'own_jobs.psv'
    ledger.write_text(subprocess.check_output(['sacct','-j',','.join(ids),'-n','-P',
        '--format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU,NNodes,TimelimitRaw,MaxRSS'],text=True))
    subprocess.run([sys.executable,'-B',str(release/'scripts/account_rank_sweep100.py'),
        '--input',str(ledger),'--output',str(dest/'occupancy.json'),'--cap','60','--cap-unit','allocated_core_hours'],check=True)
    subprocess.run([sys.executable,'-B',str(release/'scripts/collect_matched_gap_settlement.py'),
        '--account',cfg['resources']['account'],'--start','2026-10-20','--end','2026-10-22',
        '--accounting',str(ledger),'--output',str(dest/'settlement')],check=True)
    occupancy=read(dest/'occupancy.json');settled=read(dest/'settlement/own_settlement_summary.json')
    transitions={}
    for phase in ('pilot','confirm'):
        transitions[phase]=sum(read(out/'raw'/f'ce-r{r:03d}-s{s:04d}.json')['physical_transitions']
                               for r in cfg['ranks'] for s in cfg[phase+'_seeds'])
    transitions['preflight']=read(out/'preflight.json')['diagnostic_primitive_transitions']
    execution=read(out/'report-confirm/execution_cost_audit.json')
    result=dict(status='complete' if settled['all_measured_jobs_settled'] else 'settlement_pending',
        experiment=cfg['experiment'],SU_cap=60,jobs=occupancy['job_records'],states=occupancy['states'],
        allocated_core_hours=occupancy['allocated_core_hours'],maximum_RSS_bytes=occupancy['maximum_recorded_step_RSS_bytes'],
        actual_AMS_settled_rounded_SU=settled['displayed_rounded_settled_SU_sum'],
        all_measured_jobs_settled=settled['all_measured_jobs_settled'],missing_measured_job_ids=settled['missing_measured_job_ids'],
        failed_jobs=occupancy['failed_jobs'],physical_transitions_by_phase=transitions,
        committed_physical_transitions=sum(transitions.values()),
        physical_transitions_lower=execution['campaign_executed_transitions_lower'],
        physical_transitions_upper=execution['campaign_executed_transitions_upper'],
        discarded_sampling_transitions_upper=execution['discarded_sampling_transitions_upper'],
        note='Paired dense/truncated share each physical trajectory. Offline policy auditing adds CPU cost, no learning transitions. '
             'Interrupted uncommitted sampler work is included in the physical-transition interval. Resource failures are retained separately from controller instabilities.')
    assert occupancy['allocated_core_hours']<60 and result['actual_AMS_settled_rounded_SU']<60
    (dest/'cost-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (dest/'balance-after.txt').write_text(subprocess.check_output(['myproject'],text=True))
    for rel in ('scripts/account_rank_sweep100.py','scripts/collect_matched_gap_settlement.py','scripts/collect_ce500_equal_modes_cost.py'):
        target=dest/'sources'/Path(rel).name;target.parent.mkdir(exist_ok=True);shutil.copyfile(release/rel,target)
    manifest={str(f.relative_to(dest)):hashlib.sha256(f.read_bytes()).hexdigest() for f in dest.rglob('*')
              if f.is_file() and f.name!='cost-file-sha256.json'}
    (dest/'cost-file-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
