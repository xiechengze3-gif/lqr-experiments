"""Resolve the pre-registered X10b resource plan after its pilot; never submits."""
import argparse
import ast
import copy
import datetime
import hashlib
import io
import json
import math
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CONTROL = HERE/'actor-correction-controls-v2'
CHANNEL = HERE.parents[1]
SOURCE = HERE/'actor-pilot-release-v2'
NAME = 'x10-20261106-b-formal-v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def payload(value):
    return (json.dumps(value, indent=2)+'\n').encode()


def time_minutes(value):
    day, clock = value.split('-',1) if '-' in value else ('0',value)
    hour, minute, second = map(int,clock.split(':'))
    return int(day)*1440+hour*60+minute+second/60


def select_partition(minutes, metadata):
    if metadata is None:
        return 'short' if minutes <= 120 else None
    assert metadata['status'] == 'READ_ONLY_GRACE_MATCHED_CPU_PARTITIONS'
    assert metadata['same_nodes_qos_billing_configuration']
    partitions = metadata['partitions']
    for key in ['Nodes','QoS','TRES','TRESBillingWeights','OverSubscribe','ExclusiveUser']:
        assert partitions['short']['fields'].get(key) == partitions['medium']['fields'].get(key)
    for name in ['short','medium']:
        fields = partitions[name]['fields']
        assert fields['PartitionName'] == name and fields['State'] == 'UP'
        if minutes <= time_minutes(fields['MaxTime']):
            return name
    return None


