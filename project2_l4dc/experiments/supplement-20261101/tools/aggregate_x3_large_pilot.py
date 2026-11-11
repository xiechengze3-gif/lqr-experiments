"""Aggregate completed dense-only largest-budget measurements; no scientific computation."""
import hashlib,json,math
from pathlib import Path

root=Path('/scratch/user/changze/lqr_experiments/results/supplement-20261101/X3/pilot-npg-large')
items=[]
for sp in ['smooth','gapped','flat']:
    d=json.loads((root/f'MEASURE_{sp}.json').read_text());assert d['status']=='COMPLETE' and d['base_selection_already_frozen']
    assert hashlib.sha256(Path(d['path']).read_bytes()).hexdigest()==d['sha256'];items.append(d)
maximum=max(d['seconds'] for d in items);seconds=maximum*5*3*(21/16)*1.3+60;minutes=15*math.ceil(seconds/(15*60))
out=dict(status='COMPLETE',items=items,dense_only_timing=True,max_largest_dense_seconds=maximum,
         formal_worst_bundle_estimate_seconds=seconds,formal_wall_minutes=minutes,formal_request_bound_SU=32*minutes/60,
         total_batch_multipliers=21,methods=5,spectra=3,margin=1.3,startup_seconds=60,
         base_already_frozen_by_dense_qualification=True,formal_outputs_used=False)
p=root/'BASE8192_COMPLETE.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='items'}))
