"""Compare saved CE results and exact system geometry; collect no new data."""
import ast
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    import dense_scaling as ds

    current = Path(r'E:\ChatGPT\Results\LQR_experiments\rank-sweep100-confirm-20261016')
    historical = Path(r'E:\ChatGPT\Results\LQR_experiments\cross-rank-complete-709f81b14811afb5\cross-rank-709f81b14811afb5\ce\raw')
    output = ROOT / 'analysis/ce-comparison-20261018'
    output.mkdir(parents=True, exist_ok=True)
    hashes = {}

    def read(path):
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return json.loads(path.read_text(encoding='utf-8'))

    cfg = read(current / 'resolved_config.json')
    threshold_source = current / 'report-confirm/sample_complexity.csv'
    hashes[str(threshold_source)] = hashlib.sha256(threshold_source.read_bytes()).hexdigest()
    with threshold_source.open(newline='', encoding='utf-8-sig') as stream:
        complexity = list(csv.DictReader(stream))
    for path in (Path(__file__), ROOT / 'dense_scaling.py'):
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    metrics = []
    for rank in (2, 8, 100):
        data = [read(current / f'raw/ce-r{rank:03d}-s{seed:04d}.json')['records'] for seed in range(100, 130)]
        for count in (4096, 16384, 65536):
            paired = {m: [next(q for q in rows if q['method'] == m and q['ols_samples'] == count) for rows in data] for m in ('dense', 'truncated')}
            values = {m: {k: float(np.median([q[k] for q in rows])) for k in ('gap', 'B_error_fro2')} for m, rows in paired.items()}
            metrics.append(dict(rank=rank, seeds=30, ols_samples=count, transitions=count+cfg['burn'],
                                **{f'{m}_{k}': value for m, fields in values.items() for k, value in fields.items()},
                                B_squared_error_ratio=values['dense']['B_error_fro2']/values['truncated']['B_error_fro2'],
                                gap_ratio=values['dense']['gap']/values['truncated']['gap']))
    old = {}
    for path in sorted(historical.glob('task-*.json')):
        d = json.loads(path.read_text(encoding='utf-8')); t = d['task']
        if t['n'] == 100 and t['r'] in (1, 2, 4) and t['tail'] == 0:
            old.setdefault(t['r'], []).append(read(path))
    old_metrics = []
    for rank, data in old.items():
        for method in ('raw', 'truncated'):
            points = sorted({q['transitions'] for q in data[0]['records'] if q['method'] == method})
            attained = []
            for budget in points:
                rows = [next(q for q in d['records'] if q['transitions'] == budget and q['method'] == method) for d in data]
                if all(q['stable'] and q['gap'] is not None and q['gap'] <= .1 for q in rows):
                    attained.append(budget)
            old_metrics.append(dict(rank=rank, method=method, system_seeds=[d['task']['system_seed'] for d in data], absolute_target=.1,
                                    first_tested_two_system_success=min(attained) if attained else None))
    # Execute just the existing generator function, avoiding its Unix-only CLI imports.
    source = ROOT / 'scripts/ce_high_rank.py'
    hashes[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
    node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'extended_system')
    namespace = dict(vars(ds)); namespace.update(np=np, math=math, solve_discrete_lyapunov=solve_discrete_lyapunov)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    geometry = []
    with threadpool_limits(1):
        for rank in (2, 100):
            path = current / f'frozen/system_inputs/r{rank:03d}.npz'
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            with np.load(path) as arrays:
                s = {k: arrays[k].copy() for k in arrays.files}
            task = dict(n=100, m=100, r=rank, system_seed=0, trial_seed=0, family='coupled_unstable', stabilizer='isotropic', tail=0., tail_shape='energy')
            previous = namespace['extended_system'](task)
            if rank < 100:
                original = ds.system(task)
                for key in ('A', 'B', 'Q', 'R', 'K0'):
                    np.testing.assert_array_equal(previous[key], original[key])
            for label, model, sigma in (('current', s, 2.), ('historical_seed0', previous, 1.)):
                f = model['A'] - model['B'] @ model['K0']
                p = solve_discrete_lyapunov(f.T, model['Q'] + model['K0'].T @ model['R'] @ model['K0'])
                covariance = solve_discrete_lyapunov(f, np.eye(100) + sigma**2 * model['B'] @ model['B'].T)
                geometry.append(dict(family=label, rank=rank, sigma=sigma,
                    Q_eigenvalue_range=np.linalg.eigvalsh(model['Q'])[[0,-1]].tolist(),
                    R_eigenvalue_range=np.linalg.eigvalsh(model['R'])[[0,-1]].tolist(),
                    K0_rank=int(np.linalg.matrix_rank(model['K0'],tol=1e-10)),
                    F0_operator_norm=float(np.linalg.norm(f,2)), P0_operator_norm=float(np.linalg.norm(p,2)),
                    initial_gap=float(np.trace(p)-model['Jstar']),
                    stationary_exploration_covariance_trace=float(np.trace(covariance))))
    thresholds = [q for q in complexity if q['route']=='ce' and float(q['epsilon'])==cfg['epsilon']]
    report = dict(status='complete_saved_result_review', new_primitive_transitions=0,
        current_absolute_target=cfg['epsilon'], current_sample_complexities=thresholds,
        current_fixed_budget_medians=metrics, historical_coarse_thresholds=old_metrics,
        exact_system_geometry=geometry, source_sha256=hashes,
        interpretation_limits=[
            'Within each rank both CE methods use the same OLS Ahat/Bhat; only Bhat is truncated.',
            'B squared estimation error, control gap, and fixed-target budget ratios are different quantities.',
            'Historical two-system success and present 27/30 conditional-data-seed success are different criteria.',
            'Exploration strength, costs, dynamics, initial policy and rank construction differ across campaigns.',
            'No known-A or known-B intervention was run; A-versus-B causal error contributions remain unidentified.',
            'No previously delivered numerical results or archives were modified.'])
    (output/'audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (output/'current_fixed_budget_medians.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(metrics[0]));writer.writeheader();writer.writerows(metrics)
    print(json.dumps(dict(status=report['status'],report=str(output/'audit.json'),new_primitive_transitions=0),ensure_ascii=False))


if __name__ == '__main__':
    main()
