"""Verify new delivery, preserving every existing byte including older results."""
import argparse,json,tarfile
from pathlib import Path
from control import ROOT,sha,write

p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args()
folder=ROOT/'deliveries';manifest=json.loads((folder/(a.name+'.json')).read_text(encoding='utf-8-sig'))
archive=folder/(a.name+'.tar.gz');assert sha(archive)==manifest['archive_sha256']
with tarfile.open(archive) as tf:
    members=tf.getmembers();assert len(members)==manifest['count']
    for m in members:
        assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
        path=ROOT/m.name;payload=tf.extractfile(m).read()
        if path.exists():assert path.read_bytes()==payload,'Existing file differs; never overwrite'
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
for r in manifest['files']:
    path=ROOT/r['relative'];assert path.stat().st_size==r['size'] and sha(path)==r['sha256']
old=json.loads((ROOT/'provenance/old_files_sha256.json').read_text())
assert all(sha(p)==h for p,h in old.items())
result=dict(status='PASS',files=manifest['count'],bytes=manifest['bytes'],old_files_unchanged=len(old))
write(folder/(a.name+'.verified.json'),result);print(json.dumps(result))
