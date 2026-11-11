"""Own-job occupancy/AMS reconciliation; no simulation or policy evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def read(path):return json.loads(path.read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    args=p.parse_args();cfg=read(args.manifest);out=Path(cfg['output'])
    dest=out.parents[1]/'accounting'/cfg['experiment'];dest.mkdir(parents=True,exist_ok=True)
    ids=[read(out/'submission-preflight.json')['job']]
    for name in ('submission-pilot.json','submission-pilot-fixed.json','submission-formal.json','submission-finalize.json','submission-finish.json'):
        path=out/name
        if path.exists():ids+=list(read(path).get('jobs',{}).values())
    for path in out.glob('submission-recovery*.json'):
        ids+=list(read(path).get('jobs',{}).values())
    ids=list(dict.fromkeys(ids));ledger=dest/'own_jobs.psv'
    ledger.write_text(subprocess.check_output(['sacct','-j',','.join(ids),'-n','-P',
        '--format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU,NNodes,TimelimitRaw,MaxRSS'],text=True))
    root=Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable,'-B',str(root/'scripts/account_rank_sweep100.py'),
        '--input',str(ledger),'--output',str(dest/'occupancy.json'),
        '--cap','60','--cap-unit','allocated_core_hours'],check=True)
    occupancy=read(dest/'occupancy.json')
    assert occupancy['allocated_core_hours']<60 and occupancy['elapsed_billing_unit_hours']<60
    wanted={q.split('|')[0] for q in ledger.read_text().splitlines()
            if q and '.' not in q.split('|')[1] and int(q.split('|')[4] or 0)>0
            and int(q.split('|')[5] or 0)>0}
    text=subprocess.check_output(['myproject','-j',cfg['resources']['account']],text=True)
    matches=[]
    for line in text.splitlines():
        c=[q.strip() for q in line.split('|')]
        if len(c)>9 and c[1]==cfg['resources']['account'] and c[2] in wanted:
            matches.append(dict(job=c[2],array_index=c[3],wall_seconds=int(c[7]),
                                slots=int(c[8]),SU=float(c[9])))
    missing=sorted(wanted-{q['job'] for q in matches})
    phases={phase:sum(read(out/'raw'/f'ce-r{r:03d}-s{s:04d}.json')['physical_transitions']
                     for r in cfg['ranks'] for s in cfg[phase+'_seeds']) for phase in ('pilot','confirm')}
    phases['preflight']=read(out/'preflight.json')['diagnostic_primitive_transitions']
    assert read(out/'launcher_failure_audit.json')['physical_learning_transitions']==0
    result=dict(status='complete' if not missing else 'settlement_pending',experiment=cfg['experiment'],
        SU_cap=60,job_ids=ids,states=occupancy['states'],allocated_core_hours=occupancy['allocated_core_hours'],
        elapsed_billing_unit_hours=occupancy['elapsed_billing_unit_hours'],
        actual_AMS_settled_rounded_SU=sum(q['SU'] for q in matches),
        all_measured_jobs_settled=not missing,unsettled_own_job_ids=missing,
        maximum_RSS_bytes=occupancy['maximum_recorded_step_RSS_bytes'],
        physical_transitions_by_phase=phases,committed_physical_transitions=sum(phases.values()),
        failed_job_records=occupancy['failed_jobs'],settled_own_records=matches,
        note='Slurm occupancy is measured; missing AMS charges remain pending. Paired methods share each physical trajectory. Launcher failures produced zero transitions. Any science interruption needs its separately saved recovery/lost-work audit.')
    (dest/'cost-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (dest/'balance-after.txt').write_text(subprocess.check_output(['myproject'],text=True))
    files={str(path.relative_to(dest)):hashlib.sha256(path.read_bytes()).hexdigest()
           for path in dest.rglob('*') if path.is_file() and path.name!='cost-file-sha256.json'}
    (dest/'cost-file-sha256.json').write_text(json.dumps(files,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('settled_own_records','failed_job_records')},indent=2))


if __name__=='__main__':main()
