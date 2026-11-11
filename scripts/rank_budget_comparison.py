"""Direct paired budget/precision comparisons, computed only on Grace Slurm."""
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
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from dense_scaling import require_compute, atomic_json


COLORS = {'raw': '#b43b39', 'truncated': '#1769aa'}
RANKS = (1, 2, 4, 8, 16)
ALGORITHMS = ('CE', 'PI-LSTD', 'NPG')
NAMES = {'CE': 'CE', 'PI-LSTD': 'LSPI', 'NPG': 'NPG'}


def short(value):
    if value >= 1e9:
        return f'{value/1e9:.3g}B'
    if value >= 1e6:
        return f'{value/1e6:.3g}M'
    if value >= 1e3:
        return f'{value/1e3:.3g}k'
    return str(int(value))


def dump_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(root):
    root = Path(root)
    report, out = root/'report', root/'direct-comparison-v3'
    out.mkdir(exist_ok=True)
    summary = json.loads((report/'summary.json').read_text())
    endpoints = list(csv.DictReader((report/'endpoints.csv').open()))
    endpoints = [e for e in endpoints if float(e['tail']) == 0 and
                 int(e['n']) in (50, 100) and int(e['r']) in RANKS]
    index = {}
    for e in endpoints:
        key = (e['algorithm'], int(e['n']), int(e['r']), int(e['planned_transitions']))
        index.setdefault(key, {}).setdefault(e['method'], []).append(e)
    paired = []
    for (algorithm, n, rank, budget), group in sorted(index.items()):
        assert set(group) == set(COLORS)
        assert all(len(rows) == 2 and {int(e['seed']) for e in rows} == {0, 1}
                   for rows in group.values())
        row = dict(algorithm=algorithm, n=n, r=rank, total_samples=budget)
        for method, records in group.items():
            good = all(e['eligible'] == 'True' for e in records)
            values = [float(e['gap']) for e in records] if good else []
            row[f'{method}_eligible'] = good
            row[f'{method}_mean_gap'] = float(np.mean(values)) if good else None
            row[f'{method}_min_gap'] = min(values) if good else None
            row[f'{method}_max_gap'] = max(values) if good else None
            for seed in (0, 1):
                e = next(e for e in records if int(e['seed']) == seed)
                row[f'{method}_seed{seed}_gap'] = float(e['gap']) if e['gap'] else None
                row[f'{method}_seed{seed}_eligible'] = e['eligible'] == 'True'
        row['error_gain'] = (row['raw_mean_gap']/row['truncated_mean_gap']
                             if row['raw_eligible'] and row['truncated_eligible'] and
                             row['truncated_mean_gap'] > 0 else None)
        row['status'] = ('measured' if row['error_gain'] is not None else
                         'raw failed' if not row['raw_eligible'] and row['truncated_eligible'] else
                         'trunc failed' if row['raw_eligible'] else 'both failed')
        paired.append(row)
    lookup = {(p['algorithm'], p['n'], p['r'], p['total_samples']): p for p in paired}
    budgetsets = {a: sorted({p['total_samples'] for p in paired if p['algorithm'] == a})
                  for a in ALGORITHMS}
    # Chosen display budgets are declared here; complete grid shown separately.
    display = {'CE': 32768+512, 'PI-LSTD': 6*(524288+1024),
               'NPG': 80*(1024+(1048576+1)*16)}
    precision_rows = []
    thresholds = summary['thresholds']
    for algorithm in ALGORITHMS:
        for n in (50, 100):
            for rank in RANKS:
                for epsilon in (5., 2., 1., .5, .1):
                    matches = {m: next(t for t in thresholds if t['algorithm'] == algorithm
                        and t['n'] == n and t['r'] == rank and t['tail'] == 0
                        and t['epsilon'] == epsilon and t['method'] == m) for m in COLORS}
                    raw, tr = matches['raw'], matches['truncated']
                    # Independently reproduce each sustained fixed-output threshold.
                    for method, threshold in matches.items():
                        budgets = budgetsets[algorithm]
                        success = []
                        for budget in budgets:
                            entries = index[(algorithm, n, rank, budget)][method]
                            success.append(all(e['eligible'] == 'True' and
                                               float(e['gap']) <= epsilon for e in entries))
                        at = next((i for i in range(len(budgets)) if all(success[i:])), None)
                        assert threshold['budget'] == (None if at is None else budgets[at])
                        assert threshold['success_by_budget'] == success
                    gain = (raw['budget']/tr['budget']
                            if raw['budget'] is not None and tr['budget'] is not None else None)
                    lower_gain = (raw['lower_budget']/tr['budget']
                                  if raw['budget'] is None and tr['budget'] is not None else None)
                    precision_rows.append(dict(algorithm=algorithm, n=n, r=rank, epsilon=epsilon,
                        raw_samples=raw['budget'], raw_status=raw['status'],
                        raw_lower_budget=raw['lower_budget'],
                        truncated_samples=tr['budget'], truncated_status=tr['status'],
                        truncated_lower_budget=tr['lower_budget'],
                        tested_grid_saving=gain, tested_range_saving_lower_bound=lower_gain,
                        ratio_note='Ratio of minimum successful TESTED budgets, not an exact continuous-budget ratio'))

    plt.rcParams.update({'font.size': 11, 'axes.titlesize': 13, 'axes.labelsize': 11,
                         'savefig.facecolor': 'white'})

    def save(fig, name):
        fig.savefig(out/f'{name}.png', dpi=180, bbox_inches='tight')
        fig.savefig(out/f'{name}.pdf', bbox_inches='tight')
        plt.close(fig)

    def fixed_cost(ax, algorithm, n):
        budget = display[algorithm]
        rows = [lookup[(algorithm, n, rank, budget)] for rank in RANKS]
        for method, color in COLORS.items():
            assert all(p[f'{method}_eligible'] for p in rows)
            mean = np.array([p[f'{method}_mean_gap'] for p in rows])
            ax.plot(range(5), mean, color=color, marker='o', linewidth=2,
                    label='No truncation' if method == 'raw' else 'Rank-r truncation')
            ax.fill_between(range(5), [p[f'{method}_min_gap'] for p in rows],
                            [p[f'{method}_max_gap'] for p in rows], color=color, alpha=.13)
        for position, p in enumerate(rows):
            lo, hi = p['truncated_mean_gap'], p['raw_mean_gap']
            ax.plot([position, position], [lo, hi], color='#6d747c', linewidth=.8, alpha=.7)
            ax.annotate(f"{p['error_gain']:.1f}x", (position, np.sqrt(lo*hi)),
                        xytext=(5, 0), textcoords='offset points', va='center', fontsize=10,
                        bbox=dict(facecolor='white', edgecolor='none', alpha=.9, pad=1))
        ax.set(yscale='log', xlabel='Rank r', ylabel='Cost gap J(K) - J*',
               title=f'{NAMES[algorithm]}, n={n} | M={budget:,} samples')
        ax.set_xticks(range(5), labels=RANKS)
        ax.set_xlim(-.3, 4.5)
        ax.grid(axis='y', alpha=.2)
        ax.legend(fontsize=9, loc='best')

    fig, axes = plt.subplots(2, 2, figsize=(12, 8.3))
    for i, algorithm in enumerate(('CE', 'PI-LSTD')):
        for j, n in enumerate((50, 100)):
            fixed_cost(axes[i, j], algorithm, n)
    fig.suptitle('Same sample budget: how much does truncation reduce cost gap?', fontsize=16)
    fig.subplots_adjust(top=.89, bottom=.13, hspace=.43, wspace=.26)
    fig.text(.5, .035,
             'Numbers = mean raw gap / mean truncated gap; larger is better. Shading = range of 2 systems.\n'
             'Exact-rank B. Both methods use the same M within each panel; CE and LSPI have different M.',
             ha='center', fontsize=10)
    save(fig, 'ce_lspi_same_budget_by_rank')
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, n in zip(axes, (50, 100)):
        fixed_cost(ax, 'NPG', n)
    fig.suptitle('NPG: same sample budget, truncation versus no truncation', fontsize=15)
    fig.subplots_adjust(top=.83, bottom=.18, wspace=.26)
    fig.text(.5, .025, 'Numbers = error reduction factor; fixed 80 updates. Exact-rank B, 2 systems.',
             ha='center', fontsize=10)
    save(fig, 'npg_same_budget_by_rank')

    for algorithm in ALGORITHMS:
        budgets = budgetsets[algorithm]
        fig, axes = plt.subplots(1, 2, figsize=(11.5, max(4.4, 1.9+.53*len(budgets))))
        for ax, n in zip(axes, (50, 100)):
            data = np.full((len(budgets), 5), np.nan)
            for i, budget in enumerate(budgets):
                for j, rank in enumerate(RANKS):
                    p = lookup[(algorithm, n, rank, budget)]
                    if p['error_gain'] is not None:
                        data[i, j] = np.log2(p['error_gain'])
            cmap = plt.get_cmap('RdBu').copy()
            cmap.set_bad('#e9e9e9')
            ax.imshow(data, cmap=cmap, norm=TwoSlopeNorm(vmin=-3, vcenter=0, vmax=8), aspect='auto')
            for i, budget in enumerate(budgets):
                for j, rank in enumerate(RANKS):
                    p = lookup[(algorithm, n, rank, budget)]
                    text = (f"{p['error_gain']:.2f}x" if p['error_gain'] < 2 else f"{p['error_gain']:.1f}x") if p['error_gain'] is not None else p['status'].replace(' ', '\n')
                    color = 'white' if np.isfinite(data[i, j]) and (data[i, j] > 4.5 or data[i, j] < -1.8) else '#222'
                    ax.text(j, i, text, ha='center', va='center', color=color, fontsize=11)
            ax.set_xticks(range(5), labels=RANKS)
            ax.set_yticks(range(len(budgets)), labels=[f'{b:,}' for b in budgets])
            ax.set(xlabel='Rank r', ylabel='Total samples M', title=f'{NAMES[algorithm]}, n={n}')
        fig.suptitle('Same-budget error reduction: raw gap / truncated gap', fontsize=15)
        fig.subplots_adjust(top=.82, bottom=.26, wspace=.37, left=.14, right=.97)
        fig.text(.5, .025,
                 'Blue: truncation helps (>1x). Red: truncation hurts (<1x). Gray: at least one output fails.\n'
                 'Ratios use means over both systems; no failed output is assigned a finite cost.',
                 ha='center', fontsize=10)
        save(fig, f'{NAMES[algorithm].lower()}_same_budget_gain_grid')

    for algorithm in ALGORITHMS:
        epsilons = (5., 1.) if algorithm == 'NPG' else (1., .1)
        fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.1))
        for row, epsilon in enumerate(epsilons):
            visible = [p[f'{m}_samples'] or p[f'{m}_lower_budget']
                       for p in precision_rows if p['algorithm'] == algorithm and p['epsilon'] == epsilon
                       for m in COLORS]
            ylim = (min(visible)*.45, max(visible)*2.5)
            for col, n in enumerate((50, 100)):
                ax = axes[row, col]
                budgetmax, budgetmin = max(budgetsets[algorithm]), min(budgetsets[algorithm])
                for method, color in COLORS.items():
                    rows = [next(p for p in precision_rows if p['algorithm'] == algorithm and
                                 p['n'] == n and p['r'] == rank and p['epsilon'] == epsilon)
                            for rank in RANKS]
                    attained = [p for p in rows if p[f'{method}_samples'] is not None]
                    # Never connect a missing threshold to a measured threshold.
                    values = [p[f'{method}_samples'] or np.nan for p in rows]
                    shift = -.045 if method == 'raw' else .045
                    ax.plot(np.arange(5)+shift, values, color=color, linewidth=1.8,
                            label='No truncation' if method == 'raw' else 'Rank-r truncation')
                    for j, p in enumerate(rows):
                        status = p[f'{method}_status']
                        value = p[f'{method}_samples']
                        y = budgetmax if value is None else value
                        marker = '^' if value is None else 'v' if status == 'left_censored' else 'o'
                        ax.scatter(j+shift, y, color=color, marker=marker, s=55, zorder=3)
                        prefix = '>' if value is None else '<=' if status == 'left_censored' else ''
                        label = prefix+short(y)
                        ax.annotate(label, (j+shift, y), xytext=(0, 11 if method == 'raw' else -19),
                                    textcoords='offset points', ha='center', color=color, fontsize=9)
                ax.set(yscale='log', xlabel='Rank r', ylabel='Samples M to reach precision',
                       title=f'{NAMES[algorithm]}, n={n} | cost gap <= {epsilon:g}')
                ax.set_xticks(range(5), labels=RANKS)
                ax.set_xlim(-.35, 4.35)
                ax.set_ylim(*ylim)
                ax.grid(axis='y', alpha=.2)
                ax.legend(fontsize=9, loc='best')
        fig.suptitle('Same precision: how many samples does each method need?', fontsize=16)
        fig.subplots_adjust(top=.89, bottom=.14, hspace=.45, wspace=.3)
        fig.text(.5, .035,
                 'Minimum TESTED budget where both systems succeed and remain successful at all higher tested budgets.\n'
                 'Up triangle (>M): target not reached. Down triangle (<=M): already reached at smallest budget.\n'
                 'k=1,000; M=1,000,000; B=1,000,000,000. Budget grid is approximately 4x; LSPI has only 3 levels.',
                 ha='center', fontsize=10)
        save(fig, f'{NAMES[algorithm].lower()}_samples_to_precision_by_rank')

    # Numeric table in addition to plots: exact counts and explicit sample savings.
    for algorithm in ALGORITHMS:
        epsilons = (5., 1.) if algorithm == 'NPG' else (1., .1)
        fig, axes = plt.subplots(1, 2, figsize=(13, 6.2))
        for ax, epsilon in zip(axes, epsilons):
            data = []
            for n in (50, 100):
                for rank in RANKS:
                    p = next(p for p in precision_rows if p['algorithm'] == algorithm and
                             p['n'] == n and p['r'] == rank and p['epsilon'] == epsilon)
                    labels = []
                    for method in COLORS:
                        status, value = p[f'{method}_status'], p[f'{method}_samples']
                        labels.append(('>' if value is None else '<=' if status == 'left_censored' else '')+
                                      f"{(p[f'{method}_lower_budget'] if value is None else value):,}")
                    if p['tested_grid_saving'] is not None:
                        ratio = f"{p['tested_grid_saving']:.2f}x"
                        if p['raw_status'] == 'left_censored' or p['truncated_status'] == 'left_censored':
                            ratio += ' (grid)'
                    elif p['tested_range_saving_lower_bound'] is not None:
                        ratio = f">{p['tested_range_saving_lower_bound']:.2f}x*"
                    else:
                        ratio = 'unresolved'
                    data.append([str(n), str(rank), *labels, ratio])
            ax.axis('off')
            table = ax.table(cellText=data, colLabels=['n', 'r', 'Raw samples', 'Trunc. samples', 'Grid saving'],
                             loc='center', cellLoc='center', colWidths=[.07, .07, .28, .28, .23])
            table.auto_set_font_size(False)
            table.set_fontsize(9.5)
            table.scale(1, 2.0)
            for (row, col), cell in table.get_celld().items():
                cell.set_edgecolor('#dddddd')
                if row == 0:
                    cell.set_facecolor('#edf0f3')
                    cell.set_text_props(weight='bold')
                elif row > 5:
                    cell.set_facecolor('#f8f9fb')
                if row > 0 and col in (2, 3):
                    cell.set_text_props(color=COLORS['raw' if col == 2 else 'truncated'])
            ax.set_title(f'Cost gap <= {epsilon:g}', fontsize=14, pad=20)
        fig.suptitle(f'{NAMES[algorithm]}: samples required at each rank (exact counts)', fontsize=16)
        fig.subplots_adjust(top=.82, bottom=.19, wspace=.13)
        fig.text(.5, .04,
                 'Saving = raw / truncation minimum successful tested budgets. It is a coarse-grid empirical ratio.\n'
                 '* Raw never reached the target in the tested range; only a tested-range lower bound is available.\n'
                 'All counts include burn-in. Two systems per cell; no population success guarantee.',
                 ha='center', fontsize=10)
        save(fig, f'{NAMES[algorithm].lower()}_samples_to_precision_table')

    dump_csv(out/'same_budget_comparison.csv', paired)
    dump_csv(out/'samples_to_precision.csv', precision_rows)
    atomic_json(out/'comparison.json', dict(same_budget=paired, samples_to_precision=precision_rows,
        displayed_same_budgets=display, epsilons=[5., 2., 1., .5, .1],
        counts=dict(paired_budget_groups=len(paired), precision_comparisons=len(precision_rows)),
        note='Exact rank only. All three algorithms retained. Small-tail experiments are in the original report. '
             'Error ratios and tested-budget ratios are separate quantities; no inference that one equals the other. '
             'No additional simulations and no interpolation or extrapolation of unattained thresholds.'))
    atomic_json(out/'provenance.json', dict(slurm_job_id=os.environ['SLURM_JOB_ID'],
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (report/'summary.json', report/'endpoints.csv')},
        artifacts={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in out.iterdir() if p.name != 'provenance.json'},
        numerical_audit='All plotted precision thresholds independently recomputed from endpoint eligibility and gaps; '
                        'all budgets have both raw/truncated and both seeds; failed endpoints retained.'))
    print(json.dumps(dict(artifact_dir=str(out), paired_groups=len(paired),
                         precision_comparisons=len(precision_rows))))


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    main(parser.parse_args().output)
