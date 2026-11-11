"""Hash/coverage verification of approved fixed-policy diagnostic; no new evaluations."""
import hashlib,json,time
from collections import Counter
from pathlib import Path

base=Path('/scratch/user/changze/lqr_experiments');out=base/'results/supplement-20261101';release=base/'releases/supplement-20261101-x4-formal-v23'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=out/'X4/formal/outputs.json';d=json.loads(p.read_text());ap=json.loads((release/'X4/ACCEPTED.json').read_text())
assert d['status']=='COMPLETE' and ap['decision']=='ACCEPTED' and d['new_training_transitions']==0
assert d['config_sha256']==ap['config_sha256']==sha(release/'configs/X4_v1.json')
assert d['source_sha256']==ap['source_sha256']==sha(release/'robustness_x4.py')
assert sha(out/'X4/formal/perturbations.npz')==d['perturbations_sha256']
assert d['max_orthogonality_error']<1e-12 and d['max_operator_norm_error']<1e-12
manifest=json.loads((release/'X4/SOURCE_POLICY_MANIFEST.json').read_text());expected={r['path']:r for r in manifest['items']}
assert len(d['source_manifest'])==len(expected)==96
for r in d['source_manifest']:
    assert r['json_sha256']==expected[r['path']]['json_sha256'] and r['archive_sha256']==expected[r['path']]['archive_sha256']
rows=d['records'];keys={(r['algorithm'],r['mode'],r['system'],r['trial'],r['scale'],r['direction']) for r in rows}
assert len(rows)==len(keys)==5760
counts=Counter((r['algorithm'],r['mode'],r['scale']) for r in rows);assert len(counts)==18 and set(counts.values())=={320}
result=dict(status='COMPLETE',scope='OFFLINE_DIAGNOSTIC',outputs=5760,source_files=96,new_training_transitions=0,
  source_failed_outputs=sum(not r['source_endpoint_stable'] for r in rows),
  new_instability=sum(r['source_endpoint_stable'] and not r['stable'] for r in rows),
  failed_outputs=sum(not r['stable'] for r in rows),outputs_sha256=sha(p),config_sha256=d['config_sha256'],source_sha256=d['source_sha256'],
  frozen_source_manifest_sha256=sha(release/'X4/SOURCE_POLICY_MANIFEST.json'),
  max_gap_identity_error=max(r.get('independent_gap_error',0.) for r in rows),
  max_null_constraint_error=d['max_orthogonality_error'],max_operator_norm_error=d['max_operator_norm_error'],
  job=d['job'],verified_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
dest=out/'X4/FORMAL_DIAGNOSTIC_COMPLETE.json';assert not dest.exists();dest.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
