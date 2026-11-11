"""Summarize paired NPG critic calibration; numerical reporting on Slurm."""
import argparse
import csv
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np


def write(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(manifest, output):
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Numerical reporting requires Grace Slurm')
    manifest, root = Path(manifest), Path(output)
    data = json.loads(manifest.read_text())
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    report = root / 'report'
    report.mkdir(parents=True, exist_ok=True)
    old = Path('/scratch/user/changze/lqr_experiments/results/dense-isotropic-actor-7f5c6de07fb244ab/report/records.csv')
    with old.open(newline='') as f:
        prior = list(csv.DictReader(f))
    old_lookup = {(int(r['n']), float(r['tail']), int(r['system_seed']), r['method'], int(r['stage'])):r
                  for r in prior if r['algorithm'] == 'NPG'}
    actor_rows, fixed_rows, replay_checks, horizons = [], [], [], []
    errors = []
    for task_id, task in enumerate(data['actor_tasks']):
        path = root / 'raw' / f'actor-{task_id:02d}.json'
        if not path.exists():
            errors.append(f'missing actor {task_id}')
            continue
        payload = json.loads(path.read_text())
        if payload['manifest_sha256'] != digest or payload['task'] != task:
            raise RuntimeError('Actor provenance mismatch')
        for r in payload['records']:
            original = old_lookup[task['n'], task['tail'], task['system_seed'], r['method'], r['stage']]
            gap_error = abs(r['gap'] - float(original['gap']))
            if gap_error > 1e-8 * max(1, abs(r['gap'])) or r['transitions'] != int(original['transitions']):
                raise RuntimeError(f'Actor replay mismatch at {task_id}, {r["stage"]}')
            replay_checks.append(dict(task_id=task_id, method=r['method'], stage=r['stage'], absolute_gap_difference=gap_error))
            actor_rows.append(dict(task_id=task_id, n=task['n'], r=task['r'], tail=task['tail'], system_seed=task['system_seed'], **r))
        for ref in payload['references']:
            for h, values in ref['horizon_bias'].items():
                horizons.append(dict(task_id=task_id, n=task['n'], tail=task['tail'], method=ref['method'], stage=ref['stage'], H=int(h), **values))
    for task_id, spec in enumerate(data['fixed_tasks']):
        path = root / 'raw' / f'fixed-{task_id:03d}.json'
        if not path.exists():
            errors.append(f'missing fixed {task_id}')
            continue
        payload = json.loads(path.read_text())
        if payload['manifest_sha256'] != digest or payload['spec'] != spec:
            raise RuntimeError('Fixed-critic provenance mismatch')
        task = payload['task']
        for r in payload['records']:
            fixed_rows.append(dict(task_id=task_id, actor_task=spec['actor_task'], policy=spec['policy'],
                                   n=task['n'], r=task['r'], tail=task['tail'], system_seed=task['system_seed'], trial_seed=spec['trial_seed'], **r))
    write(report / 'actor_records.csv', actor_rows)
    write(report / 'fixed_records.csv', fixed_rows)
    write(report / 'horizon_bias.csv', horizons)
    write(report / 'replay_checks.csv', replay_checks)
    if errors:
        (report / 'summary.json').write_text(json.dumps(dict(complete=False, errors=errors), indent=2) + '\n')
        raise RuntimeError('Missing expected outputs: ' + ', '.join(errors))

    group = defaultdict(list)
    for row in fixed_rows:
        group[row['n'], row['tail'], row['policy'], row['method'], row['N']].append(row)
    aggregates = []
    metrics = ['total_error_fro2', 'total_error_op', 'finite_target_error_fro2', 'sampling_error_fro2',
               'population_truncation_bias_fro2', 'relative_E_error', 'relative_Z_error',
               'error_op_over_sigma_r', 'E_weighted', 'direction_cosine',
               'horizon_bias_relative_E', 'horizon_bias_fro2', 'gram_condition']
    for (n, tail, policy, method, count), values in sorted(group.items()):
        row = dict(n=n, tail=tail, policy=policy, method=method, N=count, expected=len(values),
                   stable_rate=float(np.mean([v['stable'] for v in values])),
                   descent_rate=float(np.mean([v['descent'] for v in values])),
                   transitions=values[0]['transitions'])
        for metric in metrics:
            row[metric + '_mean'] = float(np.mean([v[metric] for v in values]))
        row['cost_change_mean_all_stable'] = float(np.mean([v['cost_change'] for v in values])) if all(v['stable'] for v in values) else None
        row['exact_cost_change_mean'] = float(np.mean([v['exact_inf_gap'] - v['before_gap'] for v in values]))
        aggregates.append(row)
    write(report / 'fixed_aggregate.csv', aggregates)
    final_actor = [row for row in actor_rows if row['stage'] == 24]
    summary = dict(complete=True, actor_tasks=len(data['actor_tasks']), fixed_tasks=len(data['fixed_tasks']),
                   actor_stage_records=len(actor_rows), fixed_records=len(fixed_rows),
                   replay_records_checked=len(replay_checks),
                   maximum_replay_gap_difference=max(r['absolute_gap_difference'] for r in replay_checks),
                   final_actor_diagnostics=final_actor,
                   largest_prefix=[r for r in aggregates if r['N'] == 1048576],
                   cautions=['Fixed-policy probes are independent continuous trajectories with common prefixes',
                             'Exact critic updates are one-step counterfactuals at the SAME sampled policy',
                             'Approximate-rank finite-target error includes a representation tail; sampling_error compares to truncated population target',
                             'This audit diagnoses precision and does not fit dimension/rank complexity',
                             'Two system seeds and two critic trials per exact-rank calibration group',
                             'Relative error is measured against true weighted E=RK+Z, not merely against Z'],
                   source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   manifest_sha256=digest, slurm_job_id=os.environ['SLURM_JOB_ID'])
    (report / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for i, n in enumerate((50, 100)):
        for method, style, color in [('raw', '--', '#777777'), ('truncated', '-', '#12699c')]:
            rows = [r for r in actor_rows if r['n'] == n and r['tail'] == 0 and r['method'] == method]
            g = defaultdict(list)
            for row in rows:
                g[row['stage']].append(row)
            stages = sorted(g)
            for j, metric in enumerate(('gap', 'relative_E_error', 'direction_cosine')):
                vals = [np.mean([r[metric] for r in g[s]]) for s in stages]
                axes[i, j].plot(stages, vals, style, color=color, label=method)
            axes[i, 1].plot(stages, [np.mean([r['horizon_bias_relative_E'] for r in g[s]]) for s in stages], ':', color=color, alpha=.6, label=f'{method} H=16 bias')
        for j, label in enumerate(('Absolute cost gap', r'$\|(\widehat Z-Z)\Sigma^{1/2}\|_F/\|E\Sigma^{1/2}\|_F$', 'Direction cosine with true E')):
            ax = axes[i, j]
            ax.set_title(f'n={n}, r=4, exact rank')
            ax.set_ylabel(label)
            ax.set_xlabel('NPG update')
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
        axes[i, 0].set_yscale('log')
        axes[i, 1].set_yscale('log')
        axes[i, 1].axhline(1, color='black', alpha=.3, lw=.8)
        axes[i, 2].set_ylim(-1.05, 1.05)
    fig.tight_layout()
    fig.savefig(report / 'actor_critic_precision.png', dpi=160)
    plt.close(fig)
    policies = [('initial', 'Initial K0'), ('raw24', 'Raw actor after 24 updates'),
                ('truncated24', 'Truncated actor after 24 updates'), ('exact128', 'Exact-critic reference after 128 updates')]
    for figure_name, metric, ylabel, logarithmic in [('fixed_relative_error.png', 'relative_E_error_mean', 'Critic error / true update signal', True),
                                                   ('fixed_one_step.png', 'cost_change_mean_all_stable', 'Mean one-step cost change', False)]:
        fig, axes = plt.subplots(2, 4, figsize=(17, 8))
        for i, n in enumerate((50, 100)):
            for j, (policy, title) in enumerate(policies):
                ax = axes[i, j]
                for method, style, color in [('raw', '--', '#777777'), ('truncated', '-', '#12699c')]:
                    rows = sorted([r for r in aggregates if r['n'] == n and r['tail'] == 0 and r['policy'] == policy and r['method'] == method], key=lambda r:r['N'])
                    available = [r for r in rows if r[metric] is not None]
                    ax.plot([r['N'] for r in available], [r[metric] for r in available], style + 'o', color=color, label=method)
                    if logarithmic:
                        ax.axhline(rows[0]['horizon_bias_relative_E_mean'], color=color, linestyle=':', alpha=.5)
                    elif method == 'raw':
                        ax.axhline(rows[0]['exact_cost_change_mean'], color='#35a477', linestyle=':', label='Exact critic, same policy')
                    if len(available) != len(rows):
                        ax.text(.04, .9, 'Some outputs unstable; see success table', transform=ax.transAxes, fontsize=7)
                ax.set_xscale('log')
                if logarithmic:
                    ax.set_yscale('log')
                    ax.axhline(1, color='black', alpha=.3, lw=.8)
                else:
                    ax.axhline(0, color='black', alpha=.3, lw=.8)
                ax.set_title(f'n={n}: {title}', fontsize=9)
                ax.set_xlabel('Pulse blocks N (H=16)')
                ax.set_ylabel(ylabel)
                ax.grid(alpha=.2)
                ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(report / figure_name, dpi=160)
        plt.close(fig)
    print(json.dumps(dict(complete=True, actor_tasks=len(data['actor_tasks']), fixed_tasks=len(data['fixed_tasks']),
                          replay_max_difference=summary['maximum_replay_gap_difference'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.manifest, args.output)
