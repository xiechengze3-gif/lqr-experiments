"""Freeze the zero-initialization companion and unchanged numerical dependencies."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
NAME='ce500-zero-init-20261022'


def main():
    files=['dense_scaling.py','scripts/rank_sweep100.py','scripts/actuation_redundancy.py',
        'scripts/npg_batched_collector.py','scripts/direct_stein_final.py','scripts/ce_matched_initial_gap.py',
        'scripts/ce500_matched_gap.py','scripts/ce500_zero_init.py','scripts/ce500_zero_init_ops.py',
        'configs/ce500_zero_init_20261022.json','slurm/ce500_zero_init.sbatch',
        'docs/INDEPENDENT_AB_ZERO_INIT_PROTOCOL_20261022.md']
    package=ROOT/'packages'/NAME;assert not package.exists(),'Frozen packages are immutable'
    hashes={}
    for name in files:
        source=ROOT/name
        if name.endswith('.py'):ast.parse(source.read_text(encoding='utf-8'))
        target=package/name;target.parent.mkdir(parents=True,exist_ok=True)
        data=source.read_bytes()
        if name.endswith('.sbatch'):data=data.replace(b'\r\n',b'\n')
        target.write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    (package/'SHA256SUMS').write_bytes(''.join(v+'  '+k+'\n' for k,v in hashes.items()).encode())
    archive=ROOT/'packages'/(NAME+'.tar.gz')
    with tarfile.open(archive,'w:gz') as tar:tar.add(package,arcname=NAME)
    receipt=dict(status='frozen',archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        bytes=archive.stat().st_size,sources=hashes,free_local_E_bytes=shutil.disk_usage(ROOT).free)
    (ROOT/'receipts'/(NAME+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},indent=2))


if __name__=='__main__':main()
