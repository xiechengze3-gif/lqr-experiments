"""Freeze every predeclared source policy archive; no performance-based selection."""
import hashlib,json
from pathlib import Path

out=Path('/scratch/user/changze/lqr_experiments/results/supplement-20261101');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
complete=json.loads((out/'X1/FORMAL_ACTOR_COMPLETE.json').read_text());assert complete['status']=='COMPLETE' and complete['hard_failure_attempts']==0
items=[]
for system in range(101,109):
    for trial in range(1001,1005):
        for algorithm in ['CE','NPG','PI']:
            p=out/'X1/formal'/algorithm/f's{system}-t{trial}-m12-null25.json';d=json.loads(p.read_text())
            archive=p.with_name(p.stem+'.audit.npz');ap=p.with_name(p.stem+'.audit.json');audit=json.loads(ap.read_text())
            assert sha(archive)==audit['candidate_archive_sha256']
            items.append(dict(algorithm=algorithm,system=system,trial=trial,path=str(p),json_sha256=sha(p),archive=str(archive),archive_sha256=sha(archive),audit_json_sha256=sha(ap)))
assert len(items)==96
dest=out/'X4/SOURCE_POLICY_MANIFEST.json';assert not dest.exists()
dest.write_text(json.dumps(dict(status='COMPLETE',source_files=96,learned_source_policies=192,selection='All predeclared frozen final outputs; failed sources retained',items=items),indent=2)+'\n')
print(json.dumps(dict(status='COMPLETE',source_files=96,sha256=sha(dest))))
