"""Dimension, reference-convergence and measured-exponent plots on Grace only."""
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


COLORS = {'raw': '#b43b39', 'truncated': '#1769aa'}
RANKS = (1, 2, 4, 8, 16)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(root):
    root = Path(root)
    report = root / 'report'
    summary = json.loads((report / 'summary.json').read_text())
    audit = json.loads((report / 'numerical_audit.json').read_text())
    assert summary['status'] == 'complete' and audit['status'] == 'PASS'
    with (report / 'same_budget.csv').open(newline='') as stream:
        paired = list(csv.DictReader(stream))
    references = json.loads((report / 'population_references.json').read_text())
    thresholds = summary['thresholds']
    # Cell identities come from verified endpoint rows, without reconstructing models.
    with (report / 'endpoints.csv').open(newline='') as stream:
        endpoint_rows = list(csv.DictReader(stream))
    cells = {(int(e['n']), int(e['r']), e['tail_mode'], float(e['level'])): e['cell'] for e in endpoint_rows}
    def cell(n, r, mode, level):
        return cells[(n, r, 'exact' if level == 0 else mode, level)]
    out = report / 'supplement'
    out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'savefig.facecolor': 'white'})
    def save(fig, name):
        fig.savefig(out / (name + '.png'), dpi=160)
        fig.savefig(out / (name + '.pdf'))
        plt.close(fig)

    # Fixed relative tail separates dimension from growing absolute tail energy.
    for epsilon in (1., .1):
        fig, axes = plt.subplots(3, 3, figsize=(16, 12))
        for i, algorithm in enumerate(('CE', 'LSPI', 'NPG')):
            for j, alpha in enumerate((0., .05, .3)):
                ax = axes[i, j]
                for method, color in COLORS.items():
                    rows = [next(t for t in thresholds if t['algorithm'] == algorithm and
                            t['method'] == method and t['cell'] == cell(n, 4, 'relative', alpha) and
                            t['epsilon'] == epsilon) for n in (25, 50, 75, 100)]
                    x = np.array([25, 50, 75, 100]) + (-1 if method == 'raw' else 1)
                    ax.plot(x, [t['budget'] or np.nan for t in rows], color=color, label=method)
                    for xx, t in zip(x, rows):
                        value = t['budget'] or t['lower_budget']
                        marker = '^' if t['status'] == 'right_censored' else 'v' if t['status'] == 'left_censored' else 'o'
                        ax.scatter(xx, value, color=color, marker=marker)
                        label = ('>' if marker == '^' else '<=' if marker == 'v' else '') + f'{value:.2g}'
                        ax.annotate(label, (xx, value), xytext=(0, 9 if method == 'raw' else -17),
                                    textcoords='offset points', ha='center', fontsize=8, color=color)
                ax.set(xlabel='Dimension n', ylabel='Minimum tested transitions', yscale='log',
                       title=f'{algorithm}: r=4, relative tail={alpha:g}')
                ax.set_xticks([25, 50, 75, 100]); ax.grid(alpha=.2); ax.legend(fontsize=8)
        fig.suptitle(f'Fixed-rank dimension controls: cost gap <= {epsilon:g}', fontsize=16)
        fig.subplots_adjust(top=.93, bottom=.10, hspace=.42, wspace=.30)
        fig.text(.5, .025, 'Up triangles: target not attained; down triangles: attained at smallest tested budget.\n'
                 '2/2 systems and sustained at higher tested budgets. Relative tail = ||B-B_r||_F / ||B_r||_F.', ha='center')
        save(fig, f'fixed_rank_dimension_precision_{str(epsilon).replace(".", "p")}')

    fig, axes = plt.subplots(3, 3, figsize=(15, 11))
    for i, algorithm in enumerate(('CE', 'LSPI', 'NPG')):
        budget = max(float(p['samples']) for p in paired if p['algorithm'] == algorithm)
        for j, alpha in enumerate((0., .05, .3)):
            ax = axes[i, j]
            for method, color in COLORS.items():
                xx, yy = [], []
                for n in (25, 50, 75, 100):
                    p = next(p for p in paired if p['algorithm'] == algorithm and
                             p['cell'] == cell(n, 4, 'relative', alpha) and float(p['samples']) == budget)
                    if p[method + '_eligible'] == 'True':
                        xx.append(n); yy.append(max(1e-12, float(p[method + '_gap'])))
                    else:
                        ax.scatter(n, .97 if method == 'raw' else .91, color=color, marker='x',
                                   transform=ax.get_xaxis_transform())
                ax.plot(xx, yy, color=color, marker='o', label=method)
            ax.set(xlabel='Dimension n', ylabel='Mean cost gap', yscale='log',
                   title=f'{algorithm}: r=4, tail={alpha:g}, M={budget:.3g}')
            ax.set_xticks([25, 50, 75, 100]); ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.suptitle('Same-budget dimension controls at fixed relative tail', fontsize=16)
    fig.subplots_adjust(top=.92, bottom=.08, hspace=.43, wspace=.29)
    fig.text(.5, .025, 'M fixed across dimensions within each algorithm; x at panel top = at least one system failed.', ha='center')
    save(fig, 'fixed_rank_dimension_same_budget')

    # A population trajectory is a diagnostic of finite outer-iteration effects.
    tailcolors = {0.: '#555555', .01: '#1769aa', .1: '#b43b39'}
    for n in (50, 100):
        fig, axes = plt.subplots(2, 3, figsize=(16, 9))
        for ax, r in zip(axes.flat, (*RANKS, n)):
            for level in ((0.,) if r == n else (0., .01, .1)):
                selected_cell = cell(n, r, 'singular', level)
                for method, finite, linestyle in (('raw', False, '--'), ('truncated', False, '-'), ('truncated', True, ':')):
                    rows = [q for q in references['records'] if q['algorithm'] == 'NPG' and
                            q['cell'] == selected_cell and q['method'] == method and q['finite_horizon'] == finite]
                    by_stage = {}
                    for q in rows:
                        by_stage.setdefault(q['stage'], {})[q['seed']] = q
                    points = [(stage, max(1e-12, float(np.mean([q['gap'] for q in group.values()]))))
                              for stage, group in sorted(by_stage.items()) if len(group) == 2 and
                              all(q['stable'] and q['gap'] is not None for q in group.values())]
                    ax.plot([p[0] for p in points], [p[1] for p in points],
                            color=tailcolors[level], linestyle=linestyle, linewidth=1.5)
            ax.axvline(256, color='#999999', alpha=.6, linewidth=1)
            ax.set(xlabel='Outer updates (population critic)', ylabel='Mean cost gap', yscale='log',
                   title=f'n={n}, rank={r}')
            ax.set_xscale('symlog', linthresh=16); ax.grid(alpha=.2)
        handles = [Line2D([0], [0], color=c, label=f's={s:g}') for s, c in tailcolors.items()]
        handles += [Line2D([0], [0], color='black', linestyle=ls, label=label) for ls, label in
                    (('--', 'raw, infinite-H'), ('-', 'truncated, infinite-H'), (':', 'truncated, H=16'))]
        fig.legend(handles=handles, loc='lower center', ncol=3, bbox_to_anchor=(.5, .035))
        fig.suptitle('NPG: outer-iteration residual versus tail and finite-H bias', fontsize=16)
        fig.subplots_adjust(top=.91, bottom=.19, hspace=.4, wspace=.29)
        fig.text(.5, .005, 'Vertical line = 256 sampled updates. Population curves are diagnostics only; early endings do not prove a floor.\n'
                 'Values <=1e-12 displayed at 1e-12. No statistical samples used in population references.', ha='center', fontsize=9)
        save(fig, f'npg_population_convergence_n{n}')

    # Descriptive slopes use only interior, observed precision thresholds.
    slopes = []
    for algorithm in ('CE', 'LSPI', 'NPG'):
        for method in COLORS:
            for epsilon in (1., .1):
                base = [t for t in thresholds if t['algorithm'] == algorithm and t['method'] == method and
                        t['epsilon'] == epsilon and t['tail_mode'] == 'exact']
                groups = [('dimension', 4, [t for t in base if t['r'] == 4])] + [
                    ('rank', n, [t for t in base if t['n'] == n and t['r'] in RANKS]) for n in (50, 100)]
                for variable, fixed, group in groups:
                    good = [t for t in group if t['status'] == 'attained']
                    record = dict(algorithm=algorithm, method=method, epsilon=epsilon, variable=variable,
                                  fixed_rank_or_dimension=fixed, measured_cells=len(good), total_cells=len(group),
                                  excluded_censored_cells=[dict(n=t['n'], r=t['r'], status=t['status'])
                                                           for t in group if t['status'] != 'attained'])
                    if len(good) >= 3:
                        x = np.log([t['n'] if variable == 'dimension' else t['r'] for t in good])
                        y = np.log([t['budget'] for t in good])
                        coefficient = np.polyfit(x, y, 1)
                        record.update(descriptive_exponent=float(coefficient[0]),
                                      cells=[dict(n=t['n'], r=t['r'], budget=t['budget']) for t in good])
                    else:
                        record['status'] = 'insufficient_interior_thresholds'
                    slopes.append(record)
    atomic_json(out / 'measured_threshold_slopes.json', dict(slopes=slopes,
        interpretation='Descriptive fits of discrete measured sample thresholds, not a proof of rn^2. '
                       'Censored thresholds excluded explicitly; only two systems per cell.'))
    atomic_json(out / 'provenance.json', dict(status='complete', slurm_job_id=os.environ['SLURM_JOB_ID'],
        source_sha256=sha(__file__), inputs={name: sha(report / name) for name in
        ('summary.json', 'numerical_audit.json', 'same_budget.csv', 'endpoints.csv', 'population_references.json')},
        artifacts={p.name: sha(p) for p in out.iterdir() if p.name != 'provenance.json'}))
    print(json.dumps(dict(status='complete', supplement=str(out))))


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    main(parser.parse_args().output)
