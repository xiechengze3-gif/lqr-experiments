"""Metadata-only corrected-pilot deployment/dispatch with preserved history."""
import argparse
import fcntl
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path

BASE = Path('/scratch/user/changze/lqr_experiments')
OUT = BASE/'results/x10-20261106/X10b'
ACCOUNT = '132685389143'
NAME = 'x10-20261106-b-pilot-v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data, indent=2)+'\n')
    temp.replace(path)


def new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def verify(root):
    seen = set()
    for line in (root/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert name not in seen and not Path(name).is_absolute() and '..' not in Path(name).parts
        seen.add(name)
        assert sha(root/name) == digest, name


def deploy(digest):
    archive = BASE/'tmp/x10-20261106'/(NAME+'.tar.gz')
    assert sha(archive) == digest
    target = BASE/'releases'/NAME
    assert not target.exists(), 'Reconcile an existing release, never overwrite.'
    with tarfile.open(archive, 'r:gz') as tf:
        members = tf.getmembers()
        assert len(members) == len({member.name for member in members})
        assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
        target.mkdir()
        tf.extractall(target, members=members)
    verify(target)
    print(json.dumps(dict(status='DEPLOYED_VERIFIED', release=str(target), archive_sha256=digest)))


def pilot(root):
    assert root.resolve() == BASE/'releases'/NAME
    verify(root)
    sys.path.insert(0, str(root))
    import preflight_correction_v2 as checks
    approval = json.loads((root/'approval-v2.json').read_text())
    assert checks.sha(root/'actor-config-protocol-v2.json') == approval['config_sha256']
    with (OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        proof = checks.check_before_submission()
        assert proof['status'] == 'PASS_CORRECTED_PILOT_INPUTS_AND_PRESERVED_HISTORY'
        own_running = subprocess.check_output(['squeue', '--me', '-h', '-t', 'RUNNING,COMPLETING', '-o', '%i|%C|%j'], text=True)
        assert not own_running.strip(), 'Wait for other own compute to preserve global<=8.'
        ledger_path = OUT/'budget/ledger.json'
        old_bytes = ledger_path.read_bytes()
        assert sha(ledger_path) == proof['prior_ledger_sha256']
        ledger = json.loads(old_bytes)
        old_rows = list(ledger['submissions'])
        assert old_rows == proof['prior_ledger_submissions']
        new(OUT/'budget/PRIOR_PILOT_LEDGER_v1_before_correction.json', old_bytes)
        preflight_path = OUT/'submissions/PILOT_INPUT_PREFLIGHT_v2.json'
        new(preflight_path, (json.dumps(proof, indent=2)+'\n').encode())
        dependency, jobs = None, []
        for role, minutes in [('equivalence', 10), ('NPG', 120), ('PI', 120)]:
            name = NAME+'-'+role.lower()
            receipt = OUT/'submissions'/(name+'.json')
            assert not receipt.exists()
            bound = minutes/60
            assert ledger['cumulative_requested_SU']+bound <= 8+1/3+1e-9
            balance = subprocess.check_output(['myproject'], text=True)
            account = next(line for line in balance.splitlines() if '|'+ACCOUNT+'|' in line)
            assert float(account.split('|')[6].strip()) >= bound
            command = ['sbatch', '--parsable', '-A', ACCOUNT, '-p', 'short',
                       '--ntasks=1', '--cpus-per-task=1', '--mem=2048M', '-t', str(minutes),
                       '--array=0-0%1', '-J', name, '-o', str(OUT/'logs'/(name+'-%A_%a.out'))]
            if dependency:
                command.append('--dependency=afterok:'+dependency)
            command.append(str(root/('pilot-'+role+'.sbatch')))
            row = dict(id=name, role=role, stage='PILOT', experiment='X10b', job=None,
                       status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY', command=command,
                       requested_bound_SU=bound, dependency=dependency, epoch=time.time(),
                       approval=approval, release=str(root), release_manifest_sha256=sha(root/'SHA256SUMS'),
                       balance_snapshot=balance, resource_namespace='resource-v2',
                       preflight_sha256=sha(preflight_path), automatic_retries=0)
            save(receipt, row)
            ledger['submissions'].append(row)
            ledger['cumulative_requested_SU'] += bound
            assert ledger['submissions'][:3] == old_rows
            save(ledger_path, ledger)
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            row.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            if result.returncode == 0 and re.fullmatch(r'\d+(;[^\s]+)?', result.stdout.strip()):
                row.update(job=result.stdout.strip().split(';')[0], status='SUBMITTED')
            else:
                row['status'] = 'RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
            save(receipt, row)
            ledger['submissions'][-1] = row
            assert ledger['submissions'][:3] == old_rows
            save(ledger_path, ledger)
            print(json.dumps(dict(status=row['status'], role=role, job=row['job'], dependency=dependency,
                                  requested_bound_SU=bound)), flush=True)
            assert row['status'] == 'SUBMITTED'
            if role == 'equivalence':
                dependency = row['job']
            jobs.append(dict(role=role, job=row['job']))
        assert len(ledger['submissions']) == 6
        assert abs(ledger['cumulative_requested_SU']-8-1/3) < 1e-9
        chain = dict(status='AUTHORIZED_CORRECTED_PILOT_CHAIN_SUBMITTED', jobs=jobs,
                     prior_jobs=list(checks.FAILED_HISTORY), original_history_preserved=True,
                     prior_actual_elapsed_SU=57/3600, requested_additional_upper_SU=4+1/6,
                     requested_cumulative_pilot_upper_SU=ledger['cumulative_requested_SU'],
                     preflight_sha256=sha(preflight_path), formal_submitted=False,
                     no_NPG_resampling=True, automatic_retries=0)
        new(OUT/'submissions/PILOT_CHAIN_v2.json', (json.dumps(chain, indent=2)+'\n').encode())
        print(json.dumps(chain), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    d = sub.add_parser('deploy')
    d.add_argument('sha256')
    p = sub.add_parser('pilot')
    p.add_argument('root', type=Path)
    args = parser.parse_args()
    if args.mode == 'deploy':
        deploy(args.sha256)
    else:
        pilot(args.root)
