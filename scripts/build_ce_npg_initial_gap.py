"""Package report-only sources with an explicitly LF-encoded checksum manifest."""
import ast
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
NAME='ce-npg-initial-gap-20261028'
FILES=['scripts/ce_npg_initial_gap_postprocess.py','scripts/submit_ce_npg_initial_gap.py',
       'configs/ce_npg_initial_gap_postprocess_20261028.json','slurm/ce_npg_initial_gap.sbatch',
       'docs/CE_NPG_INITIAL_GAP_PROTOCOL_20261028.md']
package=ROOT/'packages'/NAME
hashes={}
for rel in FILES:
    data=(ROOT/rel).read_bytes().replace(b'\r\n',b'\n')
    if rel.endswith('.py'):ast.parse(data.decode('utf-8'))
    target=package/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    hashes[rel]=hashlib.sha256(data).hexdigest()
manifest=''.join(d+'  '+p+'\n' for p,d in hashes.items()).encode('ascii')
(package/'SHA256SUMS').write_bytes(manifest)
assert b'\r' not in manifest
archive=ROOT/'packages'/(NAME+'.tar.gz')
with tarfile.open(archive,'w:gz') as stream:stream.add(package,arcname=NAME)
receipt=dict(status='PACKAGED_NOT_SUBMITTED',archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    bytes=archive.stat().st_size,files=hashes,checksum_manifest_line_endings='LF',new_learning_runs=0,new_training_transitions=0)
(ROOT/'receipts'/(NAME+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,indent=2))
