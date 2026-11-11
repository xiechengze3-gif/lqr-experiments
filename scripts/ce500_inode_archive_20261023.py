"""Losslessly consolidate completed old experiments; never discard evidence.

Only the three explicitly named completed experiments and their policy,
checkpoint, and estimate folders are eligible. Every archived byte is hashed
and read back before any original file is unlinked. No active experiment is
eligible. The JSON index supports restoring the original relative paths.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

BASE = Path('/scratch/user/changze/lqr_experiments/results')
NAMES = ['ce500-matched-gap-20261019', 'ce500-random-a-20261020',
         'ce-matched-initial-gap-20261018']
SUBDIRS = ['policies', 'checkpoints', 'estimates']


def sha_stream(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
        h.update(block)
    return h.hexdigest()


def sha(path):
    with path.open('rb') as f:
        return sha_stream(f)


def write(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    tmp.replace(path)


def main():
    assert os.environ.get('SLURM_JOB_ID'), 'Use a bounded maintenance allocation'
    active = subprocess.check_output(['squeue', '-u', 'changze', '-h', '-o', '%j'], text=True)
    assert not any(x in active for x in NAMES)
    for name in NAMES:
        root = (BASE / name).resolve()
        assert root.parent == BASE.resolve()
        report = json.loads((root / 'report-confirm/summary.json').read_text())
        assert report['status'] == 'complete' and len(report['seeds']) == 30
        archive = root / 'inode-preserved-20261023.tar'
        index = root / 'INODE_ARCHIVE_20261023.json'
        assert not archive.exists() and not index.exists(), 'Inspect prior archive receipt before replay'
        files = []
        for sub in SUBDIRS:
            folder = root / sub
            if not folder.exists():
                continue
            for path in sorted(folder.rglob('*')):
                assert not path.is_symlink()
                if path.is_file():
                    assert path.resolve().is_relative_to(folder.resolve())
                    files.append(path)
        assert files
        total = sum(p.stat().st_size for p in files)
        stats = os.statvfs(root)
        assert stats.f_bavail * stats.f_frsize > total + 10 * 1024**3
        entries = []
        with tarfile.open(archive, 'w') as tf:
            for p in files:
                rel = str(p.relative_to(root))
                entries.append(dict(path=rel, size=p.stat().st_size, sha256=sha(p)))
                tf.add(p, arcname=rel, recursive=False)
        with tarfile.open(archive, 'r') as tf:
            members = tf.getmembers()
            assert len(members) == len(entries)
            for member, entry in zip(members, entries):
                assert member.isfile() and member.name == entry['path'] and member.size == entry['size']
                with tf.extractfile(member) as f:
                    assert sha_stream(f) == entry['sha256']
        receipt = dict(status='archive_verified_before_consolidation', original_root=str(root),
                       archive=str(archive), archive_sha256=sha(archive), entries=entries,
                       files=len(files), bytes=total, slurm_job_id=os.environ['SLURM_JOB_ID'],
                       restore='Verify archive_sha256; extract tar entries at original_root to restore original paths',
                       report_kept_in_place=True, raw_kept_in_place=True, epoch=time.time())
        write(index, receipt)
        for p, entry in zip(files, entries):
            assert sha(p) == entry['sha256'], 'Source changed after archive verification'
            p.unlink()
        for sub in SUBDIRS:
            folder = root / sub
            if folder.exists():
                for d, dirs, fs in os.walk(folder, topdown=False):
                    assert not fs
                    Path(d).rmdir()
        receipt.update(status='PASS', original_files_consolidated=True)
        write(index, receipt)
        print(json.dumps({k: receipt[k] for k in ['status', 'original_root', 'files', 'bytes', 'archive_sha256']}), flush=True)
    print(subprocess.check_output(['df', '-i', str(BASE)], text=True), flush=True)


if __name__ == '__main__':
    main()
