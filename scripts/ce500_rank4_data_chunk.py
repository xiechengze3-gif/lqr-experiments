"""Archive only committed, immutable numerical files while auditing continues."""
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time

base=Path('/scratch/user/changze/lqr_experiments');name='ce500-rank4-extension-20261020'
out=base/'results'/name;dest=base/'archives'/name;dest.mkdir(parents=True,exist_ok=True)
assert os.environ.get('SLURM_JOB_ID')
assert len(list((out/'raw').glob('ce-r004-s02*.json')))==30
began=time.monotonic()
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
files={}
for directory in ['policies','checkpoints','estimates','systems','diagnostics']:
    for f in sorted((out/directory).rglob('*')):
        if f.is_file():files[str(f.relative_to(out))]=sha(f)
archive=dest/'data.tar'
assert not archive.exists()
with tarfile.open(archive,'w') as t:
    for rel in files:t.add(out/rel,arcname=rel,recursive=False)
receipt=dict(status='complete',slurm_job_id=os.environ['SLURM_JOB_ID'],files=files,
    archive_sha256=sha(archive),bytes=archive.stat().st_size,seconds=time.monotonic()-began,
    scope='Committed immutable data only; full 900-policy audit and original complete archive retained.')
(dest/'data.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='files'}),flush=True)
