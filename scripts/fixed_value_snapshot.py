"""Plot completed jobs and atomic checkpoints without changing the experiment."""
import argparse
import json
from pathlib import Path

import numpy as np


def snapshot(manifest, root, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    cfg = json.loads(manifest.read_text())
    identity = json.loads((root / 'verification.json').read_text())['identity']
    destination.mkdir(parents=True, exist_ok=True)
    algorithms = cfg['algorithms']
    methods = ['dense', 'adaptive_1', 'known_rank']
    labels = ['Dense', 'Adaptive truncation (c=1)', 'Fixed-r reference']
    colors = ['#666666', '#0072b2', '#269449']
    summary = []
    snapshot_sources = []
    for scenario in ['orth-exact', 'orth-tail010', 'orth-tail003']:
        task = next(t for t in cfg['tasks'] if t['scenario'] == scenario
                    and t['profile'] == 'standard' and t['system_seed'] == 10
                    and t['trial_seed'] == 0)
        fig, axes = plt.subplots(2, len(algorithms), figsize=(17, 7.1))
        for col, algorithm in enumerate(algorithms):
            raw = root / algorithm / 'raw' / f"task-{task['id']:03d}.json"
            ckpt = root / algorithm / 'checkpoints' / f"task-{task['id']:03d}.npz"
            rows = []
            complete = raw.exists()
            if complete:
                data = json.loads(raw.read_text())
                assert data['identity'] == identity and data['task'] == task
                rows = data['records']
                source = str(raw)
            elif ckpt.exists():
                with np.load(ckpt, allow_pickle=False) as data:
                    assert json.loads(str(data['identity'])) == identity
                    rows = json.loads(str(data['records']))
                source = str(ckpt)
            else:
                source = None
            snapshot_sources.append(dict(scenario=scenario, algorithm=algorithm,
                                         source=source, complete=complete, records=rows))
            setting = cfg['profiles']['standard'][algorithm]
            completed_stage = max((r['stage'] for r in rows), default=0)
            used = cfg['burn'] + setting['batch']
            if algorithm in ('DIRECT_PI', 'NPG'):
                used = cfg['burn'] + (setting['batch'] + 1) * cfg['horizon']
            budget = used * setting['stages']
            state = 'complete' if complete else (f"partial {completed_stage}/{setting['stages']}" if rows else 'pending')
            for row_index, (metric, ylabel) in enumerate([
                    ('value', 'True average cost J(K)'),
                    ('gap', 'Absolute optimality gap J(K) - J*')]):
                ax = axes[row_index, col]
                for method, label, color in zip(methods, labels, colors):
                    observed = [r for r in rows if r['method'] == method and r.get('observed', True)]
                    finite = [r for r in observed if r['stable'] and r.get(metric) is not None
                              and np.isfinite(r[metric])]
                    xs = [r['actual_transitions'] / 1e6 for r in finite]
                    ys = [max(r[metric], 1e-12) if metric == 'gap' else r[metric] for r in finite]
                    ax.plot(xs, ys, color=color, lw=2 if method == 'adaptive_1' else 1.6,
                            marker='o', markersize=2.5, label=label,
                            linestyle='--' if method == 'known_rank' else '-')
                    failure = next((r for r in observed if r.get('failure_kind')), None)
                    if failure:
                        ax.plot([failure['actual_transitions'] / 1e6], [.96 - methods.index(method) * .06],
                                marker='x', color=color, transform=ax.get_xaxis_transform())
                        if row_index == 0:
                            ax.text(.03, .97 - methods.index(method) * .08,
                                    f"{label}: {failure['failure_kind']}",
                                    transform=ax.transAxes, va='top', fontsize=7, color=color)
                ax.set_xlim(0, budget / 1e6 * 1.02)
                if metric == 'gap':
                    if not rows:
                        ax.set_ylim(1e-3, 1e3)
                    ax.set_yscale('log')
                if not rows:
                    ax.text(.5, .5, 'Not run yet', ha='center', va='center', transform=ax.transAxes)
                ax.grid(alpha=.22)
                ax.set_xlabel('Actual primitive transitions (millions)')
                ax.set_ylabel(ylabel)
                ax.ticklabel_format(axis='x', style='plain')
                if row_index == 0:
                    ax.set_title(f"{algorithm.replace('_PI', ' PI')} | {state}\nAssigned budget: {budget:,}", fontsize=10)
            for method in methods:
                method_rows = [r for r in rows if r['method'] == method and r.get('observed', True)]
                last = method_rows[-1] if method_rows else {}
                failure = next((r for r in method_rows if r.get('failure_kind')), {})
                summary.append(dict(scenario=scenario, algorithm=algorithm, method=method,
                                    status=state, stage=last.get('stage'), assigned_budget=budget,
                                    actual_transitions=last.get('actual_transitions'),
                                    value=last.get('value'), gap=last.get('gap'),
                                    retained_rank=last.get('retained_rank'),
                                    failure_kind=failure.get('failure_kind')))
        spectrum_label = {'orth-exact': 'Exact rank 4',
                          'orth-tail010': 'Approximate rank 4: 46 tail singular values = 0.10',
                          'orth-tail003': 'Approximate rank 4: 46 tail singular values = 0.03'}[scenario]
        fig.suptitle(f'{spectrum_label} | n=m=50 | standard fixed budget\n'
                     'ONE system / ONE data seed; each route has its own budget; checkpoints are partial', fontsize=12)
        fig.legend(*axes[0, 0].get_legend_handles_labels(), loc='lower center', ncol=3, frameon=False)
        fig.tight_layout(rect=(0, .055, 1, .91))
        fig.savefig(destination / f'{scenario}_value_gap.png', dpi=160)
        plt.close(fig)
    result = dict(identity=identity, endpoints=summary, sources=snapshot_sources)
    (destination / 'snapshot.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    snapshot(args.manifest, args.root, args.destination)
