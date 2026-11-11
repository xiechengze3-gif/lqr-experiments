"""Render reviewed plots from completed report, retaining the original archive."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from dense_scaling import require_compute, atomic_json


def main(root):
    root = Path(root)
    report, out = root/'report', root/'review-v2'
    out.mkdir(exist_ok=True)
    summary = json.loads((report/'summary.json').read_text())
    thresholds = summary['thresholds']
    endpoints = list(csv.DictReader((report/'endpoints.csv').open()))
    colors = {'raw': '#c44e52', 'truncated': '#4c72b0'}
    markers = {'attained': 'o', 'left_censored': 'v', 'right_censored': '^'}
    offset = {'raw': .97, 'truncated': 1.03}
    censor_legend = [Line2D([0], [0], color='#555555', marker=m, linestyle='None', label=l)
        for m, l in (('v', 'smallest tested budget already succeeds'),
                     ('^', 'not attained through largest tested budget'))]

    def save(fig, name):
        fig.savefig(out/f'{name}.png', dpi=180)
        fig.savefig(out/f'{name}.pdf')
        plt.close(fig)

    for algorithm, power in (('CE', 1), ('PI-LSTD', 2), ('NPG', 2)):
        tag = algorithm.lower().replace('-', '_')
        fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
        for ax, n in zip(axes[:, 0], (50, 100)):
            for method, color in colors.items():
                for rank in (1, 4, 16):
                    rows = [e for e in endpoints if e['algorithm'] == algorithm and e['method'] == method
                        and int(e['n']) == n and int(e['r']) == rank and float(e['tail']) == 0]
                    xx, yy = [], []
                    for budget in sorted(set(int(e['planned_transitions']) for e in rows)):
                        group = [e for e in rows if int(e['planned_transitions']) == budget]
                        assert len(group) == 2
                        if all(e['eligible'] == 'True' for e in group):
                            xx.append(budget)
                            yy.append(max(1e-10, float(np.mean([float(e['gap']) for e in group]))))
                        else:
                            ax.scatter(budget*offset[method], .96 if method == 'raw' else .91,
                                       color=color, marker='x', transform=ax.get_xaxis_transform())
                    ax.plot(xx, yy, color=color, marker='o',
                            linestyle={1: '-', 4: '--', 16: ':'}[rank], label=f'{method}, r={rank}')
            all_budgets = [int(e['planned_transitions']) for e in endpoints if e['algorithm'] == algorithm
                           and int(e['n']) == n and float(e['tail']) == 0]
            ax.set_xlim(min(all_budgets)*.8, max(all_budgets)*1.2)
            ax.set(xscale='log', yscale='log', xlabel='Primitive transitions (fixed output)',
                   ylabel='Mean absolute gap (2 systems)',
                   title=f'{algorithm}, n={n}; top crosses = failed paired outputs')
            ax.grid(alpha=.2)
            ax.legend(fontsize=8, ncol=2)
        for ax, n in zip(axes[:, 1], (50, 100)):
            for method, color in colors.items():
                rows = sorted([t for t in thresholds if t['algorithm'] == algorithm
                    and t['method'] == method and t['n'] == n and t['tail'] == 0
                    and t['epsilon'] == 1.], key=lambda t: t['r'])
                measured = [t for t in rows if t['budget'] is not None]
                ax.plot([t['r'] for t in measured], [t['budget'] for t in measured], color=color, label=method)
                for t in rows:
                    ax.scatter(t['r']*offset[method], t['budget'] or t['lower_budget'],
                               color=color, marker=markers[t['status']], zorder=3, s=48)
            ax.set(xscale='log', yscale='log', xlabel='Rank r',
                   ylabel='Minimum tested primitive transitions', title=f'n={n}, absolute gap <= 1')
            ax.set_xticks([1, 2, 4, 8, 16], labels=['1', '2', '4', '8', '16'])
            ax.grid(alpha=.2)
            ax.legend(fontsize=9)
        fig.legend(handles=censor_legend, loc='outside lower center', ncol=2, fontsize=9)
        save(fig, f'{tag}_batch_rank_review')

        fig, axes = plt.subplots(2, 3, figsize=(13, 8), constrained_layout=True)
        for col, eps in enumerate((5., 2., 1.)):
            for method, color in colors.items():
                rows = sorted([t for t in thresholds if t['algorithm'] == algorithm
                    and t['method'] == method and t['tail'] == 0 and t['r'] == 4
                    and t['epsilon'] == eps], key=lambda t: t['n'])
                measured = [t for t in rows if t['budget'] is not None]
                for row, normalized in ((0, False), (1, True)):
                    ax = axes[row, col]
                    scale = lambda t: t['r']*t['n']**power if normalized else 1
                    ax.plot([t['n'] for t in measured], [t['budget']/scale(t) for t in measured],
                            color=color, label=method)
                    for t in rows:
                        ax.scatter(t['n']*offset[method], (t['budget'] or t['lower_budget'])/scale(t),
                                   color=color, marker=markers[t['status']], s=40, zorder=3)
                    ax.set(xscale='log', yscale='log', xlabel='Dimension n (r=4)',
                           ylabel=f'M / (r n^{power})' if normalized else 'Primitive transitions',
                           title=f'{algorithm}, gap <= {eps:g}')
                    ax.set_xticks([25, 50, 75, 100], labels=['25', '50', '75', '100'])
                    ax.grid(alpha=.2)
                    ax.legend(fontsize=8)
        fig.legend(handles=censor_legend, loc='outside lower center', ncol=2, fontsize=9)
        save(fig, f'{tag}_dimension_collapse_review')

    fig, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
    tails = (0., .01, .1, .3)
    for ax, algorithm in zip(axes, ('CE', 'PI-LSTD', 'NPG')):
        for n in (50, 100):
            for method, color in colors.items():
                rows = [e for e in endpoints if e['algorithm'] == algorithm and int(e['n']) == n
                    and int(e['r']) == 4 and e['method'] == method]
                largest = max(int(e['planned_transitions']) for e in rows)
                xx, yy = [], []
                for position, tail in enumerate(tails):
                    group = [e for e in rows if float(e['tail']) == tail
                             and int(e['planned_transitions']) == largest]
                    assert len(group) == 2
                    if all(e['eligible'] == 'True' for e in group):
                        xx.append(position)
                        yy.append(max(1e-10, float(np.mean([float(e['gap']) for e in group]))))
                    else:
                        ax.scatter(position, .96, color=color, marker='x', transform=ax.get_xaxis_transform())
                ax.plot(xx, yy, color=color, marker='o', linestyle='-' if n == 50 else '--',
                        label=f'{method}, n={n}')
        ax.set(yscale='log', xlabel='Frobenius tail of B (categorical levels)',
               ylabel='Mean final absolute gap', title=f'{algorithm}, r=4, largest tested budget')
        ax.set_xticks(range(4), labels=['0', '0.01', '0.1', '0.3'])
        ax.grid(alpha=.2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=4, fontsize=9)
    save(fig, 'approximate_tail_review')
    atomic_json(out/'review_provenance.json', dict(slurm_job_id=os.environ['SLURM_JOB_ID'],
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        report_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (report/'summary.json', report/'endpoints.csv')},
        artifacts={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(out.iterdir()) if p.suffix in ('.png', '.pdf')},
        note='Original numerical report and archive unchanged. Scatter markers shifted horizontally 3% only to show overlapping methods; original ranks/dimensions retained in ticks, lines and data. Failure crosses at axes top have no finite cost value. Tail categories have explicit labels.'))


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    main(parser.parse_args().output)
