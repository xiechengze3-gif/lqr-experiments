"""Verify archive/checksums and extract safely to the approved E: results tree."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();receipt=json.loads(a.receipt.read_text());assert sha(a.archive)==receipt['sha256']
    root=a.root.resolve();target=root/'final-story-20261024'
    assert root.drive.upper()=='E:' and target.parent==root
    with tarfile.open(a.archive) as t:
        for member in t.getmembers():
            rel=PurePosixPath(member.name)
            assert not rel.is_absolute() and '..' not in rel.parts and rel.parts[0]==target.name
            assert member.isfile() or member.isdir()
            assert root.joinpath(*rel.parts).resolve().is_relative_to(target.resolve())
        t.extractall(root,filter='data')
    manifest=target/'artifact_sha256.json';assert sha(manifest)==receipt['manifest_sha256']
    files=json.loads(manifest.read_text())
    for rel,digest in files.items():
        item=(target/rel).resolve();assert item.is_relative_to(target.resolve())
        assert sha(item)==digest,rel
    assert sha(target/'report/summary.json')==receipt['report_sha256']
    result=dict(status='PASS',verified_files=len(files),archive_sha256=receipt['sha256'],
                output=str(target),report_status=json.loads((target/'report/summary.json').read_text())['status'])
    (target/'local_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
