"""Freeze numerical sources and reporting for the fixed random-A experiment."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
NAME='ce500-random-a-20261020'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    files=['scripts/rank_sweep100.py','scripts/actuation_redundancy.py',
        'scripts/npg_batched_collector.py','scripts/direct_stein_final.py','dense_scaling.py',
        'scripts/ce_matched_initial_gap.py','scripts/ce500_matched_gap.py','scripts/ce500_report.py',
        'scripts/ce500_random_a.py','scripts/ce500_random_a_report.py','scripts/ce500_random_a_operations.py',
        'configs/ce500_random_a_20261020.json','docs/CE500_RANDOM_A_PROTOCOL_20261020.md',
        'slurm/ce500_random_a.sbatch']
    cfg=json.loads((ROOT/'configs/ce500_random_a_20261020.json').read_text())
    package=ROOT/'packages'/NAME;assert not package.exists(),'Frozen packages are immutable'
    for name in files:
        source=ROOT/name
        if name.endswith('.py'):ast.parse(source.read_text(encoding='utf-8'),filename=name)
        dest=package/name;dest.parent.mkdir(parents=True,exist_ok=True)
        content=source.read_bytes()
        dest.write_bytes(content.replace(b'\r\n',b'\n') if name.endswith('.sbatch') else content)
    (package/'SHA256SUMS').write_bytes(''.join(sha(package/n)+'  '+n+'\n' for n in files).encode())
    archive=ROOT/'packages'/(NAME+'.tar.gz')
    with tarfile.open(archive,'w:gz') as bundle:bundle.add(package,arcname=NAME)
    receipt=dict(status='frozen',experiment=NAME,archive=str(archive),sha256=sha(archive),
        sources={n:sha(package/n) for n in files},local_output=cfg['local_output'],
        remote_output=cfg['output'],SU_cap=cfg['resources']['total_SU_cap'],
        local_free_bytes=shutil.disk_usage(ROOT).free)
    (ROOT/'receipts'/(NAME+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
