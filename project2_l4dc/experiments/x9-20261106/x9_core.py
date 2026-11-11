"""X9 versioned model/dispatch wrapper. All numerical work requires Slurm."""
import json
import os
import resource
import time
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_are
import frozen_engine as e
import estimation
import actor_paths as actor

ROOT = Path(__file__).resolve().parent
OUT = Path('/scratch/user/changze/lqr_experiments/results/x9-20261106')


def save_new(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, indent=2)
        stream.write('\n')


def verify(config):
    for name, digest in config['scientific_sources'].items():
        assert e.sha(ROOT / name) == digest, name
    for name, digest in config['baseline_sources'].items():
        assert e.sha(ROOT / name) == digest, name


def base_model(system, config):
    if system not in config['formal_systems']:
        assert system in config['pilot_systems']
        return estimation.model('S', 24, system)
    meta = config['baseline_models'][str(system)]
    path = ROOT / meta['path']
    assert e.sha(path) == meta['sha256']
    with np.load(path, allow_pickle=False) as archive:
        model = {key: archive[key].copy() for key in archive.files}
    model['certificate'] = dict(meta['certificate'])
    return model


def make_model(system, alpha, config):
    e.require_compute()
    s = base_model(system, config)
    u = e.haar(e.rng(2, 24, system), 24)
    v = e.haar(e.rng(3, 24, 24, system), 24)
    assert np.allclose(s['B'], u[:, :2] @ v[:, :2].T, rtol=0, atol=1e-13)
    if alpha == 0:
        return s
    assert alpha in config['new_alphas']
    s['B'] = s['B'] + alpha * (u[:, 2:] @ v[:, 2:].T)
    s['basis'] = None
    s['Pstar'] = solve_discrete_are(s['A'], s['B'], s['Q'], s['R'])
    s['Kstar'] = np.linalg.solve(s['R'] + s['B'].T @ s['Pstar'] @ s['B'],
                                s['B'].T @ s['Pstar'] @ s['A'])
    c = s['certificate']
    c.update(r=24, physical_rank=24, retained_order=2, alpha=alpha,
             tau2_sq=22*alpha**2, spectrum='two-level-full-rank',
             Jstar=float(np.trace(s['Pstar'])),
             initial_gap=float(np.trace(s['P0'] - s['Pstar'])),
             redundant_cost_identity='NOT_APPLICABLE_FULL_RANK')
    assert c['initial_gap'] > 0 and c['P0_op'] <= 1.5625 + 1e-10
    assert np.max(np.abs(np.linalg.svd(s['B'], compute_uv=False)
                         - np.r_[np.ones(2), np.full(22, alpha)])) < 1e-12
    assert np.count_nonzero(s['K0']) == 0
    return s


def save_model(s, directory):
    assert not directory.exists()
    directory.mkdir(parents=True)
    path = directory / 'model.npz'
    np.savez_compressed(path, **{k: v for k, v in s.items()
                               if k != 'certificate' and v is not None})
    meta = dict(path=str(path), sha256=e.sha(path), certificate=s['certificate'])
    save_new(directory / 'model.json', meta)
    return meta


def load_model(meta):
    path = Path(meta['path'])
    assert path.resolve().is_relative_to(OUT) and e.sha(path) == meta['sha256']
    with np.load(path, allow_pickle=False) as archive:
        s = {key: archive[key].copy() for key in archive.files}
    s.setdefault('basis', None)
    s['certificate'] = meta['certificate']
    assert s['basis'] is None and s['certificate']['r'] == 24
    return s


def stage_config(entry):
    return dict(H=16, nu=1., burn_blocks=16, eta=.2, schedules=entry['batches'])


def equivalence(s, spec, algorithm, destination):
    """Compare gains, collector outputs/RNG and counts, never score a pilot."""
    cfg = dict(H=16, nu=1., burn_blocks=16, eta=.2,
               npg_batches=[256, 512], pi_batches=[256, 512],
               schedules=dict(NPG=[256, 512], PI=[256, 512]))
    original_assess, original_collect = e.assess, e.collect

    def execute(reference):
        gains, collections = [], []

        def assess(model, gain):
            gains.append(gain.copy())
            return original_assess(model, gain)

        def collect(model, gain, state, count, random, config):
            result = original_collect(model, gain, state, count, random, config)
            collections.append((gain.copy(), count, [x.copy() for x in result],
                                json.dumps(random.bit_generator.state, sort_keys=True)))
            return result

        e.assess, e.collect = assess, collect
        try:
            if reference:
                result = e.actor_run(s, spec, cfg, algorithm, destination / 'reference.json')
                totals = result['actual_transitions']
            else:
                result = actor.run(s, spec, cfg, algorithm, destination / 'wrapped')
                totals = result['primitive_transitions']
        finally:
            e.assess, e.collect = original_assess, original_collect
        return gains, collections, totals

    left, right = execute(True), execute(False)
    assert len(left[0]) == len(right[0])
    assert all(np.array_equal(a, b) for a, b in zip(left[0], right[0]))
    assert len(left[1]) == len(right[1]) == 4
    for a, b in zip(left[1], right[1]):
        assert np.array_equal(a[0], b[0]) and a[1] == b[1] and a[3] == b[3]
        assert all(np.array_equal(x, y) for x, y in zip(a[2], b[2]))
    assert left[2] == right[2] == dict(dense=12832, truncated=12832)
    return dict(status='PASS_BITWISE_GAINS_COLLECTOR_RNG_COUNTS',
                reference_primitive_transitions=left[2], wrapped_primitive_transitions=right[2])


