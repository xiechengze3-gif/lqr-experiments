"""Append the final settled accounting supplement; never overwrite v1 delivery."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
channel=root.parents[1]
name='accounting-20261103T000843.json'
path=root/name
data=json.loads(path.read_text())
assert data['status']=='BILLING_VERIFIED'
assert len(data['allocations'])==41 and len(data['settled_records'])==41
assert all(r['state']=='COMPLETED' for r in data['allocations'])
assert data['slurm_elapsed_billing_SU']==data['ams_settled_walltime_slots_SU']
assert data['cumulative_requested_SU']<=15 and not data['unknown_billing_jobs']
sha=hashlib.sha256(path.read_bytes()).hexdigest()
manifest=root/'ACCOUNTING_SETTLED_SUPPLEMENT_v1.json'
assert not manifest.exists()
supplement={'status':'ALL_41_ALLOCATIONS_SETTLED','accounting_file':name,'sha256':sha,
    'checked_utc':data['checked_utc'],'actual_SU':data['slurm_elapsed_billing_SU'],
    'requested_bound_SU':data['cumulative_requested_SU'],'cap_SU':15,
    'prior_delivery_unchanged':True,
    'note':'Slurm elapsed and AMS settled now agree. They represent the same cost, never add them.'}
manifest.write_text(json.dumps(supplement,indent=2)+'\n')
assert hashlib.sha256((channel/'CLAUDE_TASK.md').read_bytes()).hexdigest()=='faafceaef595bfb7d810247eaaad32b79ddbb27406685de4f36b3c79019fab1f'
reply=channel/'CODEX_REPLY.md'
header='## X7 REPORT — final settled accounting supplement (00:08:43 UTC)'
assert header not in reply.read_text(encoding='utf-8-sig')
with reply.open('a',encoding='utf-8',newline='\n') as f:
    f.write('\n\n'+header+'\n\nAll 41 allocations now settled in AMS. Slurm elapsed billing and AMS walltime-times-slots both equal **0.372777778 SU**; these are two views of the same cost, not additive. Requested bound remains 4.6/15 SU. New shallow file `experiments/x7-20261102/'+name+'` SHA256 '+sha+'. `ACCOUNTING_SETTLED_SUPPLEMENT_v1.json` binds the snapshot. Original delivery manifest, earlier timestamped accounting, figures, science, raw results and paper tex are unchanged. Latest review still 17:30 PROTOCOL acceptance; waiting for the REPORT review in the foreground.\n\nSTATUS: REPORT DONE X7\n')
print(json.dumps(supplement))
