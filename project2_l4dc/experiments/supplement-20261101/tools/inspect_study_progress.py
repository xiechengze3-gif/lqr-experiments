"""Operations only: own Slurm allocations, existing receipts and immutable result counts."""
import json,subprocess,sys
from collections import Counter
from pathlib import Path

base=Path('/scratch/user/changze/lqr_experiments')
sys.path.insert(0,str(base/'releases/supplement-20261101-actor-figures-refine-v25/tools'))
import submit_pilot_remote as ops

ledger=ops.status();folder=ops.OUT/'X3/formal/NPG';counts=Counter();hard=[]
for p in sorted(folder.glob('n*.json')):
    d=json.loads(p.read_text());s=d['spec'];counts[(s['spectrum'],s['budget_multiplier'])]+=1
    if d['status']!='COMPLETE':hard.append(dict(path=str(p),status=d['status'],error=d.get('error')))
q=subprocess.run(['squeue','-j','20359471','-h','-o','%T'],universal_newlines=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
states=Counter(q.stdout.splitlines())
progress=dict(checked_utc=ledger['last_accounting_utc'],spent_SU=ledger['spent_SU'],requested_bound_SU=ledger['requested_total_bound_SU'],cap_SU=200,
  X3_array=20359471,stored_multi_runs=sum(counts.values()),expected_multi_runs=288,
  complete_bundles=len(list((ops.OUT/'X3/formal-npg-bundles').glob('bundle-*.json'))),expected_bundles=32,
  cohorts=[dict(spectrum=k[0],batch_multiplier=k[1],files=v,expected=32) for k,v in sorted(counts.items())],
  hard_failure_receipts=hard,queue_states=dict(states),queue_query_error=q.stderr.strip() if q.returncode else None,
  max_observed_effective_billing_cores=max((r['effective_billing_cores'] for r in ledger['allocations']),default=0),
  note='Stored-file counts only, no model evaluation, no learner/parameter changes; partial cohorts are not final scientific conclusions')
print(json.dumps(dict(progress=progress,ledger=ledger)))
