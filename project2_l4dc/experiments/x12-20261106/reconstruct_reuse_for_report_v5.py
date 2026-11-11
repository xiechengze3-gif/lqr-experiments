"""Reconstruct the canonical reuse tar on compute-local tmp from sealed evidence.

Original transit evidence is read-only; this avoids a second large home copy.
The new tar must match the already-verified E tar byte for byte.
"""
import tarfile
from pathlib import Path

from virtual_task_store_v2 import digest, file_sha


EVIDENCE = Path('/home/changze/lqr-x12-failure-transit-20261107-v1/x12-failed-formal-v1.tar.gz')
EVIDENCE_SHA = '051d016a353fc4c743e9f7aee5ae6f8ddb0d3a17212d13c1fcd8081f65f9b4f2'
PREFIX = 'results/formal-v1/'


def reproduce(source, out, manifest):
    assert file_sha(source) == manifest['old_failed_evidence_archive_sha256']
    assert not out.exists()
    # The E packer used USTAR in task/rung/lexical filename order. Place each
    # header and payload at its canonical offset while streaming the source once.
    index = {}
    offset = 0
    for path in manifest['reused_paths']:
        for f in path['files']:
            name = f['path']
            assert PREFIX + name not in index
            index[PREFIX + name] = (offset, f)
            offset += 512 + ((f['bytes'] + 511) // 512) * 512
    length = ((offset + 1024 + 10239) // 10240) * 10240
    assert length == manifest['archive_bytes']
    found = set()
    with out.open('xb') as target, tarfile.open(source, 'r|gz') as src:
        target.truncate(length)  # Includes the required zero padding.
        for member in src:
            if member.name not in index:
                continue
            position, f = index[member.name]
            assert member.isfile() and member.size == f['bytes'] and member.name not in found
            data = src.extractfile(member).read()
            assert len(data) == f['bytes'] and digest(data) == f['sha256']
            info = tarfile.TarInfo(f['path'])
            info.size, info.mode = len(data), 0o600
            header = info.tobuf(format=tarfile.USTAR_FORMAT)
            assert len(header) == 512
            target.seek(position)
            target.write(header)
            target.write(data)
            found.add(member.name)
    assert found == set(index) and out.stat().st_size == length
    h = file_sha(out)
    assert h == manifest['archive_sha256'], 'Recreated old raw archive must match E bytes exactly.'
    return dict(members=len(found), archive_sha256=h, archive_bytes=length,
                source_archive_sha256=manifest['old_failed_evidence_archive_sha256'], home_copy_created=False)
