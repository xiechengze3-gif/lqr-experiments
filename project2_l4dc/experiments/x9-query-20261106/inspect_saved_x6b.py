"""Resource and byte-identity metadata only. No model/estimator execution."""
import csv
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
OLD = EXP / 'x6-20261101/X6b-protocol-v2'
RAW = OLD / 'deliveries/formal-v1/X6b/formal-v1'
CONFIG = OLD / 'prepared-formal-v1/formal-config.json'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

cfg = json.loads(CONFIG.read_text())
source_checks = []
for name, digest in cfg['scientific_sources'].items():
    path = OLD / name
    assert sha(path) == digest, name
    source_checks.append({'path': str(path.resolve()), 'sha256': digest})
models = []
for system in cfg['formal_systems']:
    meta = cfg['model_registry'][f'n24-s{system}']
    path = CONFIG.parent / meta['path']
    assert sha(path) == meta['sha256']
    models.append({'system': system, 'path': str(path.resolve()), 'sha256': meta['sha256']})
schedules = [r for r in cfg['all_schedules'] if r['n'] == 24]
paths = []
for group in [g for g in cfg['formal_groups'] if g['n'] == 24]:
    for index in range(32):
        folder = RAW / group['id'] / f'task-{index}'
        done = json.loads((folder / 'DONE.json').read_text())
        assert done['status'] == 'COMPLETE' and done['config_sha256'] == sha(CONFIG)
        assert done['source_sha256'] == cfg['scientific_sources']['formal_driver.py']
        assert done['actor_sha256'] == cfg['scientific_sources']['actor_paths.py']
        assert done['engine_sha256'] == cfg['scientific_sources']['frozen_engine.py']
        system, seed = cfg['formal_systems'][index // 4], cfg['formal_sampling_seeds'][index % 4]
        for run, saved in zip(group['runs'], done['paths']):
            path = folder / saved['path'] / 'DONE.json'
            assert sha(path) == saved['done_sha256']
            item = json.loads(path.read_text())
            spec = item['spec']
            assert (spec['n'], spec['system'], spec['seed']) == (24, system, seed)
            assert item['source_sha256'] == cfg['scientific_sources']['actor_paths.py']
            assert item['engine_sha256'] == cfg['scientific_sources']['frozen_engine.py']
            schedule = next(s for s in schedules if s['rung'] == spec['rung'])
            count = schedule['primitive_per_arm_per_algorithm']
            assert item['primitive_transitions'] == dict(dense=count, truncated=count)
            assert len(item['records']) == 2 * (len(schedule['batches'][run['algorithm']]) + 1)
            paths.append({'system': system, 'seed': seed, 'algorithm': run['algorithm'],
                          'rung': spec['rung'], 'path': str(path.resolve()), 'sha256': sha(path),
                          'primitive_per_arm': count})
assert len(paths) == 256
assert len({(p['system'], p['seed'], p['algorithm'], p['rung']) for p in paths}) == 256
with (EXP / 'x6-20261101/X6b-report-v1/summary.csv').open() as stream:
    summaries = [r for r in csv.DictReader(stream)
                 if r['n'] == '24' and r['ratio_kind'] == 'both_stable']
payload = {
    'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'status': 'SAVED_METADATA_IDENTITY_PASS_NO_MODEL_EXECUTION',
    'config': {'path': str(CONFIG.resolve()), 'sha256': sha(CONFIG)},
    'engine_fields': {key: cfg[key] for key in ['family', 'eta', 'nu', 'H', 'burn_blocks',
        'baseline_blocks', 'formal_systems', 'formal_sampling_seeds', 'selected_NPG_T',
        'selected_PI_T', 'p0_class_bound']},
    'sources': source_checks, 'models': models, 'schedules': schedules,
    'paired_paths': paths, 'existing_n24_summaries': summaries,
    'limits': 'Checks existing model/receipt bytes and counts only; no new alpha model, numeric equivalence trajectory, solve, bootstrap or re-analysis.'
}
with (HERE / 'x6b_reuse_identity_v1.json').open('x', encoding='utf-8') as stream:
    json.dump(payload, stream, indent=2)
print(json.dumps({'status': payload['status'], 'sources': len(source_checks),
                  'models': len(models), 'paired_paths': len(paths),
                  'primitive_per_arm_by_rung': [s['primitive_per_arm_per_algorithm'] for s in schedules]}))
