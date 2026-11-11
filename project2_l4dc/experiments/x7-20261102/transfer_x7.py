"""Streaming sealed X7 delivery. Pack raw/models/report on the compute node.

Based on preserved X6 streaming control. No scientific calculation or data change.
"""
import argparse
import datetime
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path


def sha(data):return hashlib.sha256(data).hexdigest()


def sha_file(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def pack(root,archive,scope):
    assert root.resolve()==Path('/scratch/user/changze/lqr_experiments/results/x7-20261102')
    assert archive.parent.resolve()==Path('/scratch/user/changze/lqr_experiments/tmp/x7-20261102')
    assert re.fullmatch(r'[a-z0-9-]+\.tar\.gz',archive.name)
    assert not archive.exists() and not archive.with_suffix('.json').exists()
    prefixes={'formal':['resource-v1','formal-v1'], 'report':['report-v1']}[scope]
    if scope=='formal':
        proof=json.loads((root/'formal-v1/FORMAL_COMPLETE_v1.json').read_text())
        assert proof['status']=='COMPLETE_COVERAGE_COUNTS_SOURCES'
    else:
        assert json.loads((root/'report-v1/summary/verification.json').read_text())['status']=='COMPLETE'
    paths=[p for prefix in prefixes+['budget','submissions','logs']
           for p in (root/prefix).rglob('*') if p.is_file()]
    assert paths and len(paths)==len(set(paths))
    entries=[]
    with tarfile.open(archive,'w:gz',compresslevel=1) as tf:
        for path in sorted(paths):
            assert not path.is_symlink()
            payload=path.read_bytes();name=path.relative_to(root).as_posix()
            entries.append(dict(path=name,size=len(payload),sha256=sha(payload)))
            member=tarfile.TarInfo(name);member.size=len(payload)
            tf.addfile(member,io.BytesIO(payload))
    result=dict(status='SEALED',scope=scope,archive=archive.name,
                archive_sha256=sha_file(archive),files=entries,
                created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_sha256=sha_file(Path(__file__)),archive_hash_mode='STREAMED_1MiB',
                compression_level=1,
                metadata_note='Logs/submissions/accounting are snapshots during REPORT; final accounting is delivered separately.')
    archive.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='SEALED',files=len(entries),archive=str(archive),
                         archive_sha256=result['archive_sha256'])))


def unpack(archive,manifest,out):
    assert not out.exists(),'Never merge into an old delivery.'
    data=json.loads(manifest.read_text(encoding='utf-8-sig'))
    assert sha_file(archive)==data['archive_sha256']
    expected={r['path']:r for r in data['files']}
    with tarfile.open(archive,'r:gz') as tf:
        members=tf.getmembers()
        assert len(members)==len(expected) and {m.name for m in members}==set(expected)
        for member in members:
            assert member.isfile() and not Path(member.name).is_absolute()
            assert '..' not in Path(member.name).parts
            payload=tf.extractfile(member).read();record=expected[member.name]
            assert len(payload)==record['size'] and sha(payload)==record['sha256']
        out.mkdir(parents=True)
        for member in members:
            destination=out/member.name;destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(tf.extractfile(member).read())
    result=dict(status='VERIFIED_EXTRACTED',files=len(expected),archive_sha256=data['archive_sha256'])
    out.with_suffix('.verified.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['pack','unpack'])
    p.add_argument('--root',type=Path);p.add_argument('--scope',choices=['formal','report'])
    p.add_argument('--archive',required=True,type=Path);p.add_argument('--manifest',type=Path)
    p.add_argument('--out',type=Path);a=p.parse_args()
    if a.mode=='pack':pack(a.root,a.archive,a.scope)
    else:unpack(a.archive,a.manifest,a.out)
