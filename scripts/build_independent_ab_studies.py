"""Freeze numerical dependencies, scientific grid and bounded submission code."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


def main():
    root=Path(__file__).resolve().parents[1];name='independent-ab-studies-20261022-v1'
    files=['dense_scaling.py','scripts/rank_sweep100.py','scripts/actuation_redundancy.py',
        'scripts/npg_batched_collector.py','scripts/direct_stein_final.py','scripts/project2_overnight.py',
        'scripts/ce_matched_initial_gap.py','scripts/ce500_matched_gap.py',
        'scripts/independent_ab_stabilizer.py','scripts/independent_ab_study_support.py',
        'scripts/ce500_independent_stabilizer.py','scripts/stein_independent_stabilizer.py',
        'scripts/independent_ab_operations.py','configs/ce500_independent_stabilizer_20261022.json',
        'configs/stein_independent_stabilizer_20261022.json','slurm/independent_ab_studies.sbatch']
    dest=root/'packages'/name;assert not dest.exists(),'Frozen packages are immutable';hashes={}
    for f in files:
        source=root/f
        if f.endswith('.py'):ast.parse(source.read_text(encoding='utf-8'))
        if f.endswith('.json'):json.loads(source.read_text())
        data=source.read_bytes().replace(b'\r\n',b'\n');target=dest/f
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        hashes[f]=hashlib.sha256(data).hexdigest()
    (dest/'SHA256SUMS').write_bytes(''.join(v+'  '+k+'\n' for k,v in hashes.items()).encode())
    archive=root/'packages'/(name+'.tar.gz')
    with tarfile.open(archive,'w:gz') as tar:tar.add(dest,arcname=name)
    receipt=dict(status='frozen',archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        bytes=archive.stat().st_size,sources=hashes,free_E_bytes=shutil.disk_usage(root).free,
        CE_max_SU=100,Stein_max_SU=60,automatic_retries=0,
        CE_formal_pairs=150,Stein_PI_formal_paths=96,
        progression='measured preflight -> pilot with frozen grid -> formal using measured resource limits -> independent evaluation audit and report')
    (root/'receipts'/(name+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},indent=2))


if __name__=='__main__':main()
