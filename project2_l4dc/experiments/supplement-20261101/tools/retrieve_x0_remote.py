"""Read historical small reports, stage a new transfer archive; no science/jobs."""
import hashlib, json, tarfile
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments')
DEST=BASE/'tmp/supplement-20261101'
ARCHIVE=DEST/'x0-retrieval-v1.tar.gz'
MANIFEST=DEST/'x0-retrieval-v1.manifest.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

if ARCHIVE.exists() or MANIFEST.exists():
    raise RuntimeError('Transfer receipt exists; inspect it before any replay.')
selected=[]
for name in ['independent-ab-stabilizer-20261022','ce500-common-constants-20261022']:
    scope=BASE/'local-archives/20261025/snapshot/project/analysis'/name
    assert scope.is_dir(),str(scope)
    for path in sorted(scope.rglob('*')):
        if path.is_file():selected.append((path,'snapshot-analysis/'+name+'/'+str(path.relative_to(scope))))
scope=BASE/'results/ce500-common-constants-20261022'
for sub in ['report-confirm','report-pilot']:
    for path in sorted((scope/sub).iterdir()):
        if path.is_file():selected.append((path,'original-results/ce500-common-constants-20261022/'+sub+'/'+path.name))
for name in ['resolved_config.json','verification.json','preflight.json','formal_plan.json','submission-formal.json','formal_submission_verification_20261023.json']:
    path=scope/name
    selected.append((path,'original-results/ce500-common-constants-20261022/'+name))
assert sum(p.stat().st_size for p,_ in selected)<20*1024*1024
DEST.mkdir(parents=True,exist_ok=True)
records=[{'remote':str(p),'archive_path':a,'size':p.stat().st_size,'sha256':sha(p)} for p,a in selected]
with tarfile.open(str(ARCHIVE),'w:gz') as tf:
    for p,a in selected:tf.add(str(p),arcname=a,recursive=False)
data={'archive':str(ARCHIVE),'archive_sha256':sha(ARCHIVE),'files':records,'bytes':sum(r['size'] for r in records),'count':len(records),'new_jobs':0}
MANIFEST.write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({'archive':str(ARCHIVE),'sha256':data['archive_sha256'],'files':len(records),'bytes':data['bytes'],'new_jobs':0}))
