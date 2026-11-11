"""Login-node file verification only; never replace an existing release."""
import hashlib,json,sys,tarfile
from pathlib import Path

name,digest=sys.argv[1:]
assert name.startswith('supplement-20261101-') and '/' not in name and '..' not in name
base=Path('/scratch/user/changze/lqr_experiments')
archive=base/'tmp/supplement-20261101'/(name+'.tar.gz')
target=base/'releases'/name
assert hashlib.sha256(archive.read_bytes()).hexdigest()==digest
assert not target.exists(), 'Existing frozen release must remain unchanged'
with tarfile.open(archive,'r:gz') as tf:
    members=tf.getmembers()
    assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
    target.mkdir()
    tf.extractall(target,members=members)
for line in (target/'SHA256SUMS').read_bytes().splitlines():
    expected,relative=line.decode().split('  ',1)
    assert hashlib.sha256((target/relative).read_bytes()).hexdigest()==expected
print(json.dumps(dict(status='DEPLOYED_VERIFIED',name=name,archive_sha256=digest)))
