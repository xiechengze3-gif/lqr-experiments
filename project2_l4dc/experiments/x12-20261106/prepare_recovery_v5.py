"""Freeze a small recovery release only from an E-verified active I/O pilot."""
import argparse
import hashlib
import json
import math
import tarfile
import zipfile
from pathlib import Path

from recovery_driver_v5 import NEW, OLD, ORIGINAL, ORIGINAL_CONFIG_SHA256
from virtual_task_store_v2 import digest, file_sha


R = Path(__file__).resolve().parent
FORMAL = R / 'formal-release-v1'
X10 = R.parent / 'x10-20261106'
REVIEW = R.parents[1] / 'CLAUDE_TASK.md'
MIB = 1024**2
FORMAL_FILES = 64 * 3 + 10 + 12 + 6 + 32
FIXED_BYTES = 128 * MIB
REPORT_BYTES = 256 * MIB


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def encode(d):
    return (json.dumps(d, indent=2) + '\n').encode()


def write(p, data):
    with p.open('xb') as f:
        f.write(data)


def frozen_plan():
    plan = read(R / 'RECOVERY_WORK_PLAN_v2.json')
    manifest = read(R / 'REUSED_COMPLETE_PATHS_v2.json')
    assert file_sha(R / 'REUSED_COMPLETE_PATHS_v2.json') == plan['reused_manifest_sha256']
    archive_path = R / 'reused-complete-paths-v2.tar'
    assert file_sha(archive_path) == manifest['archive_sha256']
    assert archive_path.stat().st_size == manifest['archive_bytes']
    lookup = {r['member_prefix']: r for r in manifest['reused_paths']}
    counts = {OLD: 0, NEW: 0}
    transitions = {OLD: 0, NEW: 0}
    with tarfile.open(archive_path, 'r:') as tf:
        for t in plan['tasks']:
            for w in t['runs']:
                kind = w['origin']
                counts[kind] += 1
                transitions[kind] += 2 * w['primitive_per_arm']
                if kind == OLD:
                    row = lookup[w['member_prefix']]
                    assert row['done_sha256'] == w['done_sha256']
                    data = tf.extractfile(w['member_prefix'] + '/DONE.json').read()
                    assert digest(data) == w['done_sha256']
                    d = json.loads(data)
                    assert d['status'] == 'COMPLETE' and d['spec']['system'] == t['system'] and d['spec']['seed'] == t['seed']
                    assert d['spec']['rung'] == w['rung'] and d['algorithm'] == t['algorithm']
                    w['final_stable'] = {a: next(x['stable'] for x in reversed(d['records']) if x['arm'] == a)
                                         for a in ('dense', 'truncated')}
    assert len(plan['tasks']) == 64 and counts == {OLD: 296, NEW: 280}
    assert transitions == {OLD: 9476201216, NEW: 184168537344}
    plan.pop('original_config_values')
    plan.update(reused_archive_sha256=manifest['archive_sha256'], transitions=transitions, counts=counts)
    return plan, manifest


