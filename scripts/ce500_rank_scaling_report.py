"""Full rank-4 policy audit and paired descriptive scaling analysis."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):
    sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from threadpoolctl import threadpool_limits
import rank_sweep100 as e
import ce500_matched_gap as run
import ce500_rank4_extension as extension
from ce_matched_initial_gap import performance_gap


def csv_save(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        w.writeheader(); w.writerows(rows)


def wilson(k, n):
    z = 1.959963984540054; p = k / n; den = 1 + z*z/n
    mid = (p + z*z/(2*n)) / den
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return max(0., mid-half), min(1., mid+half)


def threshold(success, budgets):
    hits = success.mean(axis=-2) >= .9 - 1e-12
    return np.where(hits.any(axis=-1), np.asarray(budgets)[hits.argmax(axis=-1)], np.inf)


def finite(x):
    return float(x) if np.isfinite(x) else None


def report(cfg, phase):
    began = time.monotonic(); out = Path(cfg['output']); dest = out / ('report-' + phase)
    dest.mkdir(parents=True, exist_ok=True)
    ident = extension.identity(cfg); seeds = cfg[phase + '_seeds']
    budgets = [b + cfg['burn'] for b in cfg[phase + '_budgets']]
    s = run.load_system(cfg, 4); checked = 0; max_error = 0.; hashes = {}; data = {}; rows_all = []
    for seed in seeds:
        stem = f'ce-r004-s{seed:04d}'; path = out / 'raw' / (stem + '.json'); raw = e.read(path)
        assert raw['identity'] == ident and raw['physical_transitions'] == max(budgets)
        assert raw['budgets'] == cfg[phase + '_budgets'] and len(raw['records']) == 2*len(budgets)
        hashes[str(path.relative_to(out))] = e.sha(path)
        for budget in budgets:
            pair = [q for q in raw['records'] if q['transitions'] == budget]
            assert [q['method'] for q in pair] == ['dense', 'truncated']
            pp = out / pair[0]['policy_file']; sha = e.sha(pp)
            assert sha == pair[0]['policy_sha256'] == pair[1]['policy_sha256']
            hashes[str(pp.relative_to(out))] = sha
            with np.load(pp, allow_pickle=False) as gains:
                for row in pair:
                    k = gains[row['method']]
                    gap, rho, _ = performance_gap(s, k) if np.isfinite(k).all() else (np.inf, np.inf, None)
                    stable = np.isfinite(gap); assert stable == row['stable']
                    if stable:
                        error = abs(gap - row['gap']); max_error = max(max_error, error)
                        assert error < 1e-8
                    checked += 1
        with np.load(out / 'checkpoints' / (stem + '.npz'), allow_pickle=False) as cp:
            theta = run.cho_solve(run.cho_factor((cp['gram']+cp['gram'].T)/2), cp['cross'].T).T
        with np.load(out / 'estimates' / (stem + '.npz'), allow_pickle=False) as fit:
            np.testing.assert_array_equal(theta, np.concatenate((fit['Ahat'], fit['Bhat']), axis=1))
        data[4, seed] = raw; rows_all += raw['records']
        print(json.dumps(dict(audited_rank=4, seed=seed, seconds=time.monotonic()-began)), flush=True)
    audit = dict(status='PASS', paired_tasks=len(seeds), unique_policies_reevaluated=checked,
        maximum_performance_identity_gap_error=max_error, final_joint_OLS_recomputed=len(seeds),
        physical_transitions=len(seeds)*max(budgets), sources_sha256=hashes,
        slurm_job_id=os.environ['SLURM_JOB_ID'])
    e.atomic_json(dest / 'audit.json', audit)
    ranks = [4]
    if phase == 'confirm':
        source = Path(cfg['source_output']); manifest = e.read(source / 'artifact_sha256.json')
        assert e.sha(source / 'artifact_sha256.json') == cfg['source_manifest_sha256']
        assert e.read(source / 'report-confirm/audit.json')['unique_policies_reevaluated'] == 4050
        assert e.read(source / 'report-confirm/execution_cost_audit.json')['status'] == 'PASS'
        ranks = [2, 4, 8, 32, 64, 500]
        for rank in ranks:
            if rank == 4: continue
            for seed in seeds:
                relative = f'raw/ce-r{rank:03d}-s{seed:04d}.json'; path = source / relative
                assert e.sha(path) == manifest[relative]
                raw = e.read(path); assert raw['budgets'] == cfg['confirm_budgets']
                data[rank, seed] = raw; rows_all += raw['records']
        audit['reused_existing_policy_audit'] = str(source / 'report-confirm/audit.json')
        audit['existing_timeout_effect_on_N90'] = 'All thresholds verified unchanged by all 8 discarded-transition scenarios in the source execution-cost audit.'
        e.atomic_json(dest / 'audit.json', audit)
    count = len(seeds)
    indices = np.random.default_rng(cfg['bootstrap_seed']).integers(0, count, size=(cfg['bootstrap_replicates'], count))
    rates = []; requirements = []; gaps = {}; bootN = {}
    for rank in ranks:
        for method in ('dense', 'truncated'):
            records = [[next(q for q in data[rank, seed]['records'] if q['transitions'] == b and q['method'] == method)
                        for b in budgets] for seed in seeds]
            gap = np.array([[q['gap'] if q['stable'] else np.inf for q in rr] for rr in records]); gaps[rank, method] = gap
            for target in cfg['relative_targets']:
                success = gap <= target * cfg['initial_gap']; n90 = float(threshold(success, budgets))
                boot = threshold(success[indices], budgets); bootN[rank, method, target] = boot
                ci = np.quantile(boot, [.025, .975], method='nearest')
                hit = budgets.index(n90) if np.isfinite(n90) else None
                for j, budget in enumerate(budgets):
                    wins = int(success[:, j].sum()); low, high = wilson(wins, count)
                    unstable = sum(rr[j].get('failure') == 'controller_instability' for rr in records)
                    failed = sum(rr[j].get('failure') == 'riccati_failure' for rr in records)
                    il, ih = wilson(unstable, count)
                    rates.append(dict(rank=rank, method=method, relative_target=target, transitions=budget,
                        seeds=count, successes=wins, success_rate=wins/count, ci95_low=low, ci95_high=high,
                        instabilities=unstable, instability_ci95_low=il, instability_ci95_high=ih, numerical_failures=failed))
                selected = rates[-len(budgets)+hit] if hit is not None else rates[-1]
                requirements.append(dict(rank=rank, method=method, relative_target=target, initial_gap=cfg['initial_gap'],
                    seeds=count, N_hat_90=finite(n90), status='reached' if hit is not None else 'not reached',
                    previous_tested_budget=budgets[hit-1] if hit is not None and hit else None,
                    bootstrap95_low=finite(ci[0]), bootstrap95_high=finite(ci[1]),
                    bootstrap_unreached_fraction=float(np.isinf(boot).mean()), successes=selected['successes'],
                    success_ci95_low=selected['ci95_low'], success_ci95_high=selected['ci95_high'],
                    instabilities=selected['instabilities'], instability_ci95_low=selected['instability_ci95_low'],
                    instability_ci95_high=selected['instability_ci95_high'], max_budget=max(budgets)))
    for name, rows in [('sample_complexity', requirements), ('success_by_budget', rates), ('all_checkpoints', rows_all)]:
        csv_save(dest / (name + '.csv'), rows)
    e.atomic_json(dest / 'summary.json', dict(status='complete', phase=phase, requirements=requirements,
        ranks=ranks, initial_gap=1, relative_targets=cfg['relative_targets'], primitive_budgets=budgets,
        new_policy_audit=audit, note='Same trajectory OLS; no ridge or whitening; only estimated B truncated.'))
    if phase == 'confirm':
        scaling(cfg, dest, ranks, requirements, rates, gaps, bootN, indices, budgets)


def scaling(cfg, dest, ranks, requirements, rates, gaps, bootN, indices, budgets):
    focus = [2, 4, 8, 32]; comparisons = []; fixed = []; fits = []
    def requirement(r, m, t):
        return next(q for q in requirements if q['rank'] == r and q['method'] == m and q['relative_target'] == t)
    for target in cfg['relative_targets']:
        full = requirement(500, 'dense', target)['N_hat_90']
        for rank in ranks:
            item = requirement(rank, 'truncated', target); n = item['N_hat_90']
            comparisons.append(dict(rank=rank, relative_target=target, N_hat_90=n,
                N_per_rank=n/rank if n is not None else None,
                full_rank_dense_sample_saving=full/n if n and full else None))
        for lo, hi in zip(focus[:-1], focus[1:]):
            nl = requirement(lo, 'truncated', target)['N_hat_90']; nh = requirement(hi, 'truncated', target)['N_hat_90']
            ratio = bootN[hi, 'truncated', target] / bootN[lo, 'truncated', target]
            q = np.quantile(ratio, [.025, .975], method='nearest')
            fits.append(dict(metric='adjacent_N90_ratio', relative_target=target, low_rank=lo, high_rank=hi,
                rank_ratio=hi/lo, value=nh/nl if nl and nh else None, bootstrap95_low=finite(q[0]), bootstrap95_high=finite(q[1])))
    # These two prefixes precede every resource timeout in the source campaign.
    for budget in (131328, 262400):
        j = budgets.index(budget)
        for rank in ranks:
            for method in ('dense', 'truncated'):
                x = gaps[rank, method][:, j]; bs = np.median(x[indices], axis=-1)
                q = np.quantile(bs, [.025, .975])
                fixed.append(dict(rank=rank, method=method, transitions=budget, median_gap=float(np.median(x)),
                    gap_per_rank=float(np.median(x))/rank, median_bootstrap95_low=float(q[0]), median_bootstrap95_high=float(q[1])))
        x = np.asarray(focus); y = np.array([np.median(gaps[r, 'truncated'][:, j]) for r in focus])
        design = np.column_stack((np.ones(len(x)), x)); intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
        prediction = design @ np.array([intercept, slope]); proportional = (x@y)/(x@x)
        bs_y = np.stack([np.median(gaps[r, 'truncated'][indices, j], axis=-1) for r in focus], axis=1)
        bs_coef = np.linalg.lstsq(design, bs_y.T, rcond=None)[0]
        fits.append(dict(metric='fixed_budget_affine_fit', transitions=budget, ranks=focus,
            intercept=float(intercept), slope=float(slope), R_squared=float(1-np.sum((y-prediction)**2)/np.sum((y-y.mean())**2)),
            max_relative_residual=float(np.max(abs(y-prediction)/y)), proportional_slope=float(proportional),
            proportional_max_relative_residual=float(np.max(abs(y-proportional*x)/y)),
            intercept_bootstrap95=list(np.quantile(bs_coef[0], [.025, .975])),
            slope_bootstrap95=list(np.quantile(bs_coef[1], [.025, .975]))))
    csv_save(dest / 'rank_scaling_comparison.csv', comparisons); csv_save(dest / 'fixed_budget_rank_scaling.csv', fixed)
    e.atomic_json(dest / 'scaling_analysis.json', dict(focus_ranks=focus, results=fits,
        interpretation='Descriptive conditional fits on one shared system. An affine trend is distinct from N proportional to rank. Coarse budget brackets are not confidence intervals. Seed bootstraps do not quantify variability across systems.'))
    plt.rcParams.update({'font.size': 10, 'axes.grid': True, 'grid.alpha': .2})
    def save(fig, name):
        for ext in ('png', 'svg'): fig.savefig(dest / (name + '.' + ext), dpi=180, facecolor='white')
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4), layout='constrained')
    for ax, target in zip(axes, cfg['relative_targets']):
        for method, color in [('dense', '#ba4737'), ('truncated', '#1476a3')]:
            rs = [requirement(r, method, target) for r in focus]
            ax.plot(focus, [q['N_hat_90'] for q in rs], 'o-', color=color, label=method)
            for q in rs:
                if q['N_hat_90'] and q['previous_tested_budget']:
                    ax.vlines(q['rank'], q['previous_tested_budget'], q['N_hat_90'], color=color, lw=3, alpha=.3)
        ax.axhline(requirement(500, 'dense', target)['N_hat_90'], color='.45', ls='--', label='rank 500 dense')
        ax.set(xticks=focus, xlabel='Actuation rank', ylabel='Primitive transitions for >=90% empirical success',
               title=f'Relative target {target:g}')
        ax.legend(fontsize=8)
    fig.suptitle('CE500 | initial gap = 1 | 30 paired seeds | bars: tested budget brackets')
    save(fig, 'sample_complexity_rank_2_4_8_32')
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4), layout='constrained')
    for ax, budget in zip(axes, (131328, 262400)):
        for method, color in [('dense', '#ba4737'), ('truncated', '#1476a3')]:
            rows = [next(q for q in fixed if q['rank']==r and q['method']==method and q['transitions']==budget) for r in focus]
            ax.plot(focus, [q['median_gap'] for q in rows], 'o-', color=color, label=method)
            ax.fill_between(focus, [q['median_bootstrap95_low'] for q in rows], [q['median_bootstrap95_high'] for q in rows], color=color, alpha=.15)
        fit = next(q for q in fits if q['metric']=='fixed_budget_affine_fit' and q['transitions']==budget)
        xx = np.linspace(0, 32, 100); ax.plot(xx, fit['intercept'] + fit['slope']*xx, ':', color='#1476a3', label='truncated affine fit')
        ax.set(xticks=focus, xlabel='Actuation rank', ylabel='Median absolute = relative optimality gap', title=f'{budget:,} transitions')
        ax.legend(fontsize=8)
    fig.suptitle('Same-budget comparison | shaded: paired-seed bootstrap 95% CI of medians')
    save(fig, 'fixed_budget_gap_vs_rank')
    fig, axes = plt.subplots(2, 4, figsize=(15, 6), sharey=True, layout='constrained')
    for i, target in enumerate(cfg['relative_targets']):
        for ax, rank in zip(axes[i], focus):
            for method, color in [('dense', '#ba4737'), ('truncated', '#1476a3')]:
                rows = [q for q in rates if q['rank']==rank and q['method']==method and q['relative_target']==target]
                ax.plot(budgets, [q['success_rate'] for q in rows], color=color, label=method)
                ax.fill_between(budgets, [q['ci95_low'] for q in rows], [q['ci95_high'] for q in rows], color=color, alpha=.12)
            ax.axhline(.9, color='.4', ls=':'); ax.set(xscale='log', xlabel='Transition budget', title=f'rank {rank} | target {target:g}')
        axes[i, 0].set_ylabel('Success probability')
    axes[0, -1].legend(); save(fig, 'success_probability_rank_2_4_8_32')


def main():
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['pilot', 'confirm'])
    p.add_argument('--manifest', type=Path, required=True); a = p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    with threadpool_limits(1): report(e.read(a.manifest), a.mode)


if __name__ == '__main__': main()
