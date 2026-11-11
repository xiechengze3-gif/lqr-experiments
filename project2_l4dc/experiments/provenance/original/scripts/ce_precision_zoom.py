"""Fine fixed-prefix CE evaluation. Numerical work only on Slurm compute nodes."""
import argparse
import csv
import json
import os
import resource
import time
from collections import defaultdict
from pathlib import Path

from ce_high_rank import ROOT, config, extended_system, read, sha
from dense_scaling import atomic_json, ce, require_compute
import numpy as np


def run(cfg, out, index):
    item = cfg['datasets'][index]
    task = item['task']
    old_path = ROOT/item['bundle_path']
    assert sha(old_path) == item['sha256']
    dest = out/'raw'/f'task-{index:03d}.json'
    assert not dest.exists(), 'No untracked automatic reruns'
    start = time.monotonic()
    system = extended_system(task)
    rows, _ = ce(dict(task, budgets=cfg['budgets'], sigma=cfg['sigma']), system)
    old = {(r['N'], r['method']): r for r in read(old_path)['records']}
    checks = []
    for row in rows:
        key = row['N'], row['method']
        if key not in old: continue
        expected = old[key]
        assert row['stable'] == expected['stable']
        for name in ('gap', 'cost', 'rho', 'B_error_fro2', 'A_error_op'):
            if row.get(name) is not None:
                np.testing.assert_allclose(row[name], expected[name], rtol=1e-8, atol=1e-7)
        checks.append(dict(N=row['N'], method=row['method'], status='PASS'))
    assert len(checks) == 12
    atomic_json(dest, dict(task=task, records=rows, historical_replay_checks=checks,
        identity=sha(ROOT/'manifest.json'), historical_source_sha256=item['sha256'],
        actual_physical_transitions=max(cfg['budgets'])+cfg['burn'],
        seconds=time.monotonic()-start, peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        slurm_job_id=os.environ['SLURM_JOB_ID'], execution_location='Grace Slurm compute node'))
    print(json.dumps(dict(rank=task['r'], seed=task['system_seed'], checks=len(checks), seconds=time.monotonic()-start)), flush=True)


def attainment(values, epsilon):
    values = sorted(values, key=lambda r: r['budget'])
    okay = [v['budget'] for v in values if v['success']]
    first = min(okay) if okay else None
    earlier = [v['budget'] for v in values if first is not None and v['budget'] < first]
    sustained = next((v['budget'] for i, v in enumerate(values) if all(w['success'] for w in values[i:])), None)
    return dict(first_tested_budget=first, previous_tested_budget=max(earlier) if earlier else None,
                sustained_tested_budget=sustained, right_censored=first is None,
                epsilon=epsilon)


