"""Preserve old, inactive LQR logs in verified small archives to free inodes."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

BASE = Path('/scratch/user/changze/lqr_experiments/results')
KEEP = {'ce500-common-constants-20261022', 'ce500-common-rank-extension-20261023-v2',
        'ce500-r300-fine-20261023-v1'}


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write(p, value):
    temp = p.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(p)


def main():
    assert os.environ.get('SLURM_JOB_ID')
    index = BASE / 'INODE_LOG_ARCHIVE_20261023.json'
    assert not index.exists(), 'Inspect archive receipt before replay'
    roots = [p.resolve() for p in BASE.iterdir() if p.is_dir() and p.name not in KEEP]
    jobs = subprocess.check_output(['squeue', '-u', 'changze', '-h', '-o', '%i'], text=True).split()
    for job in jobs:
        detail = subprocess.check_output(['scontrol', 'show', 'job', job], text=True)
        assert not any(str(root) + '/logs/' in detail for root in roots), 'Log is used by an active/pending job'
    files = []
    for root in roots:
        assert root.parent == BASE.resolve()
        for p in sorted((root / 'logs').rglob('*')):
            assert not p.is_symlink()
            if p.is_file():
                assert p.resolve().is_relative_to(root / 'logs')
                assert p.stat().st_size < 10 * 1024**2
                files.append(p)
    assert len(files) >= 4000
    receipt = dict(status='running', slurm_job_id=os.environ['SLURM_JOB_ID'],
                   scope='Only inactive historical LQR log files; all numerical artifacts kept in place',
                   restore='Extract each verified tar at original_root to restore exact log paths',
                   original_root=str(BASE), original_files=len(files), parts=[], epoch=time.time())
    write(index, receipt)
    for batch in range(0, len(files), 1000):
        archive = BASE / f'inode-logs-preserved-20261023-part{batch//1000:02d}.tar'
        assert not archive.exists()
        entries = []
        with tarfile.open(archive, 'w') as tf:
            for p in files[batch:batch+1000]:
                data = p.read_bytes()
                entry = dict(path=str(p.relative_to(BASE)), sha256=sha_bytes(data), size=len(data))
                entries.append(entry)
                info = tarfile.TarInfo(entry['path'])
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        with tarfile.open(archive, 'r') as tf:
            members = tf.getmembers()
            assert len(members) == len(entries)
            for member, entry in zip(members, entries):
                assert member.isfile() and member.name == entry['path'] and member.size == entry['size']
                assert sha_bytes(tf.extractfile(member).read()) == entry['sha256']
        part = dict(status='verified_before_consolidation', archive=str(archive),
                    archive_sha256=sha_bytes(archive.read_bytes()), entries=entries)
        receipt['parts'].append(part)
        write(index, receipt)
        for entry in entries:
            path = BASE / entry['path']
            assert path.resolve().is_relative_to(BASE.resolve())
            assert sha_bytes(path.read_bytes()) == entry['sha256']
            path.unlink()
        part['status'] = 'PASS'
        write(index, receipt)
        print(json.dumps(dict(part=batch//1000, status='PASS', preserved_log_files=len(entries))), flush=True)
    receipt['status'] = 'PASS'
    write(index, receipt)
    print(subprocess.check_output(['df', '-i', str(BASE)], text=True), flush=True)


if __name__ == '__main__':
    main()
