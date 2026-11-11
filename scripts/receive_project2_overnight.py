"""Verify and safely extract the completed experiment into the E: results tree."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    args=p.parse_args();receipt=json.loads(args.receipt.read_text())
    assert sha(args.archive)==receipt['archive_sha256']
    target=args.root/'project2-overnight-20261020'
    assert args.root.resolve().drive.upper()=='E:'
    with tarfile.open(args.archive) as bundle:
        members=bundle.getmembers()
        for member in members:
            relative=Path(member.name)
            assert not relative.is_absolute() and '..' not in relative.parts
            assert relative.parts[0]=='project2-overnight-20261020'
            assert member.isfile() or member.isdir()
            assert (args.root/relative).resolve().is_relative_to(target.resolve())
        bundle.extractall(args.root,filter='data')
    manifest=target/'final_artifact_sha256.json'
    assert sha(manifest)==receipt['manifest_sha256']
    files=json.loads(manifest.read_text())
    for rel,digest in files.items():
        item=(target/rel).resolve();assert item.is_relative_to(target.resolve())
        assert sha(item)==digest,rel
    result=dict(status='PASS',verified_files=len(files),archive_sha256=receipt['archive_sha256'],
                output=str(target),main_audit=json.loads((target/'audit/audit.json').read_text())['status'],
                high_budget_status=json.loads((target/'high-budget/report/summary.json').read_text())['status'])
    (target/'local_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