def pilot_limits(p, expected_mdt=0):
    assert p['status'] == 'ACTIVE_GRACE_IO_PILOT_PASS' and p['job'] and p['output_MDT'] == expected_mdt
    assert p['reference_backends'] == ['ORIGINAL_FROZEN_DISK_FIXTURE_BYTES']
    assert p['npz_old_fixture_resave_byte_identical'] == p['all_npz_fileio_vs_memory_byte_comparisons'] == 648
    assert p['named_reference_files_created'] == p['physical_loose_stage_files_per_task'] == p['new_training_transitions'] == 0
    assert p['physical_store_files_per_task'] == 2 and p['future_Slurm_logs_per_task'] == 1
    assert p['peak_RSS_KiB'] < .8 * 2048 * 1024
    node = p['node_temporary_storage']
    assert node['all64_cache_and_report_bytes'] < .8 * node['free_bytes']
    assert node['all64_cache_and_report_files'] < .8 * node['free_files']
    limits = {}
    for result in p['results']:
        paths = {}
        for m in result['members']:
            rung = m['path'].split('/', 1)[0]
            paths[rung] = paths.get(rung, 0) + 512 + ((m['bytes'] + 511) // 512) * 512
        assert len(paths) == 9
        limits[result['algorithm']] = math.ceil(1.5 * max(paths.values()))
    assert set(limits) == {'NPG', 'PI'}
    assert sum(r['json_original_byte_comparisons'] for r in p['results']) == 234
    assert sum(len(r['members']) for r in p['results']) == 882
    return limits


def main(a):
    review = REVIEW.read_bytes()
    assert digest(review) == a.expected_review_sha256
    assert b'If all pass, proceed to FORMAL and REPORT without another review' in review
    scratch = a.scratch_v6
    receipt_path = R / ('STORAGE_SCRATCH_IO_VERIFIED_v6.json' if scratch else 'STORAGE_FLAT_IO_VERIFIED_v5.json')
    p = read(receipt_path)
    assert p['status'] == 'ACTIVE_IO_PILOT_ARCHIVES_VERIFIED_ON_E'
    ppath = R / ('delivery-storage-scratch-v6/pilot-DONE.json' if scratch else 'delivery-storage-flat-v5/pilot-DONE.json')
    assert file_sha(ppath) == p['pilot_done_sha256']
    pilot = read(ppath)
    assert pilot['job'] == p['job'] and p['allocation_state'] == 'COMPLETED'
    limit = pilot_limits(pilot, expected_mdt=int(scratch))
    io_seconds = p['elapsed_seconds'] + 16
    m = read(R / ('STORAGE_SCRATCH_MANIFEST_v6.json' if scratch else 'STORAGE_FLAT_MANIFEST_v5.json'))
    assert pilot['source_sha256'] == m['files']['pilot_virtual_store_v6.py' if scratch else 'pilot_virtual_store_v5.py']
    assert pilot['store_source_sha256'] == m['files']['virtual_task_store_v2.py']
    plan, manifest = frozen_plan()
    cfg = read(FORMAL / 'formal-config.json')
    assert file_sha(FORMAL / 'formal-config.json') == ORIGINAL_CONFIG_SHA256
    for model in cfg['model_registry'].values():
        model['path'] = ORIGINAL.as_posix() + '/' + model['path']
    cfg['scientific_sources']['formal_driver.py'] = file_sha(R / 'recovery_driver_v5.py')
    bounds = {}
    new_counts = {'NPG': 0, 'PI': 0}
    for task in plan['tasks']:
        missing = sum(w['origin'] == NEW for w in task['runs'])
        new_counts[task['algorithm']] += missing
        bounds[f"{task['group']}-task-{task['index']:02d}"] = missing * limit[task['algorithm']] + 64 * 1024
    assert new_counts == {'NPG': 128, 'PI': 152}
    expected_peak_bytes = sum(bounds.values()) + 64 * 256 * 1024 + REPORT_BYTES + FIXED_BYTES
    home_bound = expected_peak_bytes + manifest['archive_bytes']  # Retain the original conservative bound.
    base_gate = read(FORMAL / 'gate.json')
    groups = []
    for group in base_gate['groups']:
        body = max(group['historical_floor_seconds'], group['measured_body_seconds']) + max(60, io_seconds)
        groups.append(dict(id=group['id'], algorithm=group['algorithm'], body_seconds=body, tasks=32,
                           wall_minutes=math.ceil((1.2 * body + 30) / 60), cpus=1, memory_MiB=2048))
    cfg['recovery'] = dict(status='READY_FOR_LIVE_STORAGE_AND_COST_GATES_ONLY',
        task_archive_byte_bounds=bounds, max_files_all64_plus_report=FORMAL_FILES,
        forecast_physical_bytes_including_reuse_reserve=home_bound, estimated_actual_physical_growth_bytes=expected_peak_bytes,
        encoded_per_path_limits=limit, io_pilot_job=p['job'], io_pilot_elapsed_seconds=p['elapsed_seconds'],
        io_pilot_receipt_sha256=file_sha(receipt_path), report_reserved_SU=8, groups=groups,
        storage_project=231181 if scratch else 31181, storage_root=m['remote_root'], mdt=int(scratch),
        original_config_sha256=ORIGINAL_CONFIG_SHA256, no_mid_path_resume=True, review_sha256=digest(review))
    if scratch:
        cleanup = R/'scratch-cleanup-proposal-20261107-v1/CLEANUP_AUDITED_v1.json'
        evidence = read(cleanup)
        assert evidence['status'] == 'EXACT_MANIFEST_CLEANUP_AUDITED_ON_E'
        assert FORMAL_FILES < .8*min(evidence['new_slots_MDT1'], evidence['new_slots_total'])
        cfg['recovery']['cleanup_audit_sha256'] = file_sha(cleanup)

    files = {n: (R / n).read_bytes() for n in (
        'recovery_driver_v5.py', 'recovery_archive_reader_v5.py', 'reconstruct_reuse_for_report_v5.py',
        'recovery_report_v5.py', 'virtual_task_store_v2.py', 'report_products_v1.py', 'report_render_v3.py',
        'REUSED_COMPLETE_PATHS_v2.json')}
    files.update({n: (FORMAL / n).read_bytes() for n in ('analyze_actor.py', 'paper_cross.py')})
    files['recovery-membership.json'] = encode(plan)
    files['CLAUDE_TASK_authorized.md'] = review
    proof = X10 / 'delivery-actor-report-v1/report-v1/PRODUCTS_COMPLETE_v1.json'
    baseline_proof = read(proof)
    assert baseline_proof['status'] == 'MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED'
    baseline = {}
    for name in ('summary.csv', 'transitions_saved_derived.csv', 'failures.csv', 'failure_counts_by_cell.csv'):
        src = 'summary_merged_nine_rungs.csv' if name == 'summary.csv' else name
        local, delivered = X10 / src, proof.parent / src
        h = file_sha(local)
        assert h == file_sha(delivered) == baseline_proof['files'][src]
        files['baseline/' + name] = local.read_bytes()
        baseline[name] = h
    files['baseline/MANIFEST_v1.json'] = encode(dict(status='ACCEPTED_X10B_BASELINE_BYTES_ONLY', files=baseline,
        source_products_proof_sha256=file_sha(proof), old_statistics_recomputed=False, old_training_transitions=0))
    files['__main__.py'] = b'''import runpy, sys
mode = sys.argv.pop(1)
assert mode in ('formal', 'report')
runpy.run_module('recovery_driver_v5' if mode == 'formal' else 'recovery_report_v5', run_name='__main__')
'''
    assert digest(files['analyze_actor.py']) == cfg['scientific_sources']['analyze_actor.py']
    assert (REVIEW.read_bytes() == review)
    release = R / ('recovery-release-v6' if scratch else 'recovery-release-v5')
    release.mkdir()
    with zipfile.ZipFile(release / 'recovery-v5.zip', 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as z:
        for n, data in files.items():
            z.writestr(n, data)
    write(release / 'recovery-config.json', encode(cfg))
    result = dict(status='LOCAL_RECOVERY_RELEASE_READY_NOT_SUBMITTED', config_sha256=file_sha(release / 'recovery-config.json'),
                  bundle_sha256=file_sha(release / 'recovery-v5.zip'), files={n:digest(b) for n,b in files.items()},
                  remote_root=m['remote_root'], review_sha256=digest(review), predicted_new_storage_objects=FORMAL_FILES,
                  conservative_storage_byte_bound=home_bound, groups=groups)
    write(release / 'RELEASE_MANIFEST_v5.json', encode(result))
    print(json.dumps({k:v for k,v in result.items() if k != 'files'}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--expected-review-sha256', required=True)
    p.add_argument('--scratch-v6', action='store_true')
    main(p.parse_args())
