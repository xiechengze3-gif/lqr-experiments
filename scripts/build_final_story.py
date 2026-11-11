"""Freeze sources and archive; local stdlib only, no simulation."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
NAME='final-story-20261024'
files=['scripts/final_story.py','scripts/final_story_ops.py','scripts/final_story_report.py',
       'slurm/final_story.sbatch','docs/FINAL_STORY_PROTOCOL_20261024.md',
       'scripts/project2_overnight.py','scripts/direct_stein_final.py',
       'scripts/npg_batched_collector.py','dense_scaling.py']
package=ROOT/'packages'/NAME
assert not (ROOT/'receipts'/(NAME+'-submitted.json')).exists(), 'Execution has started; preserve frozen sources'
for rel in files:
    data=(ROOT/rel).read_bytes().replace(b'\r\n',b'\n')
    if rel.endswith('.py'):ast.parse(data.decode('utf-8'))
    p=package/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
hashes={rel:hashlib.sha256((package/rel).read_bytes()).hexdigest() for rel in files}
(package/'SHA256SUMS').write_text(''.join(v+'  '+k+'\n' for k,v in hashes.items()),encoding='ascii',newline='\n')
archive=ROOT/'packages'/(NAME+'.tar.gz')
with tarfile.open(archive,'w:gz') as t:t.add(package,arcname=NAME)
receipt=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
             bytes=archive.stat().st_size,files=hashes,free_E_bytes=shutil.disk_usage(ROOT).free)
(ROOT/'receipts'/(NAME+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
