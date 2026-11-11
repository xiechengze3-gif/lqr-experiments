"""Read-only result packaging on a login node, with hashes for every file."""
import hashlib,json,sys,tarfile
from pathlib import Path

base=Path('/scratch/user/changze/lqr_experiments')
out=base/'results/supplement-20261101'
name,*subtrees=sys.argv[1:]
assert name.startswith('delivery-') and '/' not in name and '..' not in name
folder=base/'tmp/supplement-20261101'
archive=folder/(name+'.tar.gz');manifest=folder/(name+'.json')
assert not archive.exists() and not manifest.exists()
paths=[]
for subtree in subtrees:
    assert not Path(subtree).is_absolute() and '..' not in Path(subtree).parts
    p=out/subtree;assert p.exists(),subtree
    paths.extend([p] if p.is_file() else [q for q in p.rglob('*') if q.is_file() and not q.name.endswith('.tmp')])
paths=sorted(set(paths));assert paths
files=[dict(relative=str(p.relative_to(out)),size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]
with tarfile.open(archive,'w:gz') as tf:
    for p in paths:tf.add(p,arcname=str(p.relative_to(out)),recursive=False)
result=dict(status='PACKAGED',count=len(files),bytes=sum(r['size'] for r in files),archive=str(archive),
            archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=files)
manifest.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='files'}))
