"""Dispatch frozen X9 functions with X12 append-only archive I/O."""
import argparse
import hashlib
import io
import json
import os
import resource
import tarfile
import time
from pathlib import Path

import numpy as np
import x9_core as core
from virtual_task_store_v2 import TaskStore, VirtualPath, file_sha, install_io_only, verify_archive


ACTOR_ROOT = Path('/scratch/user/changze/lqr_experiments/results/x9-20261106')
PILOT_CASES = [('NPG', 9601, 1901), ('PI', 9601, 1901),
               ('NPG', 9602, 1902), ('PI', 9602, 1902)]
ALGORITHMS = ('NPG', 'PI')


def choose(tag, stage, index, config):
    if stage == 'pilot':
        if tag == 'a':
            algorithm, system, seed = PILOT_CASES[index]
            return .02, algorithm, system, seed
        alpha = config['new_alphas'][index // 2]
        algorithm, system, seed = PILOT_CASES[index % 4]
        return alpha, algorithm, system, seed
    alpha = config['new_alphas'][index // 64]
    algorithm = ALGORITHMS[(index % 64) // 32]
    system = config['formal_systems'][(index % 32) // 4]
    seed = config['formal_sampling_seeds'][index % 4]
    return alpha, algorithm, system, seed


def model_member(store, system, model):
    folder = store.root / f'model-{system}'
    arrays = {key: value for key, value in model.items() if key != 'certificate' and value is not None}
    member = store.save_npz(folder / 'model.npz', **arrays)
    store.save_json(folder / 'model.json', dict(certificate=model['certificate'], sha256=member['sha256']))


def load_model(archive, system):
    with tarfile.open(archive, 'r:') as tf:
        meta = json.load(tf.extractfile(f'model-{system}/model.json'))
        data = tf.extractfile(f'model-{system}/model.npz').read()
    assert hashlib.sha256(data).hexdigest() == meta['sha256']
    with np.load(io.BytesIO(data), allow_pickle=False) as arrays:
        model = {key: arrays[key].copy() for key in arrays.files}
    model.update(basis=None, certificate=meta['certificate'])
    return model


def run(a):
    core.e.require_compute()
    config = json.loads(a.config.read_bytes())
    core.verify(config)
    assert a.index == int(os.environ['SLURM_ARRAY_TASK_ID'])
    assert a.output.is_dir()
    start = time.monotonic()
    alpha, algorithm, system, seed = choose(a.item, a.stage, a.index, config)
    prefix = f'x14{a.item}-{a.stage}-{a.index:03d}'
    logical = ACTOR_ROOT / 'x14-virtual-never-materialized' / prefix
    assert not logical.exists()
    store = TaskStore(a.output / f'{prefix}.tar', a.output / f'{prefix}.jsonl', logical, 48 * 1024**2)
    original_helpers = install_io_only(core.e, core.actor, store)
    original_npz = np.savez_compressed

    def save_npz(path, *args, **values):
        if isinstance(path, VirtualPath):
            assert not args
            return store.save_npz(path, **values)
        return original_npz(path, *args, **values)

    np.savez_compressed = save_npz
    header = dict(alpha=alpha, algorithm=algorithm, index=a.index, system=system, seed=seed,
                  config_sha256=file_sha(a.config), driver_sha256=file_sha(__file__),
                  job=os.environ['SLURM_JOB_ID'])
    paths = []
    try:
        store.save_json(store.root / 'BEGIN.json', header)
        if a.stage == 'pilot' and a.item == 'a' and a.index == 0:
            for model_system in config['formal_systems']:
                model_member(store, model_system, core.make_model(model_system, alpha, config))
        if a.stage == 'formal' and a.item == 'a':
            model = load_model(a.output / 'x14a-pilot-000.tar', system)
        else:
            model = core.make_model(system, alpha, config)
        assert model['certificate']['alpha'] == alpha
        spec = dict(experiment='X9', n=24, m=24, r=2, physical_rank=24,
                    system=system, seed=seed, alpha=alpha, tau2_sq=22*alpha**2)
        equivalence = []
        if a.stage == 'pilot':
            for probe_alpha in (0., alpha):
                probe = core.make_model(system, probe_alpha, config)
                case = dict(spec, trial=seed, alpha=probe_alpha, tau2_sq=22*probe_alpha**2)
                equivalence.append(core.equivalence(probe, case, algorithm, store.root / f'equivalence-{probe_alpha}'))
        body_start = time.monotonic()
        for entry in config['all_schedules']:
            rung = entry['rung']
            label = f'{algorithm}-j{int(round(-np.log2(rung)))}'
            path = store.root / label
            result = core.actor.run(model, dict(spec, rung=rung), core.stage_config(entry), algorithm, path)
            expected = entry['primitive_per_arm_per_algorithm']
            assert result['primitive_transitions'] == dict(dense=expected, truncated=expected)
            paths.append(dict(path=label, rung=rung, algorithm=algorithm, primitive_per_arm=expected,
                              seconds=result['seconds'], done_sha256=store.sha(path / 'DONE.json')))
        cache = Path(os.environ['TMPDIR'])
        assert cache.is_relative_to(a.output) and cache.is_dir()
        cache_paths = list(cache.rglob('*'))
        cache_bytes = sum(p.stat().st_size for p in cache_paths if p.is_file())
        assert len(cache_paths)+1 <= 21 and cache_bytes <= 64*2**20
        receipt = dict(header, status='COMPLETE', paths=paths, body_seconds=time.monotonic()-body_start,
                       seconds=time.monotonic()-start, peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       scratch_cache_objects=len(cache_paths)+1, scratch_cache_bytes=cache_bytes,
                       equivalence=equivalence, observation_transitions=2*sum(row['primitive_per_arm'] for row in paths)
                       + (102656 if equivalence else 0), automatic_retries=0)
        store.save_json(store.root / 'TASK_DONE.json', receipt)
    except Exception as exc:
        store.save_json(store.root / 'HARD_FAILURE.json', dict(header, error=repr(exc), completed_paths=paths))
        raise
    finally:
        proof = store.close()
        np.savez_compressed = original_npz
        core.e.sha, core.e.save, core.actor.save_npz = original_helpers
    if a.stage == 'pilot':
        verify_archive(store.archive, proof['members'])
    with store.journal.open('ab') as stream:
        proof.pop('journal_sha256')
        stream.write((json.dumps(dict(proof, kind='TASK_FINAL', **receipt))+'\n').encode())
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(dict(status='COMPLETE', **header, body_seconds=receipt['body_seconds'],
                          archive_bytes=proof['archive_bytes'], peak_RSS_KiB=receipt['peak_RSS_KiB'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('item', choices=['a', 'b'])
    parser.add_argument('stage', choices=['pilot', 'formal'])
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    run(parser.parse_args())
