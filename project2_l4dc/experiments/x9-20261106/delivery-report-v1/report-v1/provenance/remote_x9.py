"""Stdlib deployment and exactly-once X9 resource submission, no scientific work."""
import argparse
import fcntl
import hashlib
import json
import re
import subprocess
import tarfile
import time
from pathlib import Path

BASE = Path('/scratch/user/changze/lqr_experiments')
OUT = BASE/'results/x9-20261106'
ACCOUNT = '132685389143'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj, indent=2)+'\n')
    temp.replace(path)


def verify(root):
    for line in (root/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert sha(root/name) == digest, name


def deploy(name, digest):
    assert re.fullmatch(r'x9-20261106-[a-z0-9-]+', name)
    archive = BASE/'tmp/x9-20261106'/(name+'.tar.gz')
    assert sha(archive) == digest
    root = BASE/'releases'/name
    assert not root.exists(), 'Inspect existing deployment; do not overwrite.'
    with tarfile.open(archive, 'r:gz') as tf:
        members = tf.getmembers()
        assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
        root.mkdir()
        tf.extractall(root, members=members)
    verify(root)
    print(json.dumps(dict(status='DEPLOYED_VERIFIED', root=str(root), archive_sha256=digest)))


def resource(root):
    root = root.resolve()
    assert root.parent == BASE/'releases'
    verify(root)
    approval = json.loads((root/'approval.json').read_text())
    review = root/'CLAUDE_TASK_GO.md'
    assert sha(review) == approval['review_sha256']
    assert approval['exact_go_heading'] in review.read_text()
    assert '**Cap: 50 SU**' in review.read_text()
    config = json.loads((root/'config-protocol-v1.json').read_text())
    assert config['status'] == 'PROTOCOL_FROZEN' and config['cap_SU'] == 50
    assert len(config['pilot_cases']) == 4
    plan = dict(id='x9-20261106-resource-v1', stage='PILOT', tasks=4,
                cpus=1, memory_MiB=2048, wall_minutes=15, concurrency=4)
    bound = 1.
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipt = OUT/'submissions'/(plan['id']+'.json')
        assert not receipt.exists(), 'Receipt exists; reconcile, never replay.'
        ledger_path = OUT/'budget/ledger.json'
        ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else dict(
            study='X9', cap_requested_SU=50., cumulative_requested_SU=0., submissions=[])
        assert ledger['cap_requested_SU'] == 50
        assert ledger['cumulative_requested_SU'] + bound <= 50
        assert not any(r['stage'] == 'PILOT' for r in ledger['submissions'])
        balance = subprocess.check_output(['myproject'], universal_newlines=True)
        line = next(x for x in balance.splitlines() if '|'+ACCOUNT+'|' in x)
        assert float(line.split('|')[6].strip()) >= 50
        own_queue = subprocess.check_output(['squeue', '-u', 'changze', '-h', '-o', '%i|%j|%T'], universal_newlines=True)
        assert plan['id'] not in own_queue, 'A same-name job already exists; reconcile.'
        logs = OUT/'logs'
        logs.mkdir(exist_ok=True)
        command = ['sbatch', '--parsable', '-A', ACCOUNT, '-p', 'short',
                   '--ntasks=1', '--cpus-per-task=1', '--mem=2048M', '-t', '15',
                   '--array=0-3%4', '-J', plan['id'],
                   '-o', str(logs/(plan['id']+'-%A_%a.out')), str(root/'run.sbatch')]
        row = dict(id=plan['id'], stage='PILOT', experiment='X9', job=None,
                   status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY', requested_bound_SU=bound,
                   plan=plan, command=command, epoch=time.time(), approval=approval,
                   release=str(root), release_manifest_sha256=sha(root/'SHA256SUMS'),
                   balance_snapshot=balance, own_queue_snapshot=own_queue, automatic_retries=0)
        save(receipt, row)
        ledger['submissions'].append(row)
        ledger['cumulative_requested_SU'] += bound
        save(ledger_path, ledger)
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        row.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        if result.returncode == 0 and re.fullmatch(r'\d+(;[^\s]+)?', result.stdout.strip()):
            row.update(job=result.stdout.strip().split(';')[0], status='SUBMITTED')
        else:
            row['status'] = 'RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
        save(receipt, row)
        ledger['submissions'][-1] = row
        save(ledger_path, ledger)
        print(json.dumps(row))
        assert row['status'] == 'SUBMITTED'


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='mode', required=True)
    d = sub.add_parser('deploy')
    d.add_argument('name')
    d.add_argument('sha256')
    s = sub.add_parser('resource')
    s.add_argument('root', type=Path)
    a = p.parse_args()
    if a.mode == 'deploy':
        deploy(a.name, a.sha256)
    else:
        resource(a.root)
