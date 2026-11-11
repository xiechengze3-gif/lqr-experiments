"""Readable NPG signal/noise and precision-intervention plots on Grace."""
import csv
import os
from pathlib import Path
import numpy as np


def read(path):
    with path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for k, v in list(row.items()):
            if v in ('True', 'False'):
                row[k] = v == 'True'
            elif not v:
                row[k] = None
            else:
                try:
                    row[k] = float(v)
                except ValueError:
                    pass
    return rows


def main():
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Plotting requires Grace Slurm')
    root = Path('/scratch/user/changze/lqr_experiments/results/npg-precision-e7ce4b139191d361/report')
    rows = read(root / 'fixed_aggregate.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for i, n in enumerate((50, 100)):
        for method, style, color in [('raw', '--', '#777777'), ('truncated', '-', '#12699c')]:
            points = sorted([r for r in rows if r['n'] == n and r['policy'] == 'exact128' and r['method'] == method], key=lambda r:r['N'])
            x = [r['N'] for r in points]
            axes[i, 0].loglog(x, [r['relative_E_error_mean'] for r in points], style + 'o', color=color, label=method)
            available = [r for r in points if r['cost_change_mean_all_stable'] is not None]
            axes[i, 1].semilogx([r['N'] for r in available], [r['cost_change_mean_all_stable'] for r in available], style + 'o', color=color, label=method)
            if method == 'raw':
                axes[i, 1].axhline(points[0]['exact_cost_change_mean'], color='#35a477', linestyle=':', label='Exact critic, same policy')
                axes[i, 0].text(.03, .04, f"H=16 population bias / E: {points[0]['horizon_bias_relative_E_mean']:.1e}", transform=axes[i, 0].transAxes, fontsize=9)
        axes[i, 0].axhline(1, color='black', alpha=.3, lw=.8)
        axes[i, 1].axhline(0, color='black', alpha=.5, lw=.8)
        for j, label in enumerate(('Weighted critic error / true E signal', 'Mean one-step cost change (negative = descent)')):
            ax = axes[i, j]
            ax.set_title(f'n={n}, r=4, exact rank; policy after 128 exact NPG updates')
            ax.set_xlabel('Pulse blocks N (H=16)')
            ax.set_ylabel(label)
            ax.grid(alpha=.2)
            ax.legend(fontsize=9)
    fig.suptitle('Fixed-policy precision intervention: two systems x two independent critic trials\nEach policy stays fixed while raw/truncated critics share data prefixes', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .93))
    fig.savefig(root / 'near_optimum_precision.png', dpi=160)
    plt.close(fig)
    actors = read(root / 'actor_records.csv')
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for i, n in enumerate((50, 100)):
        for method, style, color in [('raw', '--', '#777777'), ('truncated', '-', '#12699c')]:
            selected = [r for r in actors if r['n'] == n and r['tail'] == 0 and r['method'] == method]
            stages = sorted({r['stage'] for r in selected})
            for j, metric in enumerate(('relative_E_error', 'direction_cosine')):
                axes[i, j].plot(stages, [np.mean([r[metric] for r in selected if r['stage'] == s]) for s in stages], style, color=color, label=method)
        final = [r for r in actors if r['n'] == n and r['tail'] == 0 and r['stage'] == 24]
        axes[i, 0].text(.03, .04, f"Stage-24 H=16 bias / E <= {max(r['horizon_bias_relative_E'] for r in final):.1e}", transform=axes[i, 0].transAxes, fontsize=9)
        axes[i, 0].set_yscale('log'); axes[i, 0].axhline(1, color='black', alpha=.3, lw=.8)
        axes[i, 1].set_ylim(-1.05, 1.05)
        for j, label in enumerate(('Weighted critic error / true E signal', 'Direction cosine with true E')):
            ax = axes[i, j]
            ax.set_title(f'n={n}, r=4: original sampled NPG replay')
            ax.set_xlabel('NPG update'); ax.set_ylabel(label)
            ax.grid(alpha=.2); ax.legend()
    fig.tight_layout()
    fig.savefig(root / 'actor_precision_readable.png', dpi=160)
    plt.close(fig)
    print('Saved near_optimum_precision.png and actor_precision_readable.png', flush=True)


if __name__ == '__main__':
    main()
