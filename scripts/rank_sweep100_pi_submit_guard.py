"""Read-only coverage/source/resource guard before fresh PI confirmation."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--result',type=Path,required=True)
p.add_argument('--release',type=Path,required=True);p.add_argument('--accounting',type=Path,required=True)
a=p.parse_args();cfg=json.loads((a.result/'resolved_config.json').read_text())
ident=cfg['identity'];rows=[]
for path in (a.result/'raw').glob('pi-*.json'):rows.append(json.loads(path.read_text()))
assert all(d['seed'] in cfg['pilot_seeds'] for d in rows),'Fresh confirmation data already exist'
assert len(rows)==25 and {(d['rank'],d['seed']) for d in rows}=={(r,s) for r in cfg['ranks'] for s in cfg['pilot_seeds']}
assert all(d['identity']==ident and len(d['records'])==2*(len(cfg['batch_schedule'])+1) for d in rows)
for name,digest in ident['sources'].items():
    assert hashlib.sha256((a.release/name).read_bytes()).hexdigest()==digest,('Source hash changed',name)
assert json.loads((a.result/'verification.json').read_text())['status']=='PASS'
assert json.loads((a.result/'maximum_memory_verification.json').read_text())['status']=='PASS'
used=0.;records=[]
for line in a.accounting.read_text().splitlines():
    fields=line.strip().split('|')
    if len(fields)<7 or not fields[0]:continue
    raw_id,job,state,exit_code,elapsed,cpus,tres=fields[:7]
    if '.' in job:continue
    assert state.startswith(('COMPLETED','CANCELLED','OUT_OF_MEMORY','FAILED','TIMEOUT')),(job,state)
    billing=dict(kv.split('=',1) for kv in tres.split(',') if '=' in kv)
    effective=max(float(cpus or 0),float(billing.get('billing',0)))
    cost=int(elapsed or 0)*effective/3600;used+=cost
    records.append(dict(job_id=job,state=state,elapsed_seconds=int(elapsed or 0),effective_units=effective,core_hours=cost))
assert len({r['job_id'] for r in records})==len(records)
plan=json.loads((a.result/'resource_plan.json').read_text())
assert plan['learning_manifest_modified'] is False and plan['numerical_sources_modified'] is False
assert plan['formal_execution_mode']=='five_ranks_sequentially_per_seed_bundle'
assert plan['formal_seed_bundles']==len(cfg['confirm_seeds'])==30
assert plan['paired_groups_per_bundle']==len(cfg['ranks'])==5
assert plan['combined_max_concurrency']==30
remaining=plan['formal_seed_bundles']*plan['formal_bundle_walltime_minutes']/60
assert remaining==plan['formal_total_walltime_upper_core_hours']
overhead=plan['reporting_archive_allowance_core_hours'];cap=plan['planning_cap_core_hours']
assert used+remaining+overhead<=cap,(used,remaining,overhead,cap)
result=dict(status='PASS',pilot_complete=True,formal_seeds_not_started=True,
    prior_core_hours=used,remaining_formal_upper_core_hours=remaining,
    reporting_archive_allowance_core_hours=overhead,total_cap_core_hours=cap,
    bounded_upper_total_core_hours=used+remaining+overhead,own_job_records=records,resource_plan=plan,
    numerical_sources_unchanged=True,epsilon=cfg['epsilon'],batch_schedule=cfg['batch_schedule'],
    formal_bundle_source_sha256=hashlib.sha256((a.result/'formal_bundle.sbatch').read_bytes()).hexdigest())
(a.result/'preconfirmation_guard.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='own_job_records'}))
