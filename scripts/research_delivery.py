"""Audit completed Grace outputs and draw the final diagnostic comparisons."""
import csv
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path('/scratch/user/changze/lqr_experiments/results')
OLD = '0ce1ae9d35485951'
ISO = '7f5c6de07fb244ab'


def read(path):
    with path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for k, v in list(row.items()):
            if v in ('True', 'False'):
                row[k] = v == 'True'
            elif v == '':
                row[k] = None
            else:
                try:
                    row[k] = float(v)
                except ValueError:
                    pass
    return rows


def main():
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Grace compute nodes only')
    out = ROOT / f'dense-delivery-{ISO}' / 'report'
    out.mkdir(parents=True, exist_ok=True)
    profiles = [('scaling', OLD, 256), ('approximate', OLD, 160),
                ('actor', OLD, 20), ('resolved-critic', OLD, 64),
                ('isotropic-scaling', ISO, 128), ('isotropic-actor', ISO, 8)]
    audit = []
    for profile, release, expected in profiles:
        folder = ROOT / f'dense-{profile}-{release}'
        states = read(folder / 'report/task_status.csv')
        counts = {state: sum(r['status'] == state for r in states)
                  for state in sorted({r['status'] for r in states})}
        if len(states) != expected or counts != {'complete': expected}:
            raise RuntimeError(f'Incomplete {profile}: {counts}')
        audit.append(dict(profile=profile, expected=expected, states=counts))
    for profile, pattern, expected in [('references', 'reference-*.json', 64),
                                       ('pi-precision', 'precision-*.json', 8),
                                       ('projector-diagnostic', 'projector-*.json', 4)]:
        paths = sorted((ROOT / f'dense-{profile}-{OLD}' / 'raw').glob(pattern))
        if len(paths) != expected:
            raise RuntimeError(f'Incomplete {profile}: {len(paths)}')
        for path in paths:
            json.loads(path.read_text())
        audit.append(dict(profile=profile, expected=expected, files=len(paths)))
    thresholds = read(ROOT / f'dense-isotropic-scaling-{ISO}/report/thresholds.csv')
    selected_thresholds = [r for r in thresholds if r['mode'] == 'ce' and
                           r['n'] in (50, 100) and r['r'] in (1, 4) and
                           r['epsilon'] in (.1, .5)]
    actors = {}
    for family, release in [('actor', OLD), ('isotropic-actor', ISO)]:
        rows = read(ROOT / f'dense-{family}-{release}/report/records.csv')
        groups = defaultdict(list)
        for row in rows:
            if row['stage'] == 24 and row['r'] == 4 and row['algorithm'] in ('NPG', 'PG'):
                groups[row['n'], row['tail'], row['algorithm'], row['method']].append(row)
        actors[family] = [dict(n=n, tail=tail, algorithm=algorithm, method=method,
                              systems=len(values), stable=sum(r['stable'] for r in values),
                              transitions=values[0]['transitions'],
                              gap_mean=float(np.mean([r['gap'] for r in values]))
                              if all(r['stable'] and r['gap'] is not None for r in values) else None)
                          for (n, tail, algorithm, method), values in sorted(groups.items())]
    projectors = []
    for path in sorted((ROOT / f'dense-projector-diagnostic-{OLD}/raw').glob('projector-*.json')):
        data = json.loads(path.read_text())
        projectors.extend(dict(n=data['task']['n'], system_seed=data['task']['system_seed'], **r)
                          for r in data['records'] if r['stage'] == 24)
    old_refs = read(ROOT / f'dense-overview-{OLD}/report/actor_optimization_reference.csv')
    iso_refs = read(ROOT / f'dense-isotropic-overview-{ISO}/report/actor_optimization_reference.csv')
    ref_finals = [dict(family=family, **r) for family, rows in [('old', old_refs), ('isotropic', iso_refs)]
                  for r in rows if r['stage'] == 24 and r['r'] == 4]
    fits = json.loads((ROOT / f'dense-isotropic-scaling-{ISO}/report/power_fits.json').read_text())
    summary = dict(slurm_job_id=os.environ['SLURM_JOB_ID'], audit=audit,
                   core_configurations=sum(r['expected'] for r in audit),
                   isotropic_ce_thresholds=selected_thresholds,
                   isotropic_power_fits=fits, actor_final_means=actors,
                   projector_finals=projectors, matching_iteration_references=ref_finals,
                   source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out / 'research_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    colors = ['#777777', '#12699c', '#35a477', '#d7a24b']
    for i, n in enumerate((50, 100)):
        for j, alg in enumerate(('NPG', 'PG')):
            ax = axes[i, j]
            old = [r for r in actors['actor'] if r['n'] == n and r['tail'] == 0 and r['algorithm'] == alg]
            values = [next(r['gap_mean'] for r in old if r['method'] == method) for method in ('raw', 'truncated')]
            values.append(float(np.mean([r['gap'] for r in projectors if r['n'] == n and r['algorithm'] == alg])))
            values.append(float(np.mean([r['gap'] for r in old_refs if r['n'] == n and r['r'] == 4 and r['tail'] == 0
                                         and r['algorithm'] == alg and r['method'] == 'raw' and r['stage'] == 24])))
            bars = ax.bar(range(4), values, color=colors)
            ax.bar_label(bars, fmt='%.2f', padding=3)
            ax.set_xticks(range(4), ['Raw', 'Hard SVD', 'K0 projector\n(diagnostic)', 'Exact critic\n(24 steps)'])
            ax.set_title(f'{alg}, n={n}, r=4, exact rank')
            ax.set_ylabel('Absolute cost gap after 24 updates')
            ax.set_ylim(0, max(values) * 1.22)
            ax.grid(axis='y', alpha=.2)
    fig.suptitle('Old aligned stabilizer: geometry diagnosis, two systems\nProjector exploits benchmark-specific K0 geometry; exact critic is a noise-free reference', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .93))
    fig.savefig(out / 'geometry_diagnostic.png', dpi=160)
    plt.close(fig)
    refs = read(ROOT / f'dense-overview-{OLD}/report/converged_references.csv')
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, alg in zip(axes, ('NPG', 'PG', 'PI')):
        for n, color in ((50, '#12699c'), (100, '#ad4b2c')):
            groups = defaultdict(list)
            for row in refs:
                if row['algorithm'] == alg and row['n'] == n and row['method'] == 'truncated' and row['tail_shape'] == 'energy' and row['tail'] > 0:
                    if not row['converged'] or not row['stable']:
                        raise RuntimeError('Reference not converged/stable')
                    groups[row['tail'] ** 2].append(row['gap'])
            levels = sorted(groups)
            ax.loglog(levels, [np.mean(groups[x]) for x in levels], 'o-', color=color, label=f'n={n}')
        ax.set_title(f'{alg}: converged exact-critic reference')
        ax.set_xlabel(r'$\|B-B_r\|_F^2$')
        ax.set_ylabel('Absolute cost gap')
        ax.grid(alpha=.2)
        ax.legend()
    fig.tight_layout()
    fig.savefig(out / 'tail_floor.png', dpi=160)
    plt.close(fig)
    print(json.dumps(dict(audit=audit, isotropic_ce_thresholds=selected_thresholds, actor_final_means=actors), allow_nan=False))


if __name__ == '__main__':
    main()
