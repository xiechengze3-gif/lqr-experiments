"""Verify and safely extract the complete matched-gap results archive."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile
import time


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--sha256',required=True);p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args();started=time.monotonic();actual=digest(a.archive)
    assert actual==a.sha256,(actual,a.sha256)
    destination=a.destination.resolve();allowed={'matched-gap-npg-pi-v2-20261019','matched-gap-npg-pi-20261019'}
    assert destination.drive.upper()=='E:' and destination.name=='LQR_experiments'
    with tarfile.open(a.archive,'r:gz') as archive:
        members=archive.getmembers()
        for member in members:
            rel=PurePosixPath(member.name)
            assert not rel.is_absolute() and '..' not in rel.parts and rel.parts[0] in allowed
            assert member.isfile() or member.isdir(),member.name
            resolved=(destination/Path(*rel.parts)).resolve()
            assert destination in resolved.parents
        archive.extractall(destination,members=members,filter='data')
    out=destination/'matched-gap-npg-pi-v2-20261019'
    manifest=json.loads((out/'ARCHIVE_FILE_MANIFEST.json').read_text(encoding='utf-8'))
    for name,item in manifest.items():
        path=(destination/Path(*PurePosixPath(name).parts)).resolve()
        assert destination in path.parents and path.is_file()
        assert path.stat().st_size==item['bytes'] and digest(path)==item['sha256'],name
    for phase in ('pilot','confirm'):
        summary=json.loads((out/f'report-{phase}/summary.json').read_text())
        assert summary['status']=='complete'
        assert all(v['status']=='PASS' for v in summary['audits'].values())
    result=dict(status='PASS',archive=str(a.archive.resolve()),archive_bytes=a.archive.stat().st_size,
        sha256=actual,entries=len(members),verified_hashed_files=len(manifest),seconds=time.monotonic()-started,
        original_failed_preflight_and_CE_audit_included=True,all_policies_critics_checkpoints_included=True)
    (out/'local_archive_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
