"""Read-only corrected-pilot input preflight; standard library, never submits.

Prepared while correction authorization is pending. Run on the Grace login node
only after a new, explicitly authorized v2 release has been frozen/deployed.
Do not print scientific outcomes or touch any old result/release/ledger.
"""
import argparse
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

BASE = Path('/scratch/user/changze/lqr_experiments')
OUT = BASE/'results/x10-20261106/X10b'
RELEASE = BASE/'releases/x10-20261106-b-pilot-v2'
OLD_RELEASE = BASE/'releases/x10-20261106-b-pilot-v1'
BASELINE_MANIFEST_SHA = '86ff9a5c0de6106309f04cf714fc875b92ebe1c2ddfbcdd29741a08de382a011'
WRAPPER_SHA = '77586c8050a1a1982accf3d9852fa1167491b73bfd59926951259eba4c964cf6'
NPG_DONE_SHA = 'f28ec37533c341526d1eda1af17d154b8de3c4e9657ac11e641b9bba78407ee0'
FAILED_HISTORY = {'20415057': ('FAILED', 57),
                  '20415058': ('CANCELLED', 0),
                  '20415059': ('CANCELLED', 0)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(value):
    path = Path(value)
    assert not path.is_absolute() and '..' not in path.parts and str(path) != '.'
    return path


def allocation_rows(job):
    raw = subprocess.check_output(['sacct', '-X', '--array', '-j', job,
          '-n', '-P', '--format=JobID,State,ElapsedRaw,AllocTRES'], text=True)
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        jid, state, seconds, tres = line.split('|')[:4]
        assert '.' not in jid and (jid == job or jid.startswith(job+'_'))
        rows.append(dict(job=jid, state=state, elapsed_seconds=int(seconds), alloc_tres=tres))
    assert rows, ('Missing allocation history', job)
    return rows


def check_release(root):
    assert root.resolve() == RELEASE
    config_path = root/'actor-config-protocol-v2.json'
    cfg = json.loads(config_path.read_text())
    approval = json.loads((root/'approval-v2.json').read_text())
    review = root/'CLAUDE_TASK_CORRECTION_AUTHORIZED.md'
    assert sha(config_path) == approval['config_sha256']
    assert sha(review) == approval['review_sha256'] == cfg['author_review_sha256']
    assert approval['stage'] == 'PILOT' and approval['experiment'] == 'X10b'
    assert approval['corrected_pilot_explicitly_authorized'] is True
    quote = approval['exact_corrected_authorization_quote']
    assert quote and quote in review.read_text(encoding='utf-8-sig')
    assert cfg['status'] == 'PROTOCOL_FROZEN' and cfg['version'] == 2
    assert cfg['actual_forecast_cap_SU'] == 160 and cfg['requested_upper_cap_SU'] == 200
    assert abs(cfg['pilot_requested_upper_SU']-8-1/3) < 1e-9
    old_cfg_path = OLD_RELEASE/'actor-config-protocol-v1.json'
    assert sha(old_cfg_path) == cfg['original_protocol_config_sha256']
    old_cfg = json.loads(old_cfg_path.read_text())
    for key in ['family', 'eta', 'nu', 'H', 'burn_blocks', 'baseline_blocks',
                'formal_systems', 'formal_sampling_seeds', 'selected_NPG_T',
                'selected_PI_T', 'npg_bases', 'n_values', 'rank', 'rungs',
                'all_schedules', 'formal_groups', 'model_registry',
                'original_replay', 'resource_system', 'resource_seed',
                'scientific_sources', 'historical_resource_profile',
                'new_formal_paired_paths', 'new_formal_primitive_transitions']:
        assert cfg[key] == old_cfg[key], key
    sums = (root/'SHA256SUMS').read_text().splitlines()
    seen = set()
    for line in sums:
        digest, name = line.split('  ', 1)
        assert name not in seen
        seen.add(name)
        assert sha(root/relative_path(name)) == digest, name
    for name, digest in cfg['scientific_sources'].items():
        assert name in seen and sha(root/relative_path(name)) == digest, name
    for name, meta in cfg['model_registry'].items():
        path = relative_path(meta['path'])
        assert path.as_posix() in seen and sha(root/path) == meta['sha256'], name
    assert cfg['validation_wrapper_sha256'] == WRAPPER_SHA
    assert sha(root/'actor_pilot_v2.py') == WRAPPER_SHA
    assert cfg['reference_baseline_manifest_sha256'] == BASELINE_MANIFEST_SHA
    assert cfg['reuse_completed_v1_NPG_done_sha256'] == NPG_DONE_SHA
    return cfg


def check_inputs(root, cfg):
    baseline = root/'replay-baseline'
    assert sha(baseline/'MANIFEST_v2.json') == BASELINE_MANIFEST_SHA
    manifest = json.loads((baseline/'MANIFEST_v2.json').read_text())
    assert manifest['original_stage_arrays'] == 48 and manifest['original_receipts'] == 2
    assert len(manifest['files']) == 50
    for name, meta in manifest['files'].items():
        path = baseline/relative_path(name)
        assert path.is_file() and path.stat().st_size == meta['bytes'], name
        assert sha(path) == meta['sha256'], name
    replay = OUT/'resource-v1/equivalence/NPG-validation-replay'
    assert sha(replay/'DONE.json') == NPG_DONE_SHA
    actual = json.loads((replay/'DONE.json').read_text())
    reference = json.loads((baseline/'NPG/DONE.json').read_text())
    npg_ref = next(r for r in cfg['original_replay'] if r['algorithm'] == 'NPG')
    assert sha(baseline/'NPG/DONE.json') == npg_ref['sha256']
    assert actual['source_sha256'] == cfg['scientific_sources']['actor_paths.py']
    assert actual['engine_sha256'] == cfg['scientific_sources']['frozen_engine.py']
    for key in ['spec', 'records', 'primitive_transitions', 'padding_transitions']:
        assert actual[key] == reference[key], key
    assert actual['spec'] == npg_ref['spec']
    assert len(actual['artifacts']) == len(reference['artifacts']) == 32
    for new_item, old_item in zip(actual['artifacts'], reference['artifacts']):
        for key in ['stage', 'arm', 'rng_state', 'sha256']:
            assert new_item[key] == old_item[key], key
        assert sha(replay/relative_path(new_item['path'])) == new_item['sha256']
        assert sha(baseline/'NPG'/relative_path(old_item['path'])) == old_item['sha256']
    assert actual['primitive_transitions'] == dict(dense=2964976, truncated=2964976)
    return dict(reference_files=50, reference_stage_arrays=48,
                completed_NPG_stage_arrays=32, completed_NPG_done_sha256=NPG_DONE_SHA,
                reused_NPG_transitions=5929952, new_trajectories=0,
                np_array_equal_still_required_in_compute_pilot=True)


def check_before_submission():
    cfg = check_release(RELEASE)
    inputs = check_inputs(RELEASE, cfg)
    assert not (OUT/'resource-v2').exists(), 'Reconcile any existing corrected output first.'
    assert not (OUT/'submissions/PILOT_CHAIN_v2.json').exists()
    ledger_path = OUT/'budget/ledger.json'
    ledger = json.loads(ledger_path.read_text())
    assert ledger['study'] == 'X10b'
    assert ledger['actual_forecast_cap_SU'] == 160 and ledger['requested_upper_cap_SU'] == 200
    assert abs(ledger['cumulative_requested_SU']-4-1/6) < 1e-9
    assert len(ledger['submissions']) == 3
    assert {row['job'] for row in ledger['submissions']} == set(FAILED_HISTORY)
    history = []
    for row in ledger['submissions']:
        assert row['stage'] == 'PILOT' and row['status'] == 'SUBMITTED'
        rows = allocation_rows(row['job'])
        assert len(rows) == 1
        expected_state, expected_seconds = FAILED_HISTORY[row['job']]
        assert rows[0]['state'] == expected_state and rows[0]['elapsed_seconds'] == expected_seconds
        history.extend(rows)
    x9_ledger = json.loads((BASE/'results/x9-20261106/budget/ledger.json').read_text())
    assert any(row['stage'] == 'REPORT' for row in x9_ledger['submissions'])
    x9_jobs = []
    for row in x9_ledger['submissions']:
        assert row['job'], 'Reconcile any uncertain X9 submission first.'
        rows = allocation_rows(row['job'])
        assert all(item['state'] == 'COMPLETED' for item in rows)
        x9_jobs.append(dict(job=row['job'], stage=row['stage'], allocations=len(rows)))
    return dict(status='PASS_CORRECTED_PILOT_INPUTS_AND_PRESERVED_HISTORY',
                checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                release=str(RELEASE), config_sha256=sha(RELEASE/'actor-config-protocol-v2.json'),
                inputs=inputs, prior_ledger_sha256=sha(ledger_path),
                prior_ledger_submissions=ledger['submissions'], old_pilot_history=history,
                prior_actual_elapsed_SU=57/3600, prior_requested_upper_SU=4+1/6,
                proposed_additional_requested_SU=4+1/6,
                proposed_cumulative_pilot_requested_upper_SU=8+1/3,
                x9_all_compute_including_report_complete=True, x9_jobs=x9_jobs,
                no_performance_readout=True, new_trajectories=0, submitted_jobs=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--before-submission', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(check_before_submission()))
