"""Seal and verify the X9 delivery, preserving every source result file."""
import argparse
import datetime
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath

OUT = Path('/scratch/user/changze/lqr_experiments/results/x9-20261106')
TMP = Path('/scratch/user/changze/lqr_experiments/tmp/x9-20261106')


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def pack(archive):
    assert archive.parent.resolve() == TMP and archive.name == 'x9-report-v1.tar.gz'
    manifest_path = archive.with_suffix('.json')
    assert not archive.exists() and not manifest_path.exists()
    proof = json.loads((OUT/'report-v1/verification.json').read_text())
    render = json.loads((OUT/'report-v1/RENDER_COMPLETE_v1.json').read_text())
    coverage = json.loads((OUT/'formal-v1/FORMAL_COVERAGE_v1.json').read_text())
    assert proof['status'] == 'COMPLETE' and coverage['paired_paths'] == 1024
    assert render['status'] == 'SAVED_CSV_FIGURES_TABLES_RENDERED'
    for name, digest in dict(proof['files'], **render['files']).items():
        assert sha_file(OUT/'report-v1'/name) == digest
    prefixes = ['formal-v1', 'resource-v1', 'report-v1', 'budget', 'submissions', 'logs']
    paths = [p for prefix in prefixes for p in (OUT/prefix).rglob('*') if p.is_file()]
    assert len(paths) == len(set(paths)) and paths
    entries = []
    with tarfile.open(archive, 'x:gz', compresslevel=1) as tf:
        for path in sorted(paths):
            assert not path.is_symlink()
            name = path.relative_to(OUT).as_posix()
            payload = path.read_bytes()
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            tf.addfile(member, io.BytesIO(payload))
            entries.append(dict(path=name, bytes=len(payload), sha256=sha_bytes(payload)))
    proof = dict(status='SEALED_X9_COMPLETE_DELIVERY', files=entries,
                 created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 archive_sha256=sha_file(archive), source_sha256=sha_file(Path(__file__)),
                 archive_hash_mode='STREAMED_1MiB', compression_level=1,
                 note='Metadata/log/accounting snapshot during report; later settlement is delivered separately. No original result is deleted or moved.')
    with manifest_path.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status=proof['status'], members=len(entries),
                         archive=str(archive), archive_sha256=proof['archive_sha256'])), flush=True)


def unpack(archive, manifest_path, destination):
    assert not destination.exists(), 'Never merge into an earlier delivery.'
    proof = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert proof['status'] == 'SEALED_X9_COMPLETE_DELIVERY'
    assert sha_file(archive) == proof['archive_sha256']
    expected = {r['path']: r for r in proof['files']}
    assert len(expected) == len(proof['files'])
    with tarfile.open(archive, 'r:gz') as tf:
        members = tf.getmembers()
        assert len(members) == len(expected) and {m.name for m in members} == set(expected)
        for member in members:
            path = PurePosixPath(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            assert ':' not in member.name and '\\' not in member.name
            payload = tf.extractfile(member).read()
            assert len(payload) == expected[member.name]['bytes']
            assert sha_bytes(payload) == expected[member.name]['sha256']
        destination.mkdir(parents=True)
        for member in members:
            target = destination/member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(tf.extractfile(member).read())
    receipt = dict(status='VERIFIED_EXTRACTED_X9_DELIVERY', files=len(expected),
                   archive_sha256=proof['archive_sha256'], numerical_reanalysis=False)
    with destination.with_suffix('.verified.json').open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['pack', 'unpack'])
    p.add_argument('--archive', required=True, type=Path)
    p.add_argument('--manifest', type=Path)
    p.add_argument('--destination', type=Path)
    a = p.parse_args()
    if a.mode == 'pack':
        pack(a.archive)
    else:
        unpack(a.archive, a.manifest, a.destination)
