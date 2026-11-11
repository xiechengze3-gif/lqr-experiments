"""Record the actual complete pilot review before any fresh formal data."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from publish_rank_sweep100_results import read, write

ROOT=Path(__file__).resolve().parents[1]
cfg=read(ROOT/'configs/rank_sweep100_pi_20261017.json');out=Path(cfg['local_output'])
summary=read(out/'report-pilot/summary.json');plan=read(out/'resource_plan.json')
assert summary['status']=='complete' and summary['completed_tasks']==25
assert read(out/'report-pilot/baseline_reuse.json')['original_derived_hashes_verified']
assert hashlib.sha256((ROOT/'configs/rank_sweep100_pi_20261017.json').read_bytes()).hexdigest()==summary['identity']['manifest_sha256']
for name,digest in summary['identity']['sources'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
raw=[read(p) for p in (out/'raw').glob('pi-*.json')]
assert len(raw)==25 and {d['seed'] for d in raw}==set(cfg['pilot_seeds'])
assert all(d['identity']==summary['identity'] for d in raw)
assert all(len(d['records'])==10 and d['algorithm_actual_transitions']=={'dense':3474432,'truncated':3474432} for d in raw)
used=0.;states=Counter();job_ids=[]
for line in (out/'pilot_review_accounting.psv').read_text().splitlines():
    fields=line.strip().split('|')
    if len(fields)<7 or not fields[0]:continue
    assert fields[2].startswith(('COMPLETED','CANCELLED','OUT_OF_MEMORY','FAILED','TIMEOUT'))
    tres=dict(kv.split('=',1) for kv in fields[6].split(',') if '=' in kv)
    used+=int(fields[4] or 0)*max(float(fields[5] or 0),float(tres.get('billing',0)))/3600
    states[fields[2]]+=1;job_ids.append(fields[0])
assert len(job_ids)==len(set(job_ids))
upper=used+plan['formal_total_walltime_upper_core_hours']+plan['reporting_archive_allowance_core_hours']
assert upper<=plan['planning_cap_core_hours']
eps=cfg['epsilon'];primary=[r for r in summary['requirements'] if r['epsilon']==eps]
oracle=read(out/'oracle.json')['references']
result=dict(status='PASS',decision='Proceed with30 fresh seeds and exactly the same frozen four-update scientific protocol',
    actual_complete_pilot_pairs=25,pilot_seeds=cfg['pilot_seeds'],formal_seeds=cfg['confirm_seeds'],
    epsilon=eps,sensitivity_epsilon=eps/2,batch_schedule=cfg['batch_schedule'],
    prior_actual_core_hours=used,prior_own_Slurm_states=dict(states),
    remaining_formal_upper_core_hours=plan['formal_total_walltime_upper_core_hours'],
    upper_campaign_core_hours=upper,planning_cap_core_hours=plan['planning_cap_core_hours'],
    formal_execution_mode=plan['formal_execution_mode'],pilot_unique_physical_transitions=summary['physical_transitions'],
    primary_results=primary,sensitivity_results=[r for r in summary['requirements'] if r['epsilon']==eps/2],
    exact_PI_primary_iterations={str(r):next(q['stage'] for q in oracle if q['rank']==r and q['gap']<=eps) for r in cfg['ranks']},
    scientific_manifest_unchanged=True,all_nine_numerical_sources_unchanged=True,
    dense_censoring_retained=True,per_rank_learner_tuning=False,
    phase_selection='Pilot seeds excluded from all formal estimates; all new seeds100..129 retained regardless of outcome',
    review='All pilot paths stable, all solves converged. At the common primary target, dense reaches5/5 only at full rank; truncated reaches5/5 at every rank. Keep not-reached dense cells censored rather than assigning finite complexity. Complete policy/critic replay remains scheduled after final archive retrieval.')
write(ROOT/'receipts/rank-sweep100-pi-pilot-review.json',result)
print(json.dumps(dict(status='PASS',pilot_pairs=25,prior_core_hours=used,upper_core_hours=upper,
                     primary=[{k:r[k] for k in ('rank','method','N_hat_epsilon_90','max_budget_successes')} for r in primary])))
