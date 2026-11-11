"""Stdlib-only post-formal source/count/receipt audit. No numerical diagnostics."""
import argparse
import collections
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

OUT = Path('/scratch/user/changze/lqr_experiments/results/x9-20261106')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(config_path):
    config = json.loads(config_path.read_text())
    assert config['status'] == 'FORMAL_FROZEN'
    source_root = config_path.parent
    for name, digest in dict(config['scientific_sources'], **config['baseline_sources']).items():
        assert sha(source_root/name) == digest, name
    chain = json.loads((OUT/'submissions/FORMAL_CHAIN_v1.json').read_text())
    assert len(chain['jobs']) == 12 and chain['global_concurrency'] == 8
    jobs = ','.join(r['job'] for r in chain['jobs'])
    states = subprocess.check_output(['sacct', '-X', '--array', '-j', jobs, '-n', '-P',
                                     '--format=JobID,State,ElapsedRaw,AllocTRES'], universal_newlines=True)
    allocations = []
    for line in states.splitlines():
        if not line.strip():
            continue
        job, state, elapsed, tres = line.split('|')[:4]
        assert '.' not in job and state == 'COMPLETED'
        parsed = dict(v.split('=', 1) for v in tres.split(',') if '=' in v)
        assert float(parsed['billing']) == 1 and int(parsed['cpu']) == 1
        allocations.append(dict(job=job, state=state, elapsed_seconds=int(elapsed), billing_cores=1))
    assert len(allocations) == 384
    counts = collections.Counter(r['job'].split('_')[0] for r in allocations)
    assert all(counts[r['job']] == 32 for r in chain['jobs'])
    models = []
    for alpha, registry in config['model_registry'].items():
        assert len(registry) == 8
        for system, meta in registry.items():
            path = Path(meta['path'])
            assert str(path).startswith(str(OUT/'resource-v1')+'/')
            assert sha(path) == meta['sha256']
            cert = meta['certificate']
            assert cert['alpha'] == float(alpha) and cert['system'] == int(system)
            assert cert['physical_rank'] == 24 and cert['retained_order'] == 2
            models.append(dict(alpha=float(alpha), system=int(system), path=str(path), sha256=sha(path)))
    assert len(models) == 32
    refs = []
    bundles = []
    transition_sum = 0
    identities = set()
    for group in config['formal_groups']:
        for index in range(32):
            directory = OUT/'formal-v1'/group['id']/f'task-{index}'
            assert not (directory/'HARD_FAILURE.json').exists()
            done_path = directory/'DONE.json'
            done = json.loads(done_path.read_text())
            assert done['status'] == 'COMPLETE' and done['config_sha256'] == sha(config_path)
            assert done['source_sha256'] == config['scientific_sources']['x9_core.py']
            system, seed = config['formal_systems'][index//4], config['formal_sampling_seeds'][index % 4]
            assert done['system'] == system and done['seed'] == seed
            assert done['model'] == config['model_registry'][str(group['alpha'])][str(system)]
            assert len(done['paths']) == len(group['runs'])
            for run, ref in zip(group['runs'], done['paths']):
                path = directory/ref['path']/'DONE.json'
                assert sha(path) == ref['done_sha256']
                item = json.loads(path.read_text())
                spec = item['spec']
                assert item['algorithm'] == run['algorithm']
                assert (spec['n'], spec['m'], spec['r'], spec['physical_rank']) == (24, 24, 2, 24)
                assert (spec['system'], spec['seed'], spec['alpha'], spec['rung']) == (system, seed, group['alpha'], run['rung'])
                assert item['source_sha256'] == config['scientific_sources']['actor_paths.py']
                assert item['engine_sha256'] == config['scientific_sources']['frozen_engine.py']
                schedule = next(r for r in config['all_schedules'] if r['rung'] == run['rung'])
                expected = schedule['primitive_per_arm_per_algorithm']
                assert item['primitive_transitions'] == dict(dense=expected, truncated=expected)
                T = 16 if run['algorithm'] == 'NPG' else 8
                assert len(item['records']) == 2*(T+1) and len(item['artifacts']) == 2*T
                for arm in ['dense', 'truncated']:
                    rows = [r for r in item['records'] if r['arm'] == arm]
                    assert [r['stage'] for r in rows] == list(range(T+1))
                    assert rows[-1]['primitive_transitions'] == expected
                identity = (group['alpha'], system, seed, run['algorithm'], run['rung'])
                assert identity not in identities
                identities.add(identity)
                refs.append(dict(alpha=group['alpha'], system=system, seed=seed,
                                 algorithm=run['algorithm'], rung=run['rung'], path=str(path),
                                 sha256=sha(path), primitive_per_arm=expected))
                transition_sum += 2*expected
            bundles.append(dict(path=str(done_path), sha256=sha(done_path), group=group['id'], index=index))
    assert len(bundles) == 384 and len(refs) == 1024
    assert transition_sum == 128849584128
    proof = dict(status='FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS',
                 checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 source_sha256=sha(Path(__file__)), config_sha256=sha(config_path),
                 allocations=allocations, bundle_receipts=bundles, paired_path_receipts=refs,
                 frozen_model_files=models, bundles=384, paired_paths=1024, arm_paths=2048,
                 new_primitive_transitions=transition_sum,
                 formal_completed_Slurm_elapsed_SU=sum(r['elapsed_seconds']/3600 for r in allocations),
                 no_scientific_execution=True,
                 report_stage_full_estimate_file_hashes='PENDING_FROZEN_ANALYSIS_AND_SEALED_TRANSFER',
                 alpha_zero='REUSED_ORIGINAL_X6b_FULL_CELL_NO_NEW_TRANSITIONS')
    target = OUT/'formal-v1/FORMAL_COVERAGE_v1.json'
    assert not target.exists(), 'Inspect existing proof before any replay.'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status=proof['status'], bundles=384, paired_paths=1024,
                         proof_path=str(target), proof_sha256=sha(target),
                         formal_completed_Slurm_elapsed_SU=proof['formal_completed_Slurm_elapsed_SU'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, required=True)
    main(p.parse_args().config)
