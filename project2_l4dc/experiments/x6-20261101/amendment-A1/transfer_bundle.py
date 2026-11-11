"""Stdlib-only sealed transfer of explicitly selected X6 outputs."""
import argparse
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path


def sha(payload):return hashlib.sha256(payload).hexdigest()


def pack(root,archive,scope):
    assert root.resolve()==Path('/scratch/user/changze/lqr_experiments/results/x6-20261101')
    assert not archive.exists() and not archive.with_suffix('.json').exists()
    assert archive.parent.resolve()==Path('/scratch/user/changze/lqr_experiments/tmp/x6-20261101')
    assert re.fullmatch(r'[a-z0-9-]+\.tar\.gz',archive.name)
    if scope=='resource':
        paths=[p for prefix in ['X6a/resource','budget','submissions','logs']
               for p in (root/prefix).rglob('*') if p.is_file()]
        assert len(list((root/'X6a/resource').glob('task-*/DONE.json')))==8
    else:
        prefix='X6a/formal' if scope=='formal' else 'X6a/reports'
        paths=[p for p in (root/prefix).rglob('*') if p.is_file()]
        paths += [p for prefix in ['budget','submissions','logs']
                  for p in (root/prefix).rglob('*') if p.is_file()]
        if scope=='formal':assert len(list((root/'X6a/formal').glob('task-*/DONE.json')))==40
    assert paths
    entries=[]
    with tarfile.open(archive,'w:gz') as tf:
        for p in sorted(paths):
            assert not p.is_symlink()
            payload=p.read_bytes();name=p.relative_to(root).as_posix()
            entries.append(dict(path=name,size=len(payload),sha256=sha(payload)))
            info=tarfile.TarInfo(name);info.size=len(payload)
            tf.addfile(info,io.BytesIO(payload))
    result=dict(status='SEALED',scope=scope,archive=archive.name,
                archive_sha256=sha(archive.read_bytes()),files=entries)
    archive.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='SEALED',archive=str(archive),files=len(entries),
                         archive_sha256=result['archive_sha256'])))


def unpack(archive,manifest,out):
    assert not out.exists(),'Never merge into or replace an old delivery.'
    data=json.loads(manifest.read_text(encoding='utf-8-sig'))
    assert sha(archive.read_bytes())==data['archive_sha256']
    expected={row['path']:row for row in data['files']}
    with tarfile.open(archive,'r:gz') as tf:
        members=tf.getmembers()
        assert {m.name for m in members}==set(expected) and len(members)==len(expected)
        for m in members:
            assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
            payload=tf.extractfile(m).read()
            assert len(payload)==expected[m.name]['size'] and sha(payload)==expected[m.name]['sha256']
        out.mkdir(parents=True)
        tf.extractall(out,members=members)
    result=dict(status='VERIFIED_EXTRACTED',files=len(expected),archive_sha256=data['archive_sha256'])
    out.with_suffix('.verified.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('pack');a.add_argument('--root',type=Path,required=True)
    a.add_argument('--archive',type=Path,required=True)
    a.add_argument('--scope',choices=['resource','formal','report'],required=True)
    a=sub.add_parser('unpack');a.add_argument('--archive',type=Path,required=True)
    a.add_argument('--manifest',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.mode=='pack':pack(args.root,args.archive,args.scope)
    else:unpack(args.archive,args.manifest,args.out)
