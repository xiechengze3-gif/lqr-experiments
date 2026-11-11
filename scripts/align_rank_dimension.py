"""Re-tabulate existing saved observations; no simulations or model reconstruction.

Only the standard library is used. Historical sources are read-only. Protocol
cohorts stay separate, and baseline copies in the adaptive supplement are not
counted again. Primary budgets use fixed outputs, never best iterates.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = Path('E:/ChatGPT/Results/LQR_experiments')
TARGET = .1


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sources():
    cross = RESULTS/'cross-rank-complete-709f81b14811afb5/cross-rank-709f81b14811afb5'
    yield 'CE_prefix', 'CE', cross/'ce/raw', 'task-*.json', None
    for blocks in (4096, 16384, 65536, 262144, 1048576):
        yield 'NPG_constant80', 'NPG', cross/f'npg-{blocks}/raw', 'task-*.json', 80
    yield 'NPG_growing80', 'NPG', RESULTS/'npg-rank-complete-ea112fabeef4eb4a/npg-rank-ea112fabeef4eb4a/raw', 'task-*.json', 80
    yield 'NPG_nested256', 'NPG', RESULTS/'npg-budget-complete-e93b7ffa7fca793e/npg-budget-e93b7ffa7fca793e/raw', 'task-*.json', 256
    yield 'NPG_adaptive100_rank80', 'NPG', RESULTS/'historical-npg100-adaptive-20261012/adaptive/raw', 'case-*.json', 80
    for tag, cohort in [('core', 'PI_final8systems'), ('rank8', 'PI_rank8confirmation')]:
        yield cohort, 'Direct_Stein_PI', RESULTS/f'final-round-20261014/{tag}', 'n*.json', 8


def normalized(row, gap0):
    g = row.get('normalized_gap', row.get('relative_gap'))
    if g is None and row.get('gap') is not None and gap0 is not None:
        g = row['gap']/gap0
    if g is not None and not math.isfinite(g):
        raise ValueError('Nonfinite normalized gap')
    return g


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    curves, endpoints, provenance, exclusions = [], [], [], []
    paired = defaultdict(dict)
    for cohort, algorithm, directory, pattern, final_stage in sources():
        if not directory.is_dir():
            exclusions.append(dict(path=str(directory), reason='source_directory_missing'))
            continue
        for path in sorted(directory.glob(pattern)):
            data = load(path)
            case = data.get('case', {})
            task = data.get('task', data.get('meta', case.get('original_task', {})))
            if algorithm == 'NPG' and cohort == 'NPG_adaptive100_rank80':
                if case.get('benchmark') != 'rank80':
                    exclusions.append(dict(path=str(path), reason='tail256_separate_sensitivity_cohort'))
                    continue
            records = data.get('records', data.get('rows', []))
            if cohort == 'NPG_adaptive100_rank80':
                records = [r for r in records if r['method'] == 'adaptive_1']
            diag = data.get('diagnostics', {})
            gap0 = data.get('initial_gap', diag.get('initial_gap'))
            denominators = [r['gap']/r['relative_gap'] for r in records
                            if r.get('gap') is not None and r.get('relative_gap', 0) > 1e-12]
            if gap0 is None and denominators:
                gap0 = statistics.median(denominators)
            if gap0 is None or gap0 <= 0:
                raise ValueError(f'Missing initial gap: {path}')
            if any(not math.isclose(x, gap0, rel_tol=1e-8, abs_tol=1e-8) for x in denominators):
                raise ValueError(f'Inconsistent initial gap: {path}')
            provenance.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                   cohort=cohort, initial_gap=gap0,
                                   normalization='saved initial gap or verified saved gap/relative_gap'))
            groups = defaultdict(list)
            base = dict(cohort=cohort, algorithm=algorithm, n=task['n'], r=task['r'],
                        system_seed=task['system_seed'], sampling_seed=task.get('trial_seed', task.get('sampling_seed', 0)),
                        tail=task.get('tail', task.get('level', 0.)),
                        system_family='nested_773291' if cohort == 'NPG_nested256' else 'coupled_unstable_981113',
                        initial_gap=gap0, source=str(path))
            if algorithm == 'Direct_Stein_PI':
                base['blocks'] = task['blocks']
            for row in records:
                method = row.get('method', task.get('method'))
                method = {'raw': 'dense', 'truncated': 'known_rank', 'adaptive_1': 'adaptive'}.get(method, method)
                g = normalized(row, gap0)
                observed = row.get('observed', True)
                good = bool(observed and row.get('stable') and g is not None)
                out = dict(base, method=method, stage=row.get('stage'), transitions=row['transitions'],
                           observed=observed, stable=row.get('stable'), cost=row.get('cost'), gap=row.get('gap'),
                           g=g, success=bool(good and g <= TARGET), failure=row.get('failure'),
                           retained_rank=row.get('retained_rank'))
                curves.append(out)
                groups[method].append((row, out))
            for method, items in groups.items():
                actual = [r for raw, r in items if r['observed']]
                actual_budget = max((r['transitions'] for r in actual), default=0)
                if algorithm == 'CE':
                    chosen = items  # every predeclared prefix produces one fixed output
                else:
                    chosen = [items[-1]]
                for raw, row in chosen:
                    complete = algorithm == 'CE' or row['stage'] == final_stage
                    failure_rows = [(raw, row)] if algorithm == 'CE' else items
                    failure = next((r.get('failure') or ('controller_instability' if r.get('stable') is False else None)
                                    for original, r in failure_rows if r['observed'] and not r.get('stable')), None)
                    endpoint = dict(row, complete=complete, target=TARGET,
                                    planned_budget=row['transitions'],
                                    actual_budget=row['transitions'] if algorithm == 'CE' else actual_budget,
                                    failure=failure,
                                    status=('incomplete' if not complete else failure or 'completed'))
                    endpoint['success'] = bool(complete and row['success'])
                    endpoints.append(endpoint)
            if cohort in ('CE_prefix', 'NPG_growing80') and not base['tail']:
                paired[(base['n'], base['r'], base['system_seed'])][cohort] = gap0
    checks = []
    for key, values in sorted(paired.items()):
        if len(values) == 2:
            if not math.isclose(*values.values(), rel_tol=1e-8, abs_tol=1e-8):
                raise ValueError(f'CE/NPG system denominator mismatch: {key}')
            checks.append(dict(n=key[0], r=key[1], seed=key[2], status='initial_gap_matches', **values))
    grouped = defaultdict(list)
    for row in endpoints:
        grouped[(row['cohort'], row['n'], row['r'], row['tail'], row['method'], row['planned_budget'])].append(row)
    summaries = []
    for key, values in sorted(grouped.items()):
        cohort, n, rank, tail, method, budget = key
        gs = [v['g'] for v in values if v['complete'] and v['observed'] and v['stable'] and v['g'] is not None]
        summaries.append(dict(cohort=cohort, n=n, r=rank, tail=tail, method=method, budget=budget,
                              systems=len({v['system_seed'] for v in values}), trajectories=len(values),
                              complete=sum(v['complete'] for v in values),
                              successes=sum(v['success'] for v in values),
                              instabilities=sum(v['status'] == 'controller_instability' for v in values),
                              numerical_failures=sum(v['status'] not in ('completed', 'incomplete', 'controller_instability') for v in values),
                              median_g_stable_only=statistics.median(gs) if gs else None,
                              all_succeed=all(v['success'] for v in values)))
    attainment = []
    by_cell = defaultdict(list)
    for row in summaries:
        by_cell[(row['cohort'], row['n'], row['r'], row['tail'], row['method'])].append(row)
    for key, values in sorted(by_cell.items()):
        successes = [r['budget'] for r in values if r['all_succeed']]
        attainment.append(dict(cohort=key[0], n=key[1], r=key[2], tail=key[3], method=key[4],
                               minimum_tested_budget_all_systems=min(successes) if successes else None,
                               maximum_tested_budget=max(r['budget'] for r in values),
                               left_grid_censored=bool(successes and min(successes) == min(r['budget'] for r in values)),
                               right_censored=not bool(successes), target=TARGET,
                               definition='fixed-final output; all systems succeed; no interpolation'))
    coverage = []
    for cohort in sorted({r['cohort'] for r in endpoints}):
        for n in sorted({r['n'] for r in endpoints if r['cohort'] == cohort}):
            values = [r for r in endpoints if r['cohort'] == cohort and r['n'] == n and not r['tail']]
            coverage.append(dict(cohort=cohort, n=n, ranks=sorted({v['r'] for v in values}),
                                 seeds=sorted({v['system_seed'] for v in values}),
                                 methods=sorted({v['method'] for v in values})))
    for name, rows in [('curves', curves), ('endpoints', endpoints), ('summary', summaries),
                       ('sample_to_accuracy', attainment), ('matched_initial_gaps', checks), ('sources', provenance)]:
        write_csv(output/f'{name}.csv', rows)
    result = dict(status='HISTORICAL_REANALYSIS_COMPLETE', target=TARGET,
                  input_files=len(provenance), saved_observations=len(curves),
                  endpoint_outputs=len(endpoints), matched_CE_NPG_initial_gaps=len(checks),
                  new_simulated_transitions=0, coverage=coverage, exclusions=exclusions,
                  warning='Different cohorts, seeds, schedules and generators are not pooled. CE outputs share data prefixes; they are not independent trajectories. Initial-gap agreement is a numerical check, not a matrix hash identity.')
    (output/'inventory.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('coverage', 'exclusions')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=ROOT/'analysis/alignment-20261015')
    run(p.parse_args().output)
