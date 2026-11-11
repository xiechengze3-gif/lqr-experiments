"""Saved-data delivery plots. No simulation, fitting, or policy evaluation."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, output):
    source = root / 'joined-report/all_algorithms_summary.json'
    data = json.loads(source.read_text(encoding='utf-8-sig'))
    assert data['status'] == 'complete'
    rows = data['requirements']
    assert len(rows) == 60 and all(q['seeds'] == 30 for q in rows)
    assert all(q['initial_gap'] == 1 for q in rows)
    output.mkdir(parents=True, exist_ok=True)
    original_contrasts=root/'report-confirm/summary.json'
    raw_contrasts=json.loads(original_contrasts.read_text(encoding='utf-8-sig'))['contrasts']
    reviewed=[];invalid_finite_ci=0
    for original in raw_contrasts:
        q=dict(original);censored=q['full_dense_N'] is None or q['low_truncated_N'] is None
        bad=censored and any(q['paired_bootstrap95'].get(k) is not None for k in ('low','high'))
        invalid_finite_ci+=int(bad)
        q['ratio_status']='censored; no finite ratio CI estimated' if censored else 'finite grid ratio'
        q['corrected_finite_CI_for_censored_ratio']=bool(bad)
        if censored:
            assert q['full_over_low_ratio'] is None
            q['paired_bootstrap95']=dict(low=None,high=None,undefined=True,
                numerator_censored=q['full_dense_N'] is None,denominator_censored=q['low_truncated_N'] is None)
        reviewed.append(q)
    (output/'reviewed_low_truncated_vs_full_dense.json').write_text(json.dumps(dict(
        status='complete',contrasts=reviewed,original_source_sha256=digest(original_contrasts),
        invalid_finite_ratio_CI_entries_corrected=invalid_finite_ci,
        change='Censored N is not a literal infinite sample requirement. Finite ratio CIs for censored comparisons are suppressed; all N estimates, seed data and finite comparisons are unchanged.'),indent=2)+'\n',encoding='utf-8')
    with (output/'reviewed_low_truncated_vs_full_dense.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(reviewed[0]));writer.writeheader();writer.writerows(reviewed)
    ranks = [2, 8, 32, 64, 100]
    colors = {'dense': '#b94835', 'truncated': '#176da0'}
    plt.rcParams.update({'font.size': 10, 'axes.grid': True, 'grid.alpha': .16})
    fig, axes = plt.subplots(3, 2, figsize=(12.4, 11), layout='constrained')
    comparisons = []
    for line, algorithm in zip(axes, ('CE', 'NPG', 'PI')):
        for ax, target in zip(line, (.1, .05)):
            for method, offset in (('dense', -.09), ('truncated', .09)):
                selected = [next(q for q in rows if q['algorithm'] == algorithm
                    and q['method'] == method and q['rank'] == rank
                    and q['relative_target'] == target) for rank in ranks]
                xx = np.arange(5) + offset
                yy = [q['N_hat_90'] if q['N_hat_90'] is not None else np.nan for q in selected]
                ax.plot(xx, yy, '-o', color=colors[method], ms=5, lw=1.4)
                for x, q in zip(xx, selected):
                    if q['N_hat_90'] is None:
                        ax.plot(x, q['max_budget'], '^', mfc='white', mec=colors[method], ms=7)
                    elif q['bootstrap95_low'] is not None:
                        top = q['bootstrap95_high']
                        ax.vlines(x, q['bootstrap95_low'], top if top is not None else q['max_budget'],
                            color=colors[method], lw=1.6)
                        if top is None:
                            ax.annotate('', xy=(x, q['max_budget']*1.12), xytext=(x, q['max_budget']),
                                arrowprops={'arrowstyle': '->', 'color': colors[method]})
            full = next(q for q in rows if q['algorithm'] == algorithm and q['method'] == 'dense'
                and q['rank'] == 100 and q['relative_target'] == target)
            low = next(q for q in rows if q['algorithm'] == algorithm and q['method'] == 'truncated'
                and q['rank'] == 2 and q['relative_target'] == target)
            a, b = full['N_hat_90'], low['N_hat_90']
            comparison = dict(algorithm=algorithm, relative_target=target,
                rank2_truncated_N=b, full_dense_N=a, full_max_budget=full['max_budget'],
                finite_grid_ratio=a/b if a is not None and b is not None else None,
                full_max_success_rate=full['max_success_rate'],
                low_max_success_rate=low['max_success_rate'])
            comparisons.append(comparison)
            if a is not None:
                ax.axhline(a, color='.45', ls=':', lw=1)
            finite = [q['N_hat_90'] for q in rows if q['algorithm'] == algorithm
                and q['relative_target'] == target and q['N_hat_90'] is not None]
            panel = [q for q in rows if q['algorithm'] == algorithm and q['relative_target'] == target]
            tops = [q['N_hat_90'] if q['N_hat_90'] is not None else q['max_budget'] for q in panel]
            tops += [q['bootstrap95_high'] if q['bootstrap95_high'] is not None else q['max_budget']
                for q in panel if q['N_hat_90'] is not None and q['bootstrap95_low'] is not None]
            ax.set(yscale='log', xticks=range(5), xticklabels=[str(r) for r in ranks],
                xlabel='Actuation rank', ylabel='Cumulative primitive transitions',
                title=f'{algorithm} | target {target:g}',
                ylim=(min(finite)*.65 if finite else full['max_budget']*.35, max(tops)*1.45))
            ax.legend(handles=[Line2D([], [], color=colors[m], marker='o', label=m) for m in colors]
                + [Line2D([], [], color='.4', marker='^', mfc='white', ls='none', label='not reached')],
                fontsize=8, loc='lower right')
    fig.suptitle('Initial optimality gap = 1 | absolute target = relative target | 30 formal seeds\n'
        'First tested budget with >=90% empirical success; bootstrap 95% intervals\n'
        'Open triangles retain censored runs; rank positions offset only for readability', fontsize=11)
    output.mkdir(parents=True, exist_ok=True)
    for ext in ('png', 'svg'):
        fig.savefig(output / ('all_algorithms_sample_complexity_review.'+ext), dpi=180, facecolor='white')
    plt.close(fig)
    provenance = dict(status='complete', source=str(source), source_sha256=digest(source),
        plot_source_sha256=digest(Path(__file__)), new_primitive_transitions=0,
        model_evaluations=0, comparisons=comparisons,
        invalid_finite_ratio_CI_entries_corrected=invalid_finite_ci,
        changes='Categorical rank positions and method offsets, panel limits. N estimates and their intervals unchanged. Suppress invalid finite ratio CIs when a comparator is censored; original report retained.',
        environment=dict(python=sys.executable, version=platform.python_version(),
            numpy=np.__version__, matplotlib=matplotlib.__version__,
            storage={k:os.environ.get(k) for k in ('TEMP','TMP','XDG_CACHE_HOME','MPLCONFIGDIR')}))
    (output/'FINAL_REVIEW_PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(comparisons))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.root,args.output)
