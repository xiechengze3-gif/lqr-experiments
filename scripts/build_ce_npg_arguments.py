"""Local stdlib-only syntax/grid checks and immutable release packaging; no simulation."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from ce_npg_argument_grid import NAME,all_specs

files=['scripts/ce_npg_argument_grid.py','scripts/ce_npg_argument_run.py',
    'scripts/ce_npg_argument_report.py','scripts/ce_npg_argument_ops.py','slurm/ce_npg_argument.sbatch',
    'configs/ce_npg_argument_revision_20261027.json','docs/CE_NPG_ARGUMENT_PROTOCOL_20261027.md',
    'docs/CE_NPG_ARGUMENT_COVERAGE_20261027.md','docs/MANUSCRIPT_THREE_GROUPS_PROTOCOL_20261027.md',
    'scripts/manuscript_three_groups.py','scripts/manuscript_three_groups_report.py',
    'scripts/npg_batched_collector.py','dense_scaling.py']
package=ROOT/'packages'/NAME
assert not (ROOT/'receipts'/(NAME+'-formal.json')).exists(),'Formal release is immutable'
assert len(all_specs())==2064 and sum(r['reuse_id'] is None for r in all_specs())==1728
for rel in files:
    data=(ROOT/rel).read_bytes().replace(b'\r\n',b'\n')
    if rel.endswith('.py'):ast.parse(data.decode('utf-8'))
    if rel.endswith('.json'):json.loads(data)
    target=package/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
hashes={rel:hashlib.sha256((package/rel).read_bytes()).hexdigest() for rel in files}
(package/'SHA256SUMS').write_text(''.join(h+'  '+p+'\n' for p,h in hashes.items()),encoding='ascii',newline='\n')
archive=ROOT/'packages'/(NAME+'.tar.gz')
with tarfile.open(archive,'w:gz') as stream:stream.add(package,arcname=NAME)
receipt=dict(status='PACKAGED_NOT_SUBMITTED',archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    bytes=archive.stat().st_size,files=hashes,free_E_bytes=shutil.disk_usage(ROOT).free,
    planned=2064,reuse_candidates=336,new=1728,local_simulations_run=0)
(ROOT/'receipts'/(NAME+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,indent=2))
