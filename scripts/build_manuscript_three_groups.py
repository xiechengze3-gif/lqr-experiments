"""Freeze the experiment package locally, without numerical execution."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
NAME='manuscript-three-groups-20261027'
files=['scripts/manuscript_three_groups.py','scripts/manuscript_three_groups_ops.py',
    'slurm/manuscript_three_groups.sbatch','docs/MANUSCRIPT_THREE_GROUPS_PROTOCOL_20261027.md',
    'scripts/npg_batched_collector.py','dense_scaling.py']
package=ROOT/'packages'/NAME
assert not (ROOT/'receipts'/(NAME+'-formal.json')).exists(),'Formal source is frozen'
for rel in files:
    data=(ROOT/rel).read_bytes().replace(b'\r\n',b'\n')
    if rel.endswith('.py'):ast.parse(data.decode('utf-8'))
    p=package/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
hashes={p:hashlib.sha256((package/p).read_bytes()).hexdigest() for p in files}
(package/'SHA256SUMS').write_text(''.join(v+'  '+k+'\n' for k,v in hashes.items()),encoding='ascii',newline='\n')
archive=ROOT/'packages'/(NAME+'.tar.gz')
with tarfile.open(archive,'w:gz') as stream:stream.add(package,arcname=NAME)
receipt=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    bytes=archive.stat().st_size,files=hashes,free_E_bytes=shutil.disk_usage(ROOT).free)
(ROOT/'receipts'/(NAME+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