def resolve(config, audit, now, partition_metadata=None):
    assert audit['status'] == 'PASS_PILOT_SOURCES_COUNTS_RSS_SLURM'
    assert audit['no_performance_readout'] and audit['formal_numerical_work'] == 0
    assert set(audit['pilot_roles']) == {'equivalence', 'NPG', 'PI'}
    checked = datetime.datetime.fromisoformat(audit['checked_utc'].replace('Z', '+00:00'))
    assert 0 <= (now-checked).total_seconds() <= 900, 'Obtain a fresh read-only pilot audit.'
    assert audit['pilot_actual_elapsed_SU'] >= 0
    assert abs(audit['pilot_requested_upper_SU']-8-1/3) < 1e-9
    assert audit['audit_version'] == 2 and audit['no_NPG_resampling']
    if partition_metadata:
        partition_checked = datetime.datetime.fromisoformat(partition_metadata['checked_utc'].replace('Z','+00:00'))
        assert 0 <= (now-partition_checked).total_seconds() <= 86400, 'Refresh read-only partition metadata.'
    profiles = {(r['n'], r['algorithm']): r for r in config['historical_resource_profile']}
    groups = []
    for group in config['formal_groups']:
        n, algorithm = group['n'], group['runs'][0]['algorithm']
        measured = audit['pilot_roles'][algorithm]['receipt']['body_seconds']
        assert math.isfinite(measured) and measured > 0
        old = profiles[n, algorithm]['old_full_max_seconds']
        old72 = profiles[72, algorithm]['old_full_max_seconds']
        floor, scaled = old*.66796875, measured*old/old72
        body = max(floor, scaled)
        minutes = math.ceil((1.2*body+30)/60)
        groups.append(dict(id=group['id'], n=n, algorithm=algorithm, tasks=32,
                           cpus=1, memory_MiB=2048, measured_n72_body_seconds=measured,
                           historical_floor_seconds=floor, measured_scaled_seconds=scaled,
                           body_seconds=body, wall_minutes=minutes, partition=select_partition(minutes, partition_metadata),
                           wall_guard_pass=minutes*60 >= 1.2*body+30,
                           requested_bound_SU=32*minutes/60))
    formal_actual = 32*sum(g['body_seconds'] for g in groups)/3600
    formal_upper = sum(g['requested_bound_SU'] for g in groups)
    actual_total = formal_actual+audit['pilot_actual_elapsed_SU']+8
    upper_total = formal_upper+audit['pilot_requested_upper_SU']+8
    # Serial arrays, four waves each. Four audits may run together, then aggregate.
    formal_wall = sum(4*g['wall_minutes']/60 for g in groups)
    report_wall, queue_allowance = 3.5, 6.
    finish = now+datetime.timedelta(hours=formal_wall+report_wall+queue_allowance)
    deadline = datetime.datetime(2026, 11, 9, 0, 0, tzinfo=datetime.timezone.utc)
    checks = dict(actual_forecast_under_160=actual_total <= 160,
                  requested_upper_under_200=upper_total <= 200,
                  all_wall_guards_pass=all(g['wall_guard_pass'] for g in groups),
                  partitions_resolved=all(g['partition'] is not None for g in groups),
                  deadline_feasible=finish <= deadline,
                  x9_all_compute_including_report_complete=audit['x9_all_compute_including_report_complete'])
    return dict(status='ALL_GATES_PASS_READY_TO_FREEZE' if all(checks.values()) else 'STOP_OR_WAIT_GATE_NOT_SATISFIED',
                created_utc=now.isoformat(), groups=groups, checks=checks,
                formal_predicted_actual_SU=formal_actual, formal_requested_upper_SU=formal_upper,
                completed_pilot_Slurm_elapsed_SU=audit['pilot_actual_elapsed_SU'],
                pilot_requested_upper_SU=audit['pilot_requested_upper_SU'], report_reserve_SU=8,
                cumulative_predicted_actual_SU=actual_total, cumulative_requested_upper_SU=upper_total,
                actual_forecast_cap_SU=160, requested_upper_cap_SU=200,
                global_concurrency=8, formal_serial_array_running_hours=formal_wall,
                report_critical_path_hours=report_wall, queue_allowance_hours=queue_allowance,
                conditional_finish_utc=finish.isoformat(), deadline_utc=deadline.isoformat(),
                automatic_retries=0, no_outcome_selection=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pilot-audit', type=Path, required=True)
    parser.add_argument('--expected-review-sha256', required=True)
    parser.add_argument('--partition-metadata', type=Path)
    args = parser.parse_args()
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review) == args.expected_review_sha256
    quote = 'Proceed to FORMAL automatically iff all pilot checks pass'
    assert quote in review.decode('utf-8-sig')
    config_bytes = (SOURCE/'actor-config-protocol-v2.json').read_bytes()
    config = json.loads(config_bytes)
    dependency_bytes = (HERE/'OLD_REMOTE_DEPENDENCY_AUDIT_v2.json').read_bytes()
    dependency = json.loads(dependency_bytes)
    assert dependency['status'] == 'PASS_FORMAL_REPORT_NO_OLD_REMOTE_RESULT_DEPENDENCY'
    for name, digest in dependency['runtime_sources'].items():
        assert sha((HERE/name).read_bytes()) == digest, name
    for name, digest in dependency['packaged_old_inputs'].items():
        assert sha((SOURCE/name).read_bytes()) == digest, name
    audit_bytes = args.pilot_audit.read_bytes()
    audit = json.loads(audit_bytes)
    assert audit['config_sha256'] == sha(config_bytes)
    now = datetime.datetime.now(datetime.timezone.utc)
    partition_bytes = args.partition_metadata.read_bytes() if args.partition_metadata else None
    partition_metadata = json.loads(partition_bytes) if partition_bytes else None
    plan = resolve(config, audit, now, partition_metadata)
    if partition_bytes:
        plan['partition_metadata_sha256'] = sha(partition_bytes)
    if plan['status'] != 'ALL_GATES_PASS_READY_TO_FREEZE':
        target = HERE/('ACTOR_FORMAL_GATE-'+now.strftime('%Y%m%dT%H%M%S')+'.json')
        new(target, payload(plan))
        print(json.dumps(plan))
        raise SystemExit('No formal release built. Preserve pilot; do not tune/cut/retry.')
    files = {}
    for line in (SOURCE/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        data = (SOURCE/name).read_bytes()
        assert sha(data) == digest, name
        files[name] = data
    frozen = copy.deepcopy(config)
    frozen.update(status='FORMAL_FROZEN', pilot_audit_sha256=sha(audit_bytes),
                  original_protocol_config_sha256=sha(config_bytes))
    for group, resource in zip(frozen['formal_groups'], plan['groups']):
        assert group['id'] == resource['id']
        group.update(wall_minutes=resource['wall_minutes'], status='RESOLVED', partition=resource['partition'])
    files['formal-config.json'] = payload(frozen)
    plan['formal_config_sha256'] = sha(files['formal-config.json'])
    files['formal-plan.json'] = payload(plan)
    if partition_bytes:
        files['PARTITION_METADATA_v1.json'] = partition_bytes
    files['PILOT_AUDIT_v1.json'] = audit_bytes
    files['OLD_REMOTE_DEPENDENCY_AUDIT_v2.json'] = dependency_bytes
    files['CLAUDE_TASK_FORMAL_authorized.md'] = review
    files['formal-approval.json'] = payload(dict(experiment='X10b', stage='FORMAL',
          review_sha256=sha(review), exact_authorization_quote=quote,
          formal_config_sha256=plan['formal_config_sha256'], pilot_audit_sha256=sha(audit_bytes),
          all_fixed_gates_pass=True, automatic_retries=0))
    for name in ['submit_actor_formal.py', 'actor_control.py', 'prepare_actor_formal.py', 'audit_actor_formal.py']:
        selected = CONTROL/'submit_formal_v2.py' if name == 'submit_actor_formal.py' else Path(__file__) if name == 'prepare_actor_formal.py' else HERE/name
        data = selected.read_bytes()
        ast.parse(data.decode('utf-8'), filename=name)
        files[name] = data
    template = (SOURCE/'pilot-NPG.sbatch').read_text()
    template = template.replace('releases/x10-20261106-b-pilot-v2', 'releases/'+NAME)
    original = 'actor_pilot_v2.py --config actor-config-protocol-v2.json --role NPG'
    assert template.count(original) == 1
    for index, group in enumerate(frozen['formal_groups']):
        command = ('formal_driver.py --config formal-config.json --group '+group['id']
                   +' --index "$SLURM_ARRAY_TASK_ID" --out "$base/results/x10-20261106/X10b/formal-v1"')
        files[f'formal-g{index:02d}.sbatch'] = template.replace(original, command).encode()
    hashes = {name: sha(data) for name, data in files.items()}
    files['SHA256SUMS'] = ''.join(f'{digest}  {name}\n' for name, digest in hashes.items()).encode()
    target = HERE/'prepared-actor-formal-v1'
    archive = HERE/'packages'/(NAME+'.tar.gz')
    assert not target.exists() and not archive.exists()
    assert sha((CHANNEL/'CLAUDE_TASK.md').read_bytes()) == args.expected_review_sha256
    for name, data in files.items():
        new(target/name, data)
    with tarfile.open(archive, 'x:gz') as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    manifest = dict(status='FORMAL_RELEASE_FROZEN_NOT_SUBMITTED', name=NAME,
                    archive=str(archive), archive_sha256=sha(archive.read_bytes()),
                    config_sha256=plan['formal_config_sha256'], source_manifest_sha256=sha(files['SHA256SUMS']),
                    pilot_audit_sha256=sha(audit_bytes), plan=plan, files=hashes)
    new(HERE/'ACTOR_FORMAL_MANIFEST_v1.json', payload(manifest))
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}))


if __name__ == '__main__':
    main()
