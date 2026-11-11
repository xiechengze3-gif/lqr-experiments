"""X12 restart-from-K0 dispatcher; old complete paired paths are references."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from virtual_task_store_v2 import TaskStore, file_sha, install_io_only


ORIGINAL = Path('/scratch/user/changze/lqr_experiments/releases/x12-20261106-formal-v1')
ORIGINAL_CONFIG_SHA256 = '194f34ba2af8bd822396a9ae1e2317219ee5beb2da4f9a54df1d3eb479097d14'
LOGICAL = Path('/scratch/user/changze/lqr_experiments/results/x12-20261106/recovery-logical-v5')
SOURCE_FILES = {
    'actor_paths.py': '094cf07bb8b2534b97a34648cab20176304ad9dbdd3ffa25c17cf61a61e1a098',
    'frozen_engine.py': '9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989',
    'estimation.py': 'f587bd48993288dbf9160dd4cc1e62542f15ee5794bda37590ec48dc672c9c59',
}
OLD = 'REUSED_COMPLETE_V1_SHA_VERIFIED'
NEW = 'RESTART_OR_START_FROM_K0'
ARMS = ('dense', 'truncated')
TMP_BYTES = 64 * 32 * 1024**2 + 512 * 1024**2
TMP_FILES = 64 * 64 + 1024


def source_sha():
    # Zip-loaded source hashes the actual member, rather than its virtual path.
    try:
        payload = Path(__file__).read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        payload = __loader__.get_data(__file__)
    return hashlib.sha256(payload).hexdigest()


def node_storage(out):
    temp = Path(os.environ['TMPDIR']).resolve()
    assert temp.is_relative_to(Path('/tmp')) and temp.is_dir()
    assert temp.stat().st_dev != out.stat().st_dev
    for k in ('NUMBA_CACHE_DIR', 'MPLCONFIGDIR', 'XDG_CACHE_HOME'):
        p = Path(os.environ[k]).resolve()
        assert p.is_relative_to(temp.parent)
        assert p.parent.stat().st_dev == temp.stat().st_dev
    v = os.statvfs(temp)
    proof = dict(free_bytes=v.f_bavail * v.f_frsize, free_files=v.f_favail)
    assert TMP_BYTES < .8 * proof['free_bytes'] and TMP_FILES < .8 * proof['free_files']
    return proof


def json_read(path):
    return json.loads(path.read_bytes())


def audit_config(config, original):
    # Report and dispatch use the same configuration. Only provenance, physical
    # model paths and recovery controls may differ from the original config.
    assert config['status'] == 'FORMAL_FROZEN' and config['family'] == 'S'
    assert config['eta'] == .2 and config['selected_NPG_T'] == 16 and config['selected_PI_T'] == 8
    exclude = {'scientific_sources', 'model_registry', 'recovery'}
    assert {k: v for k, v in config.items() if k not in exclude} == {
        k: v for k, v in original.items() if k not in exclude}
    assert set(config['model_registry']) == set(original['model_registry'])
    for key, meta in config['model_registry'].items():
        assert meta == dict(original['model_registry'][key], path=str(ORIGINAL / original['model_registry'][key]['path']))
    for name, h in SOURCE_FILES.items():
        assert file_sha(ORIGINAL / name) == h
        if name in original['scientific_sources']:
            assert config['scientific_sources'][name] == h
    assert source_sha() == config['scientific_sources']['formal_driver.py']


def main(a):
    assert a.output.is_dir() and not LOGICAL.exists()
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_ARRAY_TASK_ID']) == a.index
    node = node_storage(a.output)
    original_cfg = ORIGINAL / 'formal-config.json'
    assert file_sha(original_cfg) == ORIGINAL_CONFIG_SHA256
    config = json_read(a.config)
    audit_config(config, json_read(original_cfg))
    assert a.output == Path(config['recovery']['storage_root'])
    placement = str(config['recovery']['mdt'])
    assert subprocess.check_output(['lfs','getdirstripe','-i',str(a.output)], text=True).strip() == placement
    assert subprocess.check_output(['lfs','getstripe','-m',str(a.output/'placement-probe.txt')], text=True).strip() == placement
    plan = json.loads(__loader__.get_data(str(Path(__file__).with_name('recovery-membership.json'))))
    group = next(g for g in config['formal_groups'] if g['id'] == a.group)
    assert 0 <= a.index < 32 and group['n'] == 60
    system = config['formal_systems'][a.index // 4]
    seed = config['formal_sampling_seeds'][a.index % 4]
    task = next(t for t in plan['tasks'] if t['group'] == a.group and t['index'] == a.index)
    assert (task['system'], task['seed']) == (system, seed)
    assert len(task['runs']) == len(group['runs']) == 9
    for run, work in zip(group['runs'], task['runs']):
        assert all(work[k] == v for k, v in run.items()) and work['origin'] in (OLD, NEW)
        if work['origin'] == OLD:
            assert work['member_prefix'] == f"{a.group}/task-{a.index}/{run['algorithm']}-{run['rung_label']}"
            assert len(work['done_sha256']) == 64 and set(work['final_stable']) == set(ARMS)

    sys.path.insert(0, str(ORIGINAL))
    import numpy as np
    import frozen_engine as e
    import actor_paths as actor
    assert Path(e.__file__) == ORIGINAL / 'frozen_engine.py' and Path(actor.__file__) == ORIGINAL / 'actor_paths.py'
    e.require_compute()
    meta = config['model_registry'][f'n60-s{system}']
    model = Path(meta['path'])
    assert file_sha(model) == meta['sha256']
    with np.load(model, allow_pickle=False) as archive:
        s = {key: archive[key].copy() for key in archive.files}
    s['certificate'] = meta['certificate']
    assert s['A'].shape == s['B'].shape == (60, 60) and s['basis'].shape == (60, 2)

    key = f'{a.group}-task-{a.index:02d}'
    bound = config['recovery']['task_archive_byte_bounds'][key]
    store = TaskStore(a.output / f'{key}.tar', a.output / f'{key}.jsonl', LOGICAL / key, bound)
    start = time.monotonic()
    original_io = install_io_only(e, actor, store)
    base = dict(experiment='X12', n=60, m=60, r=2, system=system, seed=seed)
    header = dict(group=group, index=a.index, spec=base, model=meta, job=os.environ['SLURM_JOB_ID'],
                  config_sha256=file_sha(a.config), source_sha256=source_sha(),
                  actor_sha256=SOURCE_FILES['actor_paths.py'], engine_sha256=SOURCE_FILES['frozen_engine.py'],
                  node_temporary_storage=node, original_formal_config_sha256=ORIGINAL_CONFIG_SHA256,
                  reused_archive_sha256=plan['reused_archive_sha256'], no_mid_path_resume=True)
    completed = []
    accepted = {OLD: 0, NEW: 0}
    try:
        e.save(store.root / 'BEGIN.json', header)
        for run, work in zip(group['runs'], task['runs']):
            alg, rung = run['algorithm'], run['rung']
            entry = next(x for x in config['all_schedules'] if x['n'] == 60 and x['rung'] == rung)
            count = entry['primitive_per_arm_per_algorithm']
            assert count == work['primitive_per_arm']
            assert 16 * (sum(entry['batches']['NPG']) + 17 * 16) == count
            assert 16 * (sum(entry['batches']['PI']) + 17 * 8) == count
            label = alg + '-' + run['rung_label']
            if work['origin'] == OLD:
                h, stable = work['done_sha256'], work['final_stable']
            else:
                # Unchanged numerical actor initializes states and both gains at K0.
                path = store.root / label
                stage_cfg = dict(H=16, nu=1., burn_blocks=16, eta=.2, schedules=entry['batches'])
                spec = dict(base, rung=rung, rung_label=run['rung_label'])
                result = actor.run(s, spec, stage_cfg, alg, path)
                assert result['primitive_transitions'] == dict.fromkeys(ARMS, count)
                h = e.sha(path / 'DONE.json')
                stable = {arm: next(r['stable'] for r in reversed(result['records']) if r['arm'] == arm) for arm in ARMS}
            completed.append(dict(algorithm=alg, rung=rung, path=label, done_sha256=h,
                                  primitive_per_arm=count, final_stable=stable, origin=work['origin']))
            accepted[work['origin']] += 2 * count
        e.save(store.root / 'DONE.json', dict(status='COMPLETE', **header, paths=completed,
                                             transitions_by_origin=accepted, seconds=time.monotonic() - start))
        proof = store.close()
        # Final receipt lives in the existing append journal; no extra loose file.
        proof.update(status='COMPLETE', kind='TASK_FINAL', group=a.group, index=a.index,
                     paths=completed, accepted_transitions=accepted, config_sha256=header['config_sha256'])
        proof.pop('journal_sha256')  # A receipt cannot include its own final SHA.
        with store.journal.open('ab') as f:
            f.write((json.dumps(proof, separators=(',', ':')) + '\n').encode())
            f.flush()
            os.fsync(f.fileno())
        print(json.dumps(dict(status='COMPLETE', group=a.group, index=a.index, paths=len(completed),
                              seconds=time.monotonic() - start, transitions=accepted)), flush=True)
    except Exception as exc:
        if not store.closed:
            try:
                e.save(store.root / 'HARD_FAILURE.json', dict(header, completed_paths=completed, error=repr(exc),
                    partial_path_transitions='Complete-stage checkpoints only', automatic_retry=False))
            finally:
                store.close()
        raise
    finally:
        e.sha, e.save, actor.save_npz = original_io


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--group', required=True)
    parser.add_argument('--index', type=int, required=True)
    main(parser.parse_args())
