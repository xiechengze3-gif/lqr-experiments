"""Paired fixed-budget gap analysis of completed experiments; no learning."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = Path(r'E:\ChatGPT\Results\LQR_experiments\rank-sweep100-confirm-20261016')
PI = Path(r'E:\ChatGPT\Results\LQR_experiments\rank-sweep100-pi-v2-20261017')
RANKS = (2, 8, 32, 64, 100)
SEEDS = tuple(range(100, 130))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def csv_write(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def interval(values):
    return np.quantile(values, [.025, .975]).tolist()


def wilson(count, total):
    z = 1.959963984540054; p = count/total; den = 1+z*z/total
    mid = (p+z*z/(2*total))/den
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return max(0., mid-half), min(1., mid+half)


def savefig(fig, output, name):
    fig.savefig(output/(name+'.png'), dpi=180, facecolor='white')
    fig.savefig(output/(name+'.svg'), facecolor='white')
    plt.close(fig)


def plot(summary, output, epsilon):
    plt.rcParams.update({'font.size': 10, 'axes.grid': True, 'grid.alpha': .22})
    colors = plt.get_cmap('tab10').colors
    dense, trunc = '#c24b37', '#1675a4'
    fig, axes = plt.subplots(1, 5, figsize=(17, 3.8), sharey=True, layout='constrained')
    for ax, rank in zip(axes, RANKS):
        rows = [q for q in summary if q['route']=='ce' and q['rank']==rank]
        budgets = [q['transitions'] for q in rows]
        for method, color, style in [('dense',dense,'--'), ('truncated',trunc,'-')]:
            ax.plot(budgets, [q[method+'_gap_median'] for q in rows], style, color=color, label=method.capitalize())
            ax.fill_between(budgets, [q[method+'_gap_q25'] for q in rows], [q[method+'_gap_q75'] for q in rows], color=color, alpha=.15)
        ax.axhline(epsilon, color='.4', lw=1, ls=':', label='Original target')
        ax.set(xscale='log', yscale='log', title=f'rank {rank}', xlabel='Transitions, including burn-in')
    axes[0].set_ylabel('Absolute optimality gap')
    axes[-1].legend(loc='upper right', fontsize=8)
    fig.suptitle('CE: same-budget dense / truncated gap | 30 paired seeds | medians and IQR', fontsize=13)
    savefig(fig, output, 'ce_fixed_budget_absolute_gap')

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.1), layout='constrained')
    for i, rank in enumerate(RANKS):
        rows = [q for q in summary if q['route']=='ce' and q['rank']==rank]
        x = [q['transitions'] for q in rows]
        axes[0].plot(x, [q['gap_ratio_of_medians'] for q in rows], '-o', markersize=3, color=colors[i], label=f'rank {rank}')
        axes[0].fill_between(x, [q['gap_ratio_of_medians_ci95_low'] for q in rows], [q['gap_ratio_of_medians_ci95_high'] for q in rows], color=colors[i], alpha=.12)
    for i, budget in enumerate((4352, 16640, 65792)):
        rows = sorted([q for q in summary if q['route']=='ce' and q['transitions']==budget], key=lambda q:q['rank'])
        assert len(rows)==5
        axes[1].errorbar(RANKS, [q['gap_ratio_of_medians'] for q in rows],
            yerr=np.array([[q['gap_ratio_of_medians']-q['gap_ratio_of_medians_ci95_low'] for q in rows],
                           [q['gap_ratio_of_medians_ci95_high']-q['gap_ratio_of_medians'] for q in rows]]),
            fmt='-o', color=colors[i], capsize=3, label=f'{budget:,} transitions')
    for ax in axes:
        ax.axhline(1., color='.4', ls=':', lw=1)
        ax.set(yscale='log', ylabel='Dense median gap / truncated median gap')
        ax.set_yticks([1,2,5,10,20], labels=['1','2','5','10','20'])
        ax.legend(fontsize=8)
    axes[0].set(xscale='log', xlabel='Transitions, including burn-in', title='All 11 measured budgets')
    axes[1].set(xlabel='Actuation rank', title='Three displayed common budgets', xticks=RANKS)
    fig.suptitle('CE fixed-budget gap improvement | 95% paired-seed bootstrap intervals', fontsize=13)
    savefig(fig, output, 'ce_fixed_budget_gap_improvement')

    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.1), sharey=True, layout='constrained')
    for ax, route, label in zip(axes, ('npg','ce','pi'), ('Stein NPG','CE','Full LSTD PI')):
        allrows = [q for q in summary if q['route']==route]
        budget = max(q['transitions'] for q in allrows)
        rows = sorted([q for q in allrows if q['transitions']==budget], key=lambda q:q['rank'])
        ax.errorbar(RANKS, [q['gap_ratio_of_medians'] for q in rows],
            yerr=np.array([[q['gap_ratio_of_medians']-q['gap_ratio_of_medians_ci95_low'] for q in rows],
                           [q['gap_ratio_of_medians_ci95_high']-q['gap_ratio_of_medians'] for q in rows]]),
            fmt='-o', color=trunc, capsize=4)
        ax.axhline(1., color='.4', ls=':', lw=1)
        ax.set(yscale='log', xlabel='Actuation rank', xticks=RANKS, title=f'{label}\nBudget {budget:,}')
        for q in rows:
            ax.annotate(f"{q['gap_ratio_of_medians']:.2f}x", (q['rank'],q['gap_ratio_of_medians']), xytext=(0,9), textcoords='offset points', ha='center', fontsize=8)
    axes[0].set_ylabel('Dense median gap / truncated median gap')
    axes[0].set_yticks([1,2,5,10,20,50,100], labels=['1','2','5','10','20','50','100'])
    axes[0].set_ylim(.8, 150)
    fig.suptitle('Fixed-budget endpoint gain | 30 paired seeds, 95% bootstrap CI\nBudgets differ across algorithms; dense/truncated share each stated budget', fontsize=12)
    savefig(fig, output, 'all_algorithms_fixed_budget_endpoint_gain')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); out = args.output.resolve()
    assert str(out).lower().startswith('e:\\chatgpt\\results\\lqr_experiments\\')
    out.mkdir(parents=True, exist_ok=True)
    hashes = {}; raw = []
    rng = np.random.default_rng(20261018)
    boot = rng.integers(0, len(SEEDS), size=(5000,len(SEEDS)))
    summary = []; pairs = []; rank100_checks = 0
    config = json.loads((BASE/'resolved_config.json').read_text(encoding='utf-8'))
    for source in (Path(__file__), BASE/'resolved_config.json', PI/'resolved_config.json'):
        hashes[str(source)] = sha(source)
    for route in ('npg','ce','pi'):
        origin = PI if route=='pi' else BASE
        for rank in RANKS:
            data = {}
            for seed in SEEDS:
                path = origin/f'raw/{route}-r{rank:03d}-s{seed:04d}.json'
                hashes[str(path)] = sha(path)
                d = json.loads(path.read_text(encoding='utf-8'))
                assert d['rank']==rank and d['seed']==seed and d['route']==route
                data[seed] = {(q['method'],q['transitions']):q for q in d['records']}
            grid = sorted({n for (method,n) in data[SEEDS[0]] if n>0})
            for budget in grid:
                rows = {m:[data[s][m,budget] for s in SEEDS] for m in ('dense','truncated')}
                # Every formal policy in these completed campaigns was stable.
                # Check this explicitly; never silently remove a failed seed.
                assert all(q['observed'] and q['stable'] and q.get('whole_path_stable',True) and q['gap'] is not None and not q.get('failure') for rr in rows.values() for q in rr)
                d, t = [np.array([q['gap'] for q in rows[m]],dtype=float) for m in ('dense','truncated')]
                assert np.isfinite(d).all() and np.isfinite(t).all() and (d>0).all() and (t>0).all()
                if rank==100:
                    np.testing.assert_array_equal(d,t); rank100_checks += len(SEEDS)
                md, mt = float(np.median(d)), float(np.median(t))
                br = np.median(d[boot],axis=1)/np.median(t[boot],axis=1)
                bp = np.median((d/t)[boot],axis=1)
                bd = np.median((d-t)[boot],axis=1)
                ratio_ci, paired_ci, difference_ci = interval(br), interval(bp), interval(bd)
                wins, ties = int(np.sum(t<d)), int(np.sum(t==d))
                win_ci = wilson(wins,len(SEEDS))
                row = dict(route=route, rank=rank, transitions=budget, seeds=len(SEEDS),
                    dense_gap_median=md, truncated_gap_median=mt,
                    dense_gap_q25=float(np.quantile(d,.25)), dense_gap_q75=float(np.quantile(d,.75)),
                    truncated_gap_q25=float(np.quantile(t,.25)), truncated_gap_q75=float(np.quantile(t,.75)),
                    gap_ratio_of_medians=md/mt,
                    gap_ratio_of_medians_ci95_low=ratio_ci[0], gap_ratio_of_medians_ci95_high=ratio_ci[1],
                    median_paired_gap_ratio=float(np.median(d/t)),
                    median_paired_gap_ratio_ci95_low=paired_ci[0], median_paired_gap_ratio_ci95_high=paired_ci[1],
                    gap_reduction_fraction_from_medians=1-mt/md,
                    median_paired_gap_difference=float(np.median(d-t)),
                    median_paired_gap_difference_ci95_low=difference_ci[0], median_paired_gap_difference_ci95_high=difference_ci[1],
                    dense_gap_27th_order_statistic=float(np.sort(d)[26]),
                    truncated_gap_27th_order_statistic=float(np.sort(t)[26]),
                    truncated_strict_wins=wins, ties=ties, dense_strict_wins=len(SEEDS)-wins-ties,
                    win_probability=wins/len(SEEDS), win_probability_ci95_low=win_ci[0], win_probability_ci95_high=win_ci[1],
                    dense_instabilities=0, truncated_instabilities=0, numerical_failures=0)
                summary.append(row)
                for i, seed in enumerate(SEEDS):
                    pairs.append(dict(route=route,rank=rank,seed=seed,transitions=budget,
                                      dense_gap=float(d[i]),truncated_gap=float(t[i]),gap_ratio=float(d[i]/t[i]),
                                      gap_difference=float(d[i]-t[i])))
    assert len(hashes)==453 and len(summary)==295 and len(pairs)==8850
    for path, digest in hashes.items():assert sha(path)==digest
    csv_write(out/'all_fixed_budget_statistics.csv',summary)
    csv_write(out/'per_seed_fixed_budget_pairs.csv',pairs)
    endpoint = [q for q in summary if q['transitions']==max(z['transitions'] for z in summary if z['route']==q['route'])]
    csv_write(out/'endpoint_statistics.csv',endpoint)
    plot(summary,out,config['epsilon'])
    write(out/'config.json',dict(formal_seeds=SEEDS,ranks=RANKS,bootstrap_replicates=5000,bootstrap_seed=20261018,
        bootstrap_unit='Paired sampling seed, same resample indices across ranks, budgets, algorithms',
        original_absolute_target=config['epsilon'],new_learning_transitions=0,
        statistic='Ratio of medians; median of per-seed ratios also reported separately',
        definition_90pct_gap='27th smallest of all 30 gaps, matching empirical >=27/30 success; not an interpolated quantile',
        comparison='Same rank, same algorithm, same primitive-transition budget; budgets differ between algorithms',
        original_sample_complexity_results_unchanged=True))
    write(out/'source_sha256.json',hashes)
    (out/'README.txt').write_text(
        'Fixed-budget gap supplement, computed only from the 30 fresh formal seeds.\n'
        'Gap is the true infinite-horizon absolute J(K)-Jstar already independently audited.\n'
        'Read all_fixed_budget_statistics.csv for ALL measured positive budgets, not selected best points.\n'
        'Ratios >1 favor truncation. Ratio of medians differs from median of paired ratios; both are included.\n'
        'Bootstrap intervals are paired, pointwise 95%, conditional on the one fixed system.\n'
        'IQR bands describe seed dispersion, not confidence intervals.\n'
        'The 27th order statistic gives the gap at which 27/30 outputs qualify.\n'
        'All paired seeds were retained and checked stable. Rank100 exact equality was checked.\n'
        'NPG/PI prefixes include more updates at larger budgets. Do not compare algorithm endpoints as equal-budget across algorithms.\n'
        'Fixed-gap sample complexity and fixed-budget gap improvement are complementary. No earlier results were overwritten.\n'
        'No new learning, simulator transitions, fitting, or model oracle intervention was performed.\n',encoding='utf-8')
    artifacts = {p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name not in ('completion.json','visual_review.json')}
    write(out/'completion.json',dict(status='statistics_complete_pending_visual_review',
        completed_utc=datetime.now(timezone.utc).isoformat(),source_files=450,
        budget_rank_method_pair_summaries=len(summary),paired_seed_budget_observations=len(pairs),
        rank100_gap_equality_checks=rank100_checks,all_formal_observations_stable=True,
        new_primitive_transitions=0,artifacts_sha256=artifacts))
    print(json.dumps(dict(output=str(out),rows=len(summary),pairs=len(pairs),endpoints=endpoint),ensure_ascii=False))


if __name__=='__main__':main()
