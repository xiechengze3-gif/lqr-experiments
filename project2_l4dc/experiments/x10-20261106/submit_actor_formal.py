"""Submit X10b once only after measured gates and all X9 compute completion."""
import datetime
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path
import actor_control as ops


def main():
    root = Path(__file__).resolve().parent
    assert root == ops.BASE/'releases/x10-20261106-b-formal-v1'
    ops.verify(root)
    config = json.loads((root/'formal-config.json').read_text())
    plan = json.loads((root/'formal-plan.json').read_text())
    approval = json.loads((root/'formal-approval.json').read_text())
    audit_path = root/'PILOT_AUDIT_v1.json'
    audit = json.loads(audit_path.read_text())
    review = root/'CLAUDE_TASK_FORMAL_authorized.md'
    assert ops.sha(review) == approval['review_sha256']
    assert approval['exact_authorization_quote'] in review.read_text(encoding='utf-8-sig')
    assert approval['all_fixed_gates_pass'] and plan['status'] == 'ALL_GATES_PASS_READY_TO_FREEZE'
    assert all(plan['checks'].values()) and plan['global_concurrency'] == 8
    assert plan['cumulative_predicted_actual_SU'] <= 160 and plan['cumulative_requested_upper_SU'] <= 200
    assert config['status'] == 'FORMAL_FROZEN' and config['family'] == 'S'
    assert ops.sha(root/'formal-config.json') == plan['formal_config_sha256'] == approval['formal_config_sha256']
    assert ops.sha(audit_path) == approval['pilot_audit_sha256'] == config['pilot_audit_sha256']
    assert config['formal_order'] == [g['id'] for g in plan['groups']]
    assert len(plan['groups']) == 8 and config['automatic_retries'] == 0
    deadline = datetime.datetime.fromisoformat(plan['deadline_utc'])
    now = datetime.datetime.now(datetime.timezone.utc)
    remaining_hours = plan['formal_serial_array_running_hours']+plan['report_critical_path_hours']+plan['queue_allowance_hours']
    assert now+datetime.timedelta(hours=remaining_hours) <= deadline, 'Deadline gate failed; report instead of submitting.'
    for name in {g['partition'] for g in plan['groups']}:
        assert name in ['short','medium']
        current = subprocess.check_output(['scontrol','show','partition',name],universal_newlines=True)
        fields = dict(re.findall(r'(\S+?)=(\S+)',current))
        assert fields['PartitionName'] == name and fields['State'] == 'UP'
        if 'partition_metadata_sha256' in plan:
            metadata_path = root/'PARTITION_METADATA_v1.json'
            assert ops.sha(metadata_path) == plan['partition_metadata_sha256']
            frozen_fields = json.loads(metadata_path.read_text())['partitions'][name]['fields']
            for key in ['Nodes','QoS','TRES','TRESBillingWeights','OverSubscribe','ExclusiveUser','MaxTime']:
                assert fields.get(key) == frozen_fields.get(key), 'Partition configuration changed; refresh plan.'
        else:
            assert name == 'short'
    x9proof = ops.require_x9_complete()
    pilot_chain = json.loads((ops.OUT/'submissions/PILOT_CHAIN_v1.json').read_text())
    assert len(pilot_chain['jobs']) == 3
    for item in pilot_chain['jobs']:
        assert all(row[1] == 'COMPLETED' for row in ops.job_states(item['job']))
        receipt = ops.OUT/'resource-v1'/item['role']/'PILOT_DONE.json'
        assert ops.sha(receipt) == audit['pilot_roles'][item['role']]['receipt_sha256']
    own_running = subprocess.check_output(['squeue', '--me', '-h', '-t', 'RUNNING,COMPLETING',
                                           '-o', '%i|%C|%j'], universal_newlines=True)
    assert not own_running.strip(), 'Other own compute still running; wait to preserve global<=8.'
    for meta in config['model_registry'].values():
        assert ops.sha(root/meta['path']) == meta['sha256']
    with (ops.OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = ops.OUT/'budget/ledger.json'
        assert ops.sha(path) == audit['ledger_sha256'], 'Ledger changed; reconcile before mutation.'
        ledger = json.loads(path.read_text())
        assert ledger['study'] == 'X10b'
        assert not any(r['stage'] == 'FORMAL' for r in ledger['submissions']), 'Never replay a partial chain.'
        assert abs(ledger['cumulative_requested_SU']-audit['pilot_requested_upper_SU']) < 1e-9
        assert ledger['actual_forecast_cap_SU'] == 160 and ledger['requested_upper_cap_SU'] == 200
        ledger['measured_forecast_actual_SU'] = plan['cumulative_predicted_actual_SU']
        ledger['completed_pilot_Slurm_elapsed_SU'] = audit['pilot_actual_elapsed_SU']
        ledger['formal_config_sha256'] = approval['formal_config_sha256']
        ledger['report_reserved_SU'] = 8
        dependency, jobs = None, []
        for index, group in enumerate(plan['groups']):
            assert group['cpus'] == 1 and group['memory_MiB'] == 2048 and group['tasks'] == 32
            assert group['partition'] in ['short','medium'] and group['wall_guard_pass']
            assert group['wall_minutes'] <= (120 if group['partition']=='short' else 1440)
            name = 'x10-20261106-b-formal-v1-g'+str(index).zfill(2)
            receipt = ops.OUT/'submissions'/(name+'.json')
            assert not receipt.exists()
            bound = group['requested_bound_SU']
            assert ledger['cumulative_requested_SU']+bound+8 <= 200+1e-9
            balance = subprocess.check_output(['myproject'], universal_newlines=True)
            account = next(line for line in balance.splitlines() if '|'+ops.ACCOUNT+'|' in line)
            assert float(account.split('|')[6].strip()) >= bound
            command = ['sbatch', '--parsable', '-A', ops.ACCOUNT, '-p', group['partition'],
                       '--ntasks=1', '--cpus-per-task=1', '--mem=2048M', '-t', str(group['wall_minutes']),
                       '--array=0-31%8', '-J', name, '-o', str(ops.OUT/'logs'/(name+'-%A_%a.out'))]
            if dependency is not None:
                command.append('--dependency=afterok:'+dependency)
            command.append(str(root/('formal-g'+str(index).zfill(2)+'.sbatch')))
            row = dict(id=name, stage='FORMAL', experiment='X10b', job=None,
                       status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY', command=command,
                       requested_bound_SU=bound, epoch=time.time(), group=group, dependency=dependency,
                       approval=approval, release=str(root), release_manifest_sha256=ops.sha(root/'SHA256SUMS'),
                       balance_snapshot=balance, x9_completion_proof=x9proof, automatic_retries=0)
            ops.save(receipt, row)
            ledger['submissions'].append(row)
            ledger['cumulative_requested_SU'] += bound
            ops.save(path, ledger)
            response = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            row.update(returncode=response.returncode, stdout=response.stdout, stderr=response.stderr)
            if response.returncode == 0 and re.fullmatch(r'\d+(;[^\s]+)?', response.stdout.strip()):
                row.update(job=response.stdout.strip().split(';')[0], status='SUBMITTED')
            else:
                row['status'] = 'RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
            ops.save(receipt, row)
            ledger['submissions'][-1] = row
            ops.save(path, ledger)
            print(json.dumps(dict(status=row['status'], group=group['id'], job=row['job'],
                                  dependency=dependency, requested_bound_SU=bound)), flush=True)
            assert row['status'] == 'SUBMITTED'
            dependency = row['job']
            jobs.append(dict(id=name, group=group['id'], job=dependency))
        assert abs(ledger['cumulative_requested_SU']+8-plan['cumulative_requested_upper_SU']) < 1e-9
        target = ops.OUT/'submissions/FORMAL_CHAIN_v1.json'
        assert not target.exists()
        result = dict(status='FORMAL_CHAIN_SUBMITTED', jobs=jobs,
                      cumulative_requested_SU=ledger['cumulative_requested_SU'], report_reserve_SU=8,
                      actual_forecast_SU=plan['cumulative_predicted_actual_SU'],
                      actual_forecast_cap_SU=160, requested_upper_cap_SU=200,
                      global_concurrency=8, afterok_serial_arrays=True, automatic_retries=0)
        ops.save(target, result)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
