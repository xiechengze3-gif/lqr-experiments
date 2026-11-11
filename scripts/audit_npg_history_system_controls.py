"""Read archived source identities and saved system metadata; no model execution."""
import ast
import collections
import hashlib
import json
from pathlib import Path
import sys


BASE = Path('/scratch/user/changze/lqr_experiments/results')


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function_source(path, name):
    body = path.read_text()
    nodes = ast.parse(body).body
    lines = body.splitlines()
    for i, node in enumerate(nodes):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = nodes[i + 1].lineno - 1 if i + 1 < len(nodes) else len(lines)
            return '\n'.join(lines[node.lineno - 1:end])
    return None


def archived_source(path, functions):
    return {'path': str(path), 'sha256': digest(path),
            'functions': {name: function_source(path, name) for name in functions}}


def compact_diagnostics(value):
    fields = ['Jstar', 'initial_gap', 'p0_bound', 'p0_actual', 'F0_op', 'A_op',
              'A_rho', 'B_op', 'B_fro2', 'K0_op', 'Q_condition', 'R_condition', 'hashes']
    return {k: value[k] for k in fields if k in value}


def legacy(study):
    root = BASE / study
    files = sorted((root / 'raw').glob('task-*.json'))
    assert files, study
    engine = root / 'source/engine/dense_scaling.py'
    if not engine.is_file():
        candidates = list((root / 'source').glob('**/dense_scaling.py'))
        if not candidates:
            # These two legacy releases declare the same frozen engine. Accept
            # the other archived copy only after every raw SHA matches it below.
            candidates = [BASE / 'npg-epoch-1661b50a636f09aa/source/engine/dense_scaling.py']
        assert len(candidates) == 1, (study, candidates)
        engine = candidates[0]
    expected = digest(engine)
    groups = collections.defaultdict(list)
    examples = []
    for path in files:
        value = read(path)
        assert value['engine_sha256'] == expected, path
        task, diag = value['task'], value['diagnostics']
        plant = tuple(task[k] for k in ['n', 'r', 'system_seed'])
        groups[plant].append(diag)
        examples.append({'file': str(path), 'task': task,
                         'diagnostics': compact_diagnostics(diag),
                         'engine_sha256': value['engine_sha256']})
    identical = all(all(item == values[0] for item in values) for values in groups.values())
    result = {'study': study, 'raw_final_tasks': len(files), 'plant_cells': len(groups),
              'all_raw_engine_hashes_match_frozen': True,
              'saved_diagnostics_identical_within_plant_across_schedules': identical,
              'frozen_engine': archived_source(engine, ['system', 'eta']),
              'saved_parameter_rows': examples}
    reference = root / 'reference.json'
    if reference.is_file():
        data = read(reference)
        records = data.get('records', [])
        result['stage0_reference'] = [row for row in records if row.get('stage') == 0]
        result['reference_sha256'] = digest(reference)
    return result


def nested():
    root = BASE / 'npg-budget-e93b7ffa7fca793e'
    data = read(root / 'reference.json')
    systems = data['systems']
    checks = {}
    for seed in sorted({s['system_seed'] for s in systems}):
        rows = [s for s in systems if s['system_seed'] == seed]
        checks[str(seed)] = {
            name: len({s['hashes'][name] for s in rows}) == 1
            for name in ['A', 'Q', 'R', 'K0']}
    assert all(all(row.values()) for row in checks.values())
    source = root / 'source/scripts/npg_budget_system.py'
    result = {'study': root.name, 'systems': len(systems),
              'saved_matrix_hashes_identical_across_rank_by_system_seed': checks,
              'saved_parameter_rows': [dict(n=s['n'], r=s['r'], system_seed=s['system_seed'],
                                             **compact_diagnostics(s)) for s in systems],
              'frozen_generator': archived_source(source, ['system']),
              'reference_sha256': digest(root / 'reference.json'),
              'stage0_reference': [r for r in data['records'] if r.get('stage') == 0]}
    assert data['system_sha256'] == result['frozen_generator']['sha256']
    return result


def controlled100():
    root = BASE / 'rank-sweep100-confirm-20261016'
    verification = root / 'verification.json'
    result = {'study': root.name, 'verification_exists': verification.is_file()}
    if verification.is_file():
        result['verification_sha256'] = digest(verification)
        result['verification'] = read(verification)
    for name in ['frozen/scripts/rank_sweep100.py', 'frozen/scripts/rank_sweep100_remote.py']:
        path = root / name
        if path.is_file():
            result[path.name] = archived_source(path, ['system', 'verify'])
    return result


def main():
    # Assertions compare existing metadata, not reconstructed matrices or control costs.
    result = {'operation': 'read-only frozen-source and saved-system-parameter audit',
              'legacy_epoch': legacy('npg-epoch-1661b50a636f09aa'),
              'legacy_rank80': legacy('npg-rank-ea112fabeef4eb4a'),
              'nested_rank256': nested(), 'controlled_rank100': controlled100(),
              'new_simulations': 0, 'new_control_solves': 0, 'new_Slurm_jobs': 0}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