def report(cfg, out):
    ident = sha(ROOT/'manifest.json')
    endpoints, replay, sources = [], [], []
    for index, item in enumerate(cfg['datasets']):
        p = out/'raw'/f'task-{index:03d}.json'
        data = read(p)
        assert data['identity'] == ident and data['task'] == item['task']
        task = data['task']
        replay += [dict(rank=task['r'], seed=task['system_seed'], **r) for r in data['historical_replay_checks']]
        sources.append(dict(path=str(p), sha256=sha(p), rank=task['r'], seed=task['system_seed']))
        for row in data['records']:
            endpoints.append(dict(rank=task['r'], seed=task['system_seed'], method=row['method'],
                budget=row['transitions'], absolute_gap=row.get('gap'), stable=row['stable'],
                success=bool(row['stable'] and row.get('gap') is not None and row['gap'] <= cfg['absolute_epsilon'])))
    assert len(endpoints) == 8*2*len(cfg['budgets']) and len(replay) == 96
    groups = defaultdict(list)
    for row in endpoints: groups[row['rank'], row['method'], row['budget']].append(row)
    summary = []
    for (rank, method, budget), rows in sorted(groups.items()):
        assert len(rows) == 2 and {r['seed'] for r in rows} == {0, 1}
        finite = [r['absolute_gap'] for r in rows if r['stable'] and r['absolute_gap'] is not None]
        summary.append(dict(rank=rank, method=method, budget=budget, successes=sum(r['success'] for r in rows),
            success=all(r['success'] for r in rows), worst_absolute_gap=max(finite) if len(finite) == 2 else None,
            mean_absolute_gap=sum(finite)/2 if len(finite) == 2 else None))
    crossings, seed_crossings = [], []
    for rank in cfg['ranks']:
        for method in cfg['methods']:
            crossings.append(dict(rank=rank, method=method, **attainment(
                [r for r in summary if r['rank'] == rank and r['method'] == method], cfg['absolute_epsilon'])))
            for seed in cfg['system_seeds']:
                seed_crossings.append(dict(rank=rank, method=method, seed=seed, **attainment(
                    [r for r in endpoints if r['rank'] == rank and r['method'] == method and r['seed'] == seed], cfg['absolute_epsilon'])))
    equal = 0
    for seed in cfg['system_seeds']:
        for n in cfg['budgets']:
            a, b = [r for r in endpoints if r['rank'] == 100 and r['seed'] == seed and r['budget'] == n+cfg['burn']]
            assert a['stable'] == b['stable']
            if a['absolute_gap'] is not None:
                np.testing.assert_allclose(a['absolute_gap'], b['absolute_gap'], rtol=1e-8, atol=1e-7)
            equal += 1
    dest = out/'report'
    dest.mkdir(parents=True, exist_ok=True)
    for name, rows in [('endpoints', endpoints), ('success_by_budget', summary), ('sample_to_accuracy', crossings),
                        ('per_seed_attainment', seed_crossings), ('historical_replay_checks', replay), ('sources', sources)]:
        with (dest/f'{name}.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = dict(zip(cfg['ranks'], ['#2563eb', '#ea580c', '#16a34a', '#9333ea']))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), sharey=True)
    for ax, method, title in zip(axes, cfg['methods'], ['Dense CE', 'Known-rank CE']):
        for rank in cfg['ranks']:
            vals = [r for r in summary if r['rank'] == rank and r['method'] == method and r['worst_absolute_gap'] is not None]
            ax.plot([r['budget'] for r in vals], [r['worst_absolute_gap'] for r in vals], color=colors[rank], label=f'r={rank}')
            crossing = next(r for r in crossings if r['rank'] == rank and r['method'] == method)
            if crossing['first_tested_budget']:
                ax.scatter([crossing['first_tested_budget']], [.1], color=colors[rank], s=28, zorder=5)
        ax.axhline(.1, color='#dc2626', ls='--', lw=1)
        ax.set(xlim=(32768, 225792), ylim=(.045, .17), xlabel='Total transitions (includes 512 burn)', title=title)
        ax.ticklabel_format(axis='x', style='sci', scilimits=(0, 0))
        ax.grid(alpha=.2)
        ax.legend()
    axes[0].set_ylabel('Worst absolute J-Jstar across 2 systems')
    fig.suptitle('100d CE | fixed absolute target 0.1 | same systems and sample streams')
    fig.tight_layout()
    for ext in ('png', 'svg'): fig.savefig(dest/f'precision_zoom.{ext}', dpi=170)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.7))
    for method, label, color, offset in [('raw', 'Dense CE', '#2563eb', -.16), ('truncated', 'Known-rank CE', '#ea580c', .16)]:
        vals = [next(r for r in crossings if r['rank'] == rank and r['method'] == method) for rank in cfg['ranks']]
        xs = np.arange(4)+offset
        ax.bar(xs, [r['first_tested_budget'] for r in vals], width=.3, color=color, label=label)
        for x, r in zip(xs, vals): ax.text(x, r['first_tested_budget']+2300, f"{r['first_tested_budget']:,}", ha='center', fontsize=8)
    ax.set_xticks(range(4), cfg['ranks'])
    ax.set(xlabel='True rank', ylabel='First tested total transitions: 2/2 systems attain', ylim=(0, 225000))
    ax.set_title('100d CE | absolute J-Jstar <= 0.1 | fine fixed budget grid')
    ax.legend()
    ax.grid(axis='y', alpha=.2)
    fig.tight_layout()
    for ext in ('png', 'svg'): fig.savefig(dest/f'samples_to_precision.{ext}', dpi=170)
    plt.close(fig)
    result = dict(status='COMPLETE', absolute_epsilon=.1, datasets=8, prefix_count=len(cfg['budgets']),
                  records=len(endpoints), unstable_records=sum(not r['stable'] for r in endpoints),
                  historical_replay_checks=len(replay), full_rank_equality_checks=equal,
                  actual_new_physical_transitions=8*(max(cfg['budgets'])+cfg['burn']),
                  crossings=crossings, per_seed_crossings=seed_crossings,
                  slurm_job_id=os.environ['SLURM_JOB_ID'])
    atomic_json(dest/'summary.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['run', 'report'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-id', type=int)
    args = parser.parse_args()
    cfg = config()
    if args.mode == 'run': run(cfg, args.output, args.task_id)
    else: report(cfg, args.output)
