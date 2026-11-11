"""Freeze equal-mode CE numerical sources; local stdlib file operations only."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
NAME='ce500-equal-modes-20261020'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cfg=json.loads((ROOT/'configs/ce500_equal_modes_20261020.json').read_text(encoding='utf-8'))
    source=Path(cfg['source_local_output'])
    verification=json.loads((source/'verification.json').read_text(encoding='utf-8'))
    assert sha(source/'systems/r002.npz')==cfg['source_system_sha256']
    old=verification['identity']['sources']
    for name,digest in old.items():assert sha(ROOT/name)==digest,name
    files=list(old)+['scripts/ce500_equal_modes.py','configs/ce500_equal_modes_20261020.json',
                     'docs/CE500_EQUAL_MODES_PROTOCOL_20261020.md','slurm/ce500_equal_modes.sbatch']
    package=ROOT/'packages'/NAME
    assert not package.exists(),'Frozen package must not be overwritten'
    for name in files:
        source_path=ROOT/name
        if name.endswith('.py'):ast.parse(source_path.read_text(encoding='utf-8'),filename=name)
        dest=package/name;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(source_path.read_bytes().replace(b'\r\n',b'\n') if name.endswith('.sbatch') else source_path.read_bytes())
    (package/'SHA256SUMS').write_bytes(''.join(sha(package/name)+'  '+name+'\n' for name in files).encode('utf-8'))
    archive=ROOT/'packages'/(NAME+'.tar.gz')
    with tarfile.open(archive,'w:gz') as bundle:bundle.add(package,arcname=NAME)
    receipt=dict(status='frozen',experiment=NAME,archive=str(archive),sha256=sha(archive),
                 unchanged_numeric_sources=old,source_system_sha256=cfg['source_system_sha256'],
                 local_output=cfg['local_output'],remote_output=cfg['output'],SU_cap=60,
                 local_free_bytes=shutil.disk_usage(ROOT).free)
    (ROOT/'receipts'/(NAME+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
