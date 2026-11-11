"""Unknown-rank CE on the exact historical prefix streams. Slurm only."""
import argparse
import csv
import json
import os
import resource
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from ce_high_rank import ROOT, config, extended_system, read, sha
from ce_precision_zoom import attainment
from adaptive_rank import ce_update, noise_proxy
from dense_scaling import atomic_json, ce_chunk, nominal_chunk, rng_for, dare, evaluate, trunc, require_compute


def models(s, task, budgets, capture=False):
    """Keep original full-chunk sums/RNG. Extra midpoint sums never split sampling."""
    n, k = task['n'], s['K0']
    rng = rng_for(633771, n, task['system_seed'], task['trial_seed'])
    f = np.ascontiguousarray(s['A']-s['B']@k)
    x, _ = nominal_chunk(f, np.zeros(n), rng.normal(size=(512, n)))
    gram, cross = np.zeros((2*n, 2*n)), np.zeros((n, 2*n))
    mids, snapshots = sorted({b//2 for b in budgets}), {}
    cursor, done = 0, 0
    zs, ys = [], []
    for budget in budgets:
        while done < budget:
            size = min(1024, budget-done)
            x, z, y = ce_chunk(f, s['B'], k, x, rng.normal(size=(size, n)), rng.normal(size=(size, n)))
            if capture: zs.append(z.copy()); ys.append(y.copy())
            while cursor < len(mids) and mids[cursor] <= done+size:
                mid = mids[cursor]
                count = mid-done
                assert 0 <= count <= size
                snapshots[mid] = (gram+z[:count].T@z[:count], cross+y[:count].T@z[:count])
                cursor += 1
            gram += z.T@z
            cross += y.T@z
            done += size
        first_g, first_c = snapshots.pop(budget//2)
        full = np.linalg.solve(gram, cross.T).T
        first = np.linalg.solve(first_g, first_c.T).T
        second = np.linalg.solve(gram-first_g, (cross-first_c).T).T
        yield dict(N=budget, full=full, first=first, second=second,
                   z=np.concatenate(zs) if capture else None, y=np.concatenate(ys) if capture else None)


def verify(cfg, out):
    checks = []
    task = dict(n=6, m=6, r=2, system_seed=9007, trial_seed=0,
                family='coupled_unstable', stabilizer='isotropic', tail=0., tail_shape='energy')
    s = extended_system(task)
    for item in models(s, task, [512, 2048, 4096], capture=True):
        z, y, mid = item['z'], item['y'], item['N']//2
        for name, zz, yy in [('full', z, y), ('first', z[:mid], y[:mid]), ('second', z[mid:], y[mid:])]:
            expected = np.linalg.lstsq(zz, yy, rcond=None)[0].T
            np.testing.assert_allclose(item[name], expected, rtol=1e-9, atol=1e-10)
        scale = noise_proxy(item['first'][:, 6:], item['second'][:, 6:])
        args = (item['full'][:, :6], item['full'][:, 6:], s['Q'], s['R'], 'adaptive_1', scale)
        clean = ce_update(*args)
        poisoned = ce_update(*args, known_rank=6)
        np.testing.assert_array_equal(clean[0], poisoned[0])
        assert clean[2] == poisoned[2]
        checks.append(dict(N=item['N'], independent_full_and_halves_OLS=True, adaptive_reference_rank_invariant=True))
    out.mkdir(parents=True, exist_ok=True)
    atomic_json(out/'verification.json', dict(status='PASS', identity=sha(ROOT/'manifest.json'),
                checks=checks, slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS', checks=checks)), flush=True)


def run(cfg, out, index):
    proof = read(out/'verification.json')
    assert proof['status'] == 'PASS' and proof['identity'] == sha(ROOT/'manifest.json')
    item = cfg['datasets'][index]
    p = ROOT/item['bundle_path']
    assert sha(p) == item['sha256']
    old = {(r['N'], r['method']): r for r in read(p)['records']}
    task, rows, checks = item['task'], [], []
    dest = out/'raw'/f'task-{index:03d}.json'
    assert not dest.exists(), 'No untracked reruns'
    start = time.monotonic()
    s = extended_system(task)
    for model in models(s, task, cfg['budgets']):
        budget = model['N']
        a, b = model['full'][:, :task['n']], model['full'][:, task['n']:]
        # Recompute both historical outputs to check the entire shared stream.
        for method in ('raw', 'truncated'):
            bhat = b if method == 'raw' else trunc(b, task['r'])
            candidate, _ = dare(a, bhat, s['Q'], s['R'])
            q, _ = evaluate(s, candidate)
            expected = old[budget, method]
            assert q['stable'] == expected['stable']
            for name in ('gap', 'cost', 'rho'):
                if q.get(name) is not None:
                    np.testing.assert_allclose(q[name], expected[name], rtol=1e-8, atol=1e-7)
            np.testing.assert_allclose(float(np.sum((bhat-s['B'])**2)), expected['B_error_fro2'], rtol=1e-8, atol=1e-7)
            checks.append(dict(N=budget, method=method, status='PASS'))
        # Learning receives model estimates and known costs only; no true rank/model/evaluator.
        scale = noise_proxy(model['first'][:, task['n']:], model['second'][:, task['n']:])
        row = dict(method='adaptive', N=budget, transitions=budget+512, noise_proxy=scale)
        try:
            candidate, bhat, info = ce_update(a, b, s['Q'], s['R'], cfg['adaptive']['method'], scale)
            q, _ = evaluate(s, candidate)
            row.update(q, **info, B_error_fro2=float(np.sum((bhat-s['B'])**2)))
        except (ValueError, np.linalg.LinAlgError) as error:
            # Preserve rank/threshold even when Riccati fails.
            from adaptive_rank import select
            _, _, info = select(b, cfg['adaptive']['method'], scale)
            row.update(stable=False, gap=None, relative_gap=None, failure=str(error), **info)
        rows.append(row)
    assert len(checks) == 2*len(cfg['budgets'])
    atomic_json(dest, dict(task=task, records=rows, historical_replay_checks=checks,
        identity=proof['identity'], actual_physical_transitions=max(cfg['budgets'])+512,
        seconds=time.monotonic()-start, peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(rank=task['r'], seed=task['system_seed'], checks=len(checks), seconds=time.monotonic()-start)), flush=True)


def report(cfg, out):
    ident = sha(ROOT/'manifest.json')
    endpoints, replay_checks, ranks = [], 0, []
    for index, item in enumerate(cfg['datasets']):
        old_path = ROOT/item['bundle_path']
        assert sha(old_path) == item['sha256']
        new = read(out/'raw'/f'task-{index:03d}.json')
        assert new['identity'] == ident and new['task'] == item['task']
        replay_checks += len(new['historical_replay_checks'])
        task = item['task']
        for row in read(old_path)['records']+new['records']:
            endpoints.append(dict(rank=task['r'], seed=task['system_seed'], method=row['method'],
                budget=row['transitions'], absolute_gap=row.get('gap'), stable=row['stable'],
                success=bool(row['stable'] and row.get('gap') is not None and row['gap'] <= cfg['absolute_epsilon']),
                retained_rank=row.get('retained_rank'), threshold=row.get('threshold'),
                origin='new_adaptive' if row['method']=='adaptive' else 'verified_historical'))
            if row['method'] == 'adaptive':
                ranks.append(dict(true_rank=task['r'], seed=task['system_seed'], budget=row['transitions'],
                    retained_rank=row['retained_rank'], threshold=row['threshold'], noise_proxy=row['noise_proxy'],
                    correct_rank=row['retained_rank']==task['r']))
    assert len(endpoints) == 8*3*len(cfg['budgets']) and replay_checks == 8*2*len(cfg['budgets'])
    groups = defaultdict(list)
    for row in endpoints: groups[row['rank'], row['method'], row['budget']].append(row)
    summary = []
    for (rank, method, budget), vals in sorted(groups.items()):
        assert len(vals) == 2 and {v['seed'] for v in vals} == {0, 1}
        finite = [v['absolute_gap'] for v in vals if v['stable'] and v['absolute_gap'] is not None]
        summary.append(dict(rank=rank, method=method, budget=budget, success=all(v['success'] for v in vals),
            successes=sum(v['success'] for v in vals), worst_absolute_gap=max(finite) if len(finite)==2 else None))
    crossings, per_seed = [], []
    for rank in cfg['ranks']:
        for method in cfg['methods']:
            crossing = dict(rank=rank, method=method, **attainment([r for r in summary if r['rank']==rank and r['method']==method], .1))
            if method == 'adaptive' and crossing['first_tested_budget'] is not None:
                at = [r for r in ranks if r['true_rank']==rank and r['budget']==crossing['first_tested_budget']]
                crossing['retained_ranks_at_first_hit'] = [r['retained_rank'] for r in sorted(at, key=lambda r:r['seed'])]
            else: crossing['retained_ranks_at_first_hit'] = None
            crossings.append(crossing)
            for seed in (0, 1):
                per_seed.append(dict(rank=rank, method=method, seed=seed, **attainment(
                    [r for r in endpoints if r['rank']==rank and r['method']==method and r['seed']==seed], .1)))
    dest = out/'report'
    dest.mkdir(parents=True, exist_ok=True)
    for name, rows in [('endpoints', endpoints), ('success_by_budget', summary), ('sample_to_accuracy', crossings),
                       ('per_seed_attainment', per_seed), ('adaptive_rank_by_budget', ranks)]:
        with (dest/f'{name}.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = dict(zip(cfg['ranks'], ['#2563eb', '#ea580c', '#16a34a', '#9333ea']))
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True)
    for ax, method, title in zip(axes, cfg['methods'], ['Dense CE', 'Known-rank CE', 'Adaptive CE (unknown rank)']):
        for rank in cfg['ranks']:
            vals = [r for r in summary if r['rank']==rank and r['method']==method and r['worst_absolute_gap'] is not None]
            ax.plot([r['budget'] for r in vals], [r['worst_absolute_gap'] for r in vals], color=colors[rank], label=f'r={rank}')
        ax.axhline(.1, color='#dc2626', ls='--', lw=1)
        ax.set(xlim=(32768, 225792), ylim=(.045, .17), xlabel='Total transitions (incl. 512 burn)', title=title)
        ax.ticklabel_format(axis='x', style='sci', scilimits=(0, 0)); ax.grid(alpha=.2); ax.legend()
    axes[0].set_ylabel('Worst absolute J-Jstar across 2 systems')
    fig.suptitle('100d CE | fixed absolute target 0.1 | paired data prefixes | adaptive c=1 frozen')
    fig.tight_layout()
    for ext in ('png', 'svg'): fig.savefig(dest/f'precision_zoom_three_methods.{ext}', dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    ax = axes[0]
    for method, label, color, offset in [('raw', 'Dense', '#2563eb', -.24), ('truncated', 'Known-rank', '#ea580c', 0), ('adaptive', 'Adaptive', '#16a34a', .24)]:
        vals = [next(r for r in crossings if r['rank']==rank and r['method']==method) for rank in cfg['ranks']]
        ys = [r['first_tested_budget'] if r['first_tested_budget'] is not None else max(cfg['budgets'])+512 for r in vals]
        xs = np.arange(4)+offset
        ax.bar(xs, ys, width=.23, color=color, label=label)
        for x, y, row in zip(xs, ys, vals):
            ax.text(x, y+2300, ('>' if row['right_censored'] else '')+f'{y/1000:.1f}k', ha='center', fontsize=8, rotation=60)
    ax.set_xticks(range(4), cfg['ranks']); ax.set(xlabel='True rank', ylabel='First tested total transitions: 2/2 attain', title='Absolute gap <= 0.1')
    ax.set_ylim(0, max(225000, max(y['first_tested_budget'] or max(cfg['budgets'])+512 for y in crossings)*1.24))
    ax.legend(loc='upper left'); ax.grid(axis='y', alpha=.2)
    ax = axes[1]
    for rank in cfg['ranks']:
        for seed in (0, 1):
            vals = [r for r in ranks if r['true_rank']==rank and r['seed']==seed]
            ax.plot([r['budget'] for r in vals], [r['retained_rank'] for r in vals], color=colors[rank],
                    ls='-' if seed==0 else '--', label=f'r={rank}' if seed==0 else None)
    ax.set(xscale='log', xlabel='Total transitions (incl. burn)', ylabel='Automatically retained rank', title='Data-only half-split threshold; c=1', ylim=(-2, 103)); ax.legend(); ax.grid(alpha=.2)
    fig.tight_layout()
    for ext in ('png', 'svg'): fig.savefig(dest/f'adaptive_comparison.{ext}', dpi=170)
    plt.close(fig)
    result = dict(status='COMPLETE', datasets=8, prefixes=len(cfg['budgets']), records=len(endpoints),
        adaptive_records=len(ranks), historical_replay_checks=replay_checks,
        unstable_records=sum(not r['stable'] for r in endpoints),
        adaptive_unstable_records=sum(not r['stable'] for r in endpoints if r['method']=='adaptive'),
        first_equals_sustained=all(r['first_tested_budget']==r['sustained_tested_budget'] for r in crossings+per_seed),
        crossings=crossings, new_physical_transitions=8*(max(cfg['budgets'])+512), slurm_job_id=os.environ['SLURM_JOB_ID'])
    atomic_json(dest/'summary.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['verify', 'run', 'report'])
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--task-id', type=int)
    args = parser.parse_args(); cfg = config()
    if args.mode == 'verify': verify(cfg, args.output)
    elif args.mode == 'run': run(cfg, args.output, args.task_id)
    else: report(cfg, args.output)
