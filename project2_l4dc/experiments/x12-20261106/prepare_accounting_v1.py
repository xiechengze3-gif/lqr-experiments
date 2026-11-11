"""Metadata adapter of accepted own-job AMS/Slurm accounting parser."""
import ast,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;source=R.parent/'x10-20261106/accounting_actor.py'
s=source.read_text(encoding='utf-8');s=s.replace('from pathlib import Path','from pathlib import Path\nimport remote_followon_v1 as ops')
before="    ledger = json.loads((OUT/'budget/ledger.json').read_text())\n    assert ledger['study'] == 'X10b' and ledger['requested_upper_cap_SU'] == 200 and ledger['actual_forecast_cap_SU'] == 160"
after="    ledgerpath, ledger = ops.ledger()\n    gate = json.loads((Path(__file__).resolve().parent/'gate.json').read_text())\n    assert gate['status'] == 'ALL_PILOT_COST_GATES_PASS' and gate['requested_upper_SU'] <= 300 and gate['actual_forecast_SU'] <= 230"
assert s.count(before)==1;s=s.replace(before,after)
s=s.replace("ledger['submissions']","ledger['allocations']").replace("ledger['measured_forecast_actual_SU']","ledger['measured_actual_forecast_SU']")
s=s.replace('/results/x10-20261106/X10b','/results/x12-20261106').replace('X10b','X12').replace('X10B','X12')
s=s.replace('cap_requested_SU=200, actual_forecast_cap_SU=160','cap_requested_SU=300, actual_forecast_cap_SU=230').replace("['cumulative_requested_SU'] <= 200+1e-9","['cumulative_requested_SU'] <= 300+1e-9")
ast.parse(s);target=R/'accounting_v1.py'
with target.open('x',encoding='utf-8',newline='\n') as f:f.write(s)
proof=dict(status='OWN_ACCOUNTING_METADATA_ADAPTER_PREPARED',original_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
           new_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),new_jobs=0,new_training_transitions=0,
           changes='X12 namespace/caps and immutable versioned ledger selector; accepted sacct/own-AMS parsing and overlapping-charge treatment unchanged.')
with (R/'ACCOUNTING_SOURCE_PROOF_v1.json').open('x',encoding='utf-8') as f:json.dump(proof,f,indent=2)
print(json.dumps(proof))
