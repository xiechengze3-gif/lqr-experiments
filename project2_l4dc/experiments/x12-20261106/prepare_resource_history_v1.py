"""Freeze a conservative resource-only historical floor before X12 formal runs."""
import csv,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;X=R.parent/'x10-20261106'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
oldcfg=X/'prepared-actor-formal-v1/formal-config.json';cfg=json.loads(oldcfg.read_text())
account=X/'actor-accounting-1794007093117686148.json';a=json.loads(account.read_text())
assert a['status']=='OWN_X10B_ACCOUNTING_VERIFIED' and a['Slurm_allocation_rows']==267
assert cfg['eta']==.2 and cfg['H']==16 and cfg['selected_NPG_T']==16 and cfg['selected_PI_T']==8
raw=R/'raw-deliveries-v1/calibration-v1/calibration-resolution-v1/DONE.json';cal=json.loads(raw.read_text())
assert cal['status']=='PASS_CALIBRATION' and cal['N_cal']==2097152
pair_new=2*sum(s['primitive_per_arm_per_algorithm'] for s in cal['all_schedules'])
chain=json.loads((X/'delivery-actor-report-v1/submissions/FORMAL_CHAIN_v1.json').read_text())
floors=[]
for alg in ['NPG','PI']:
    group=next(g for g in cfg['formal_groups'] if g['n']==72 and {r['algorithm'] for r in g['runs']}=={alg})
    job=next(j['job'] for j in chain['jobs'] if j['group']==group['id'])
    pair_old=2*sum(next(s['primitive_per_arm_per_algorithm'] for s in cfg['all_schedules'] if s['n']==72 and s['rung']==r['rung']) for r in group['runs'])
    rows=[r for r in a['allocations'] if r['job'].split('_')[0]==job]
    assert len(rows)==32 and all(r['state']=='COMPLETED' and r['billing_cores']==1 and r['cpus']==1 for r in rows)
    worst=max(r['elapsed_seconds'] for r in rows)
    floors.append(dict(algorithm=alg,reference_n=72,reference_job=job,reference_tasks=32,
        reference_primitive_per_paired_task=pair_old,maximum_Slurm_elapsed_seconds=worst,
        reference_seconds_per_transition=worst/pair_old,new_n=60,new_primitive_per_paired_task=pair_new,
        historical_body_floor_seconds=worst*pair_new/pair_old,
        use='max(full9rung_n60_pilot_body, historical_body_floor); no scientific outcome enters this choice'))
proof=dict(status='HISTORICAL_RESOURCE_FLOOR_FROZEN_BEFORE_FORMAL',rules=floors,
    method='Use worst allocation elapsed per primitive transition from all32 same-engine n72 tasks/algorithm; n72 is larger than n60; retain larger of floor and actual n60 pilot body.',
    uncertainty='A conservative planning floor, not a deterministic throughput guarantee. Full actual n60 pilot remains mandatory.',
    wall_guard='ceil((1.20*effective_body_seconds+30)/60) minutes',
    actual_forecast='32*sum(effective_body)/3600 + all actual pilot allocations + model-prep reserve5/60 + report reserve8',
    requested_upper='8.75 successful pilot requests + model-prep5/60 +32*sum(wall_minutes)/60 +report8; must<=300',
    caps=dict(actual_forecast_SU=230,requested_upper_SU=300),formal_observations_used=False,
    reference_config_sha256=sha(oldcfg),reference_accounting_sha256=sha(account),calibration_sha256=sha(raw),
    new_training_transitions=0,Grace_SU=0)
with (R/'RESOURCE_HISTORY_FLOOR_v1.json').open('x') as f:json.dump(proof,f,indent=2)
print(json.dumps(proof))
