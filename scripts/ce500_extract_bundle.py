"""Verify and safely extract a downloaded immutable CE500 result group."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True)
    a=p.parse_args();r=json.loads(a.receipt.read_text());assert sha(a.archive)==r['archive_sha256']
    root=a.output_root.resolve();assert str(root).lower().startswith('e:\\chatgpt\\results\\lqr_experiments')
    with tarfile.open(a.archive,'r:gz') as bundle:
        for member in bundle.getmembers():
            parts=PurePosixPath(member.name).parts
            assert parts and parts[0]=='ce500-matched-gap-20261019' and '..' not in parts and '\\' not in member.name
            assert member.isfile() or member.isdir()
        bundle.extractall(root,filter='data')
    out=root/'ce500-matched-gap-20261019'
    for relative,digest in r['files_sha256'].items():
        pp=PurePosixPath(relative);assert not pp.is_absolute() and '..' not in pp.parts
        assert sha(out/relative)==digest,relative
    result=dict(status='PASS',archive=str(a.archive),archive_sha256=r['archive_sha256'],verified_files=len(r['files_sha256']))
    a.receipt.with_name(a.receipt.stem+'-local-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
