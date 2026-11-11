"""Authorized X10b replay/equivalence and resource pilot; compute nodes only."""
import argparse
import json
import os
import resource
import time
from pathlib import Path
import numpy as np
import frozen_engine as e
import estimation
import actor_paths as actor

ROOT = Path(__file__).resolve().parent
OUT = Path('/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b')


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def verify(config):
    for name, digest in config['scientific_sources'].items():
        assert e.sha(ROOT/name) == digest, name
    for key, meta in config['model_registry'].items():
        assert e.sha(ROOT/meta['path']) == meta['sha256'], key


def model(meta):
    path = ROOT/meta['path']
    assert e.sha(path) == meta['sha256']
    with np.load(path, allow_pickle=False) as archive:
        s = {key: archive[key].copy() for key in archive.files}
    s['certificate'] = meta['certificate']
    return s


def stage_config(batches):
    return dict(H=16, nu=1., burn_blocks=16, eta=.2, schedules=batches)


def replay(config, destination):
    s = model(config['model_registry']['n24-s301'])
    baseline = json.loads((ROOT/'baseline/X6b-formal-config.json').read_text())
    schedule = next(r for r in baseline['all_schedules'] if r['n'] == 24 and r['rung'] == 1/64)
    checks = []
    for ref in config['original_replay']:
        old_path = Path(ref['remote_path'])
        assert e.sha(old_path) == ref['sha256']
        expected = json.loads(old_path.read_text())
        assert expected['spec'] == ref['spec']
        path = destination/(ref['algorithm']+'-validation-replay')
        actual = actor.run(s, expected['spec'], stage_config(schedule['batches']), ref['algorithm'], path)
        assert actual['spec'] == expected['spec']
        assert actual['records'] == expected['records'], 'Saved X6b record is not bitwise identical.'
        assert actual['primitive_transitions'] == expected['primitive_transitions']
        assert actual['padding_transitions'] == expected['padding_transitions']
        assert len(actual['artifacts']) == len(expected['artifacts'])
        checked_arrays = 0
        for new_item, old_item in zip(actual['artifacts'], expected['artifacts']):
            assert (new_item['stage'], new_item['arm']) == (old_item['stage'], old_item['arm'])
            assert new_item['rng_state'] == old_item['rng_state']
            source = old_path.parent/old_item['path']
            target = path/new_item['path']
            assert e.sha(source) == old_item['sha256'] and e.sha(target) == new_item['sha256']
            with np.load(source, allow_pickle=False) as old_arrays, np.load(target, allow_pickle=False) as new_arrays:
                assert set(old_arrays.files) == set(new_arrays.files)
                for name in old_arrays.files:
                    assert np.array_equal(old_arrays[name], new_arrays[name]), (ref['algorithm'], new_item['stage'], name)
                    checked_arrays += 1
        checks.append(dict(algorithm=ref['algorithm'], status='PASS_BITWISE_SAVED_RECORDS_ARRAYS_RNG_COUNTS',
                           source_receipt_sha256=ref['sha256'], checked_arrays=checked_arrays,
                           primitive_transitions=actual['primitive_transitions'],
                           replay_done_sha256=e.sha(path/'DONE.json')))
    return dict(status='PASS', role='equivalence', checks=checks,
                validation_replay_not_new_formal_replication=True,
                primitive_transitions=sum(sum(c['primitive_transitions'].values()) for c in checks),
                formal_observation_transitions=0, no_performance_readout=True)


def timing(config, algorithm, destination):
    equality = json.loads((OUT/'resource-v1/equivalence/PILOT_DONE.json').read_text())
    assert equality['status'] == 'PASS' and equality['source_sha256'] == e.sha(__file__)
    n, system, seed = 72, config['resource_system'], config['resource_seed']
    s = estimation.model('S', n, system)
    rows = []
    for schedule in [r for r in config['all_schedules'] if r['n'] == n]:
        spec = dict(experiment='X10b_RESOURCE_ONLY', n=n, m=n, r=2,
                    system=system, seed=seed, rung=schedule['rung'],
                    rung_label='r'+str(schedule['rung']).replace('.', ''))
        path = destination/spec['rung_label']
        result = actor.run(s, spec, stage_config(schedule['batches']), algorithm, path)
        expected = schedule['primitive_per_arm_per_algorithm']
        assert result['primitive_transitions'] == dict(dense=expected, truncated=expected)
        rows.append(dict(rung=schedule['rung'], algorithm=algorithm,
                         seconds=result['seconds'], primitive_per_arm=expected,
                         done_sha256=e.sha(path/'DONE.json')))
    assert len(rows) == 5
    return dict(status='PASS', role='timing', n=72, algorithm=algorithm,
                system=system, seed=seed, rows=rows, body_seconds=sum(r['seconds'] for r in rows),
                primitive_transitions=2*sum(r['primitive_per_arm'] for r in rows),
                formal_observation_transitions=0, no_performance_readout=True)


def main(config_path, role):
    e.require_compute()
    config = json.loads(config_path.read_text())
    assert config['status'] == 'PROTOCOL_FROZEN'
    assert config['actual_forecast_cap_SU'] == 160 and config['requested_upper_cap_SU'] == 200
    verify(config)
    destination = OUT/'resource-v1'/role
    assert not destination.exists()
    destination.mkdir(parents=True)
    begin = time.monotonic()
    save_new(destination/'BEGIN.json', dict(role=role, config_sha256=e.sha(config_path),
             source_sha256=e.sha(__file__), job=os.environ['SLURM_JOB_ID'], automatic_retries=0))
    try:
        result = replay(config, destination) if role == 'equivalence' else timing(config, role, destination)
        result.update(seconds=time.monotonic()-begin,
                      peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      source_sha256=e.sha(__file__), actor_sha256=e.sha(actor.__file__),
                      engine_sha256=e.sha(e.__file__), config_sha256=e.sha(config_path),
                      job=os.environ['SLURM_JOB_ID'], automatic_retries=0)
        assert result['peak_RSS_KiB'] <= .8*2*1024*1024
        save_new(destination/'PILOT_DONE.json', result)
        print(json.dumps(result), flush=True)
    except Exception as exc:
        save_new(destination/'PILOT_HARD_FAILURE.json', dict(role=role, error=repr(exc),
                 config_sha256=e.sha(config_path), source_sha256=e.sha(__file__),
                 job=os.environ['SLURM_JOB_ID'], automatic_retries=0,
                 partial_transitions='Use complete-stage receipts; do not invent a partial count.'))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--role', choices=['equivalence', 'NPG', 'PI'], required=True)
    args = p.parse_args()
    main(args.config, args.role)
