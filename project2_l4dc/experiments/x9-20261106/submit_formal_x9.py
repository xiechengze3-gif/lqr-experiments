"""Submit the approved X9 formal chain once; dependencies enforce global<=8."""
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path
import remote_x9 as ops


def main():
    root = Path(__file__).resolve().parent
    assert root.parent == ops.BASE/'releases'
    ops.verify(root)
    config = json.loads((root/'formal-config.json').read_text())
    plan = json.loads((root/'formal-plan.json').read_text())
    approval = json.loads((root/'formal-approval.json').read_text())
    assert config['status'] == 'FORMAL_FROZEN' and len(plan['groups']) == 12
    assert ops.sha(root/'CLAUDE_TASK_FORMAL_accepted.md') == approval['review_sha256']
    quote = approval['exact_accepted_quote']
    assert all(word in quote for word in ['X9', 'PILOT', 'ACCEPTED'])
    assert quote in (root/'CLAUDE_TASK_FORMAL_accepted.md').read_text(encoding='utf-8-sig')
    assert approval['formal_config_sha256'] == ops.sha(root/'formal-config.json')
    assert plan['formal_config_sha256'] == ops.sha(root/'formal-config.json')
    assert plan['cumulative_requested_upper_SU'] <= 50 and plan['global_concurrency'] == 8
    assert all(g['wall_guard_pass'] and g['cpus'] == 1 and g['memory_MiB'] == 2048 for g in plan['groups'])
    states = subprocess.check_output(['sacct', '-X', '--array', '-j', '20413460', '-n', '-P',
                                      '--format=JobID,State'], universal_newlines=True)
    state_rows = [line.split('|') for line in states.splitlines() if line.strip()]
    assert len(state_rows) == 4 and all(r[1] == 'COMPLETED' for r in state_rows)
    for registry in config['model_registry'].values():
        for meta in registry.values():
            path = Path(meta['path'])
            assert str(path).startswith(str(ops.OUT/'resource-v1')+'/')
            assert ops.sha(path) == meta['sha256']
    with (ops.OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger_path = ops.OUT/'budget/ledger.json'
        ledger = json.loads(ledger_path.read_text())
        assert ledger['cap_requested_SU'] == 50
        assert ledger['cumulative_requested_SU'] == 1
        assert not any(r['stage'] == 'FORMAL' for r in ledger['submissions']), 'Reconcile; never replay the chain.'
        completed = []
        dependency = None
        for index, group in enumerate(plan['groups']):
            name = f'x9-20261106-formal-v1-g{index:02d}'
            receipt = ops.OUT/'submissions'/(name+'.json')
            assert not receipt.exists()
            bound = group['requested_bound_SU']
            assert ledger['cumulative_requested_SU']+bound+2 <= 50
            balance = subprocess.check_output(['myproject'], universal_newlines=True)
            account = next(line for line in balance.splitlines() if '|'+ops.ACCOUNT+'|' in line)
            assert float(account.split('|')[6].strip()) >= bound
            command = ['sbatch', '--parsable', '-A', ops.ACCOUNT, '-p', 'short',
                       '--ntasks=1', '--cpus-per-task=1', '--mem=2048M',
                       '-t', str(group['wall_minutes']), '--array=0-31%8', '-J', name,
                       '-o', str(ops.OUT/'logs'/(name+'-%A_%a.out'))]
            if dependency is not None:
                command.append('--dependency=afterok:'+dependency)
            command.append(str(root/f'formal-g{index:02d}.sbatch'))
            row = dict(id=name, stage='FORMAL', experiment='X9', job=None,
                       status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY', command=command,
                       requested_bound_SU=bound, epoch=time.time(), group=group,
                       dependency=dependency, approval=approval, release=str(root),
                       release_manifest_sha256=ops.sha(root/'SHA256SUMS'),
                       balance_snapshot=balance, automatic_retries=0)
            ops.save(receipt, row)
            ledger['submissions'].append(row)
            ledger['cumulative_requested_SU'] += bound
            ops.save(ledger_path, ledger)
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            row.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            if result.returncode == 0 and re.fullmatch(r'\d+(;[^\s]+)?', result.stdout.strip()):
                row.update(job=result.stdout.strip().split(';')[0], status='SUBMITTED')
            else:
                row['status'] = 'RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
            ops.save(receipt, row)
            ledger['submissions'][-1] = row
            ops.save(ledger_path, ledger)
            print(json.dumps(dict(id=name, status=row['status'], job=row['job'], group=group['id'],
                                  dependency=dependency, requested_bound_SU=bound)), flush=True)
            assert row['status'] == 'SUBMITTED'
            dependency = row['job']
            completed.append(dict(id=name, job=dependency, group=group['id']))
        assert abs(ledger['cumulative_requested_SU']-47.93333333333334) < 1e-9
        summary = dict(status='FORMAL_CHAIN_SUBMITTED', jobs=completed,
                       cumulative_requested_SU=ledger['cumulative_requested_SU'],
                       report_reserve_SU=2, cap_SU=50, global_concurrency=8,
                       afterok_serial_arrays=True, automatic_retries=0)
        target = ops.OUT/'submissions/FORMAL_CHAIN_v1.json'
        assert not target.exists()
        ops.save(target, summary)
        print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
