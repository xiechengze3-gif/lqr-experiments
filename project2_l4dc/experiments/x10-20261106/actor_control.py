"""New X10b metadata-only deployment and durable submission helpers."""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

BASE = Path('/scratch/user/changze/lqr_experiments')
OUT = BASE/'results/x10-20261106/X10b'
ACCOUNT = '132685389143'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data, indent=2)+'\n')
    temp.replace(path)


def verify(root):
    for line in (root/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert sha(root/name) == digest, name


def job_states(job):
    raw = subprocess.check_output(['sacct', '-X', '--array', '-j', job, '-n', '-P',
                                   '--format=JobID,State'], universal_newlines=True)
    rows = [line.split('|')[:2] for line in raw.splitlines() if line.strip()]
    assert rows and all('.' not in r[0] for r in rows)
    return rows


def require_x9_complete():
    path = BASE/'results/x9-20261106/budget/ledger.json'
    ledger = json.loads(path.read_text())
    assert any(r['stage'] == 'REPORT' for r in ledger['submissions']), 'X9 report has not been submitted.'
    proof = []
    for row in ledger['submissions']:
        assert row['job'], 'Reconcile an uncertain X9 submission first.'
        states = job_states(row['job'])
        assert all(s[1] == 'COMPLETED' for s in states), 'Wait for all X9 compute, including REPORT.'
        proof.append(dict(stage=row['stage'], job=row['job'], states=states))
    return proof


def deploy(name, digest):
    assert name in ['x10-20261106-b-formal-v1', 'x10-20261106-b-report-v1']
    archive = BASE/'tmp/x10-20261106'/(name+'.tar.gz')
    assert sha(archive) == digest
    target = BASE/'releases'/name
    assert not target.exists(), 'Reconcile the existing release; do not overwrite.'
    with tarfile.open(archive, 'r:gz') as tf:
        members = tf.getmembers()
        names = [m.name for m in members]
        assert len(names) == len(set(names))
        assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
                   for m in members)
        target.mkdir()
        tf.extractall(target, members=members)
    verify(target)
    print(json.dumps(dict(status='DEPLOYED_VERIFIED', release=str(target), archive_sha256=digest)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['deploy'])
    parser.add_argument('name')
    parser.add_argument('sha256')
    args = parser.parse_args()
    deploy(args.name, args.sha256)