def resource_pilot(config_path, index):
    e.require_compute()
    config = json.loads(config_path.read_text())
    verify(config)
    assert config['status'] == 'PROTOCOL_FROZEN' and 0 <= index < 4
    case = config['pilot_cases'][index]
    dest = OUT / 'resource-v1' / f'task-{index}'
    assert not dest.exists()
    dest.mkdir(parents=True)
    start = time.monotonic()
    models = {}
    for system in config['formal_systems']:
        s = make_model(system, case['prepare_alpha'], config)
        models[str(system)] = save_model(s, dest / 'models' / f's{system}')
    preparation_seconds = time.monotonic() - start
    spec = dict(experiment='X9', n=24, m=24, r=2, physical_rank=24,
                system=case['system'], seed=case['seed'], trial=case['seed'],
                alpha=case['alpha'], tau2_sq=22*case['alpha']**2)
    s = make_model(case['system'], case['alpha'], config)
    checks = []
    for alpha in [0, case['alpha']]:
        probe = make_model(case['system'], alpha, config)
        checks.append(dict(alpha=alpha, **equivalence(
            probe, dict(spec, alpha=alpha), case['algorithm'], dest / f'equivalence-a{alpha}')))
    rows = []
    for entry in config['all_schedules']:
        result = actor.run(s, dict(spec, rung=entry['rung']), stage_config(entry),
                           case['algorithm'], dest / f"rung-{entry['rung']}")
        expected = entry['primitive_per_arm_per_algorithm']
        assert result['primitive_transitions'] == dict(dense=expected, truncated=expected)
        rows.append(dict(rung=entry['rung'], algorithm=case['algorithm'],
                         seconds=result['seconds'], primitive_per_arm=expected,
                         done_sha256=e.sha(dest / f"rung-{entry['rung']}" / 'DONE.json')))
    receipt = dict(status='COMPLETE_RESOURCE_ONLY', index=index, case=case, rows=rows,
                   equivalence=checks, formal_model_registry=models,
                   model_preparation_seconds=preparation_seconds,
                   formal_observation_transitions=0,
                   primitive_transitions=2*sum(r['primitive_per_arm'] for r in rows)+102656,
                   seconds=time.monotonic()-start,
                   peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   config_sha256=e.sha(config_path), source_sha256=e.sha(__file__),
                   no_performance_readout=True, automatic_retries=0,
                   job=os.environ['SLURM_JOB_ID'])
    save_new(dest / 'timing.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'formal_model_registry'}), flush=True)


def formal(config_path, group_id, index):
    e.require_compute()
    config = json.loads(config_path.read_text())
    verify(config)
    assert config['status'] == 'FORMAL_FROZEN' and 0 <= index < 32
    group = next(g for g in config['formal_groups'] if g['id'] == group_id)
    system, seed = config['formal_systems'][index//4], config['formal_sampling_seeds'][index % 4]
    meta = config['model_registry'][str(group['alpha'])][str(system)]
    s = load_model(meta)
    dest = OUT / 'formal-v1' / group_id / f'task-{index}'
    assert not dest.exists()
    dest.mkdir(parents=True)
    header = dict(group=group, index=index, system=system, seed=seed,
                  config_sha256=e.sha(config_path), source_sha256=e.sha(__file__),
                  model=meta, job=os.environ['SLURM_JOB_ID'])
    save_new(dest / 'BEGIN.json', header)
    start = time.monotonic()
    paths = []
    try:
        for run in group['runs']:
            entry = next(e for e in config['all_schedules'] if e['rung'] == run['rung'])
            spec = dict(experiment='X9', n=24, m=24, r=2, physical_rank=24,
                        system=system, seed=seed, alpha=group['alpha'],
                        tau2_sq=22*group['alpha']**2, rung=entry['rung'])
            path = dest / (run['algorithm'] + '-' + run['rung_label'])
            result = actor.run(s, spec, stage_config(entry), run['algorithm'], path)
            expected = entry['primitive_per_arm_per_algorithm']
            assert result['primitive_transitions'] == dict(dense=expected, truncated=expected)
            paths.append(dict(algorithm=run['algorithm'], rung=entry['rung'],
                              path=path.name, done_sha256=e.sha(path / 'DONE.json'),
                              primitive_per_arm=expected))
    except Exception as exc:
        save_new(dest / 'HARD_FAILURE.json', dict(header, paths=paths,
                 error=repr(exc), automatic_retries=0,
                 partial_count='Use complete-stage checkpoints; partial work is not invented.'))
        raise
    save_new(dest / 'DONE.json', dict(status='COMPLETE', **header, paths=paths,
             seconds=time.monotonic()-start,
             peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    print(json.dumps(dict(status='COMPLETE', group=group_id, index=index)), flush=True)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['resource', 'formal'])
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--index', type=int, required=True)
    p.add_argument('--group')
    a = p.parse_args()
    if a.mode == 'resource':
        resource_pilot(a.config, a.index)
    else:
        formal(a.config, a.group, a.index)
