"""Package reviewed operational additions without editing frozen science."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('files',nargs='+');a=p.parse_args()
    assert a.name.startswith('project2-overnight-') and '/' not in a.name
    dest=ROOT/'packages'/a.name;assert not dest.exists()
    hashes={}
    for rel in a.files:
        source=(ROOT/rel).resolve();assert source.is_relative_to(ROOT)
        data=source.read_bytes()
        if source.suffix=='.py':ast.parse(data.decode('utf-8'),filename=rel)
        if source.suffix=='.sbatch':data=data.replace(b'\r\n',b'\n')
        target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        hashes[rel]=hashlib.sha256(data).hexdigest()
    (dest/'SHA256SUMS').write_bytes(''.join(d+'  '+s+'\n' for s,d in hashes.items()).encode())
    archive=ROOT/'packages'/(a.name+'.tar.gz')
    with tarfile.open(archive,'w:gz') as bundle:bundle.add(dest,arcname=a.name)
    print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=hashes),indent=2))


if __name__=='__main__':main()
