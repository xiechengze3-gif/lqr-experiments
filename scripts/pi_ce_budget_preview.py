"""Complete CE/PI fixed-precision budgets; computation requires Grace Slurm."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from dense_scaling import require_compute, atomic_json


def main(release, output):
    release, output = Path(release), Path(output)
    endpoints = []
    for profile in ('ce', 'pi-32768', 'pi-131072', 'pi-524288'):
        manifest = release / f'configs/cross_rank_{profile}.json'
        cfg = json.loads(manifest.read_text())
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        algorithm = 'CE' if profile == 'ce' else 'PI-LSTD'
        for tid, task in enumerate(cfg['tasks']):
            payload = json.loads((output/profile/'raw'/f'task-{tid:03d}.json').read_text())
            assert payload['task'] == task and payload['manifest_sha256'] == digest
            for method in ('raw', 'truncated'):
                records = [row for row in payload['records'] if row['method'] == method]
                solver_ok = all(row.get('solver', {}).get('converged', True) for row in records)
                for row in records if algorithm == 'CE' else records[-1:]:
                    budget = row['N']+512 if algorithm == 'CE' else 6*(cfg['batch_schedule'][0]+1024)
                    eligible = bool(row['stable'] and solver_ok and
                                    (algorithm == 'CE' or row['stage'] == 6))
                    endpoints.append(dict(algorithm=algorithm, method=method,
                        n=task['n'], r=task['r'], seed=task['system_seed'], tail=task['tail'],
                        budget=budget, actual_transitions=row['transitions'],
                        gap=row['gap'], eligible=eligible))
    thresholds = []
    cells = sorted(set((e['algorithm'], e['method'], e['n'], e['r'], e['tail']) for e in endpoints))
    for algorithm, method, n, rank, tail in cells:
        rows = [e for e in endpoints if
                (e['algorithm'], e['method'], e['n'], e['r'], e['tail']) ==
                (algorithm, method, n, rank, tail)]
        budgets = sorted(set(e['budget'] for e in rows))
        for epsilon in (5., 2., 1., .5, .1):
            success = []
            for budget in budgets:
                group = [e for e in rows if e['budget'] == budget]
                assert len(group) == 2 and len(set(e['seed'] for e in group)) == 2
                success.append(all(e['eligible'] and e['gap'] <= epsilon for e in group))
            at = next((i for i in range(len(budgets)) if all(success[i:])), None)
            thresholds.append(dict(algorithm=algorithm, method=method, n=n, r=rank,
                tail=tail, epsilon=epsilon, tested_budgets=budgets, success_by_budget=success,
                status='right_censored' if at is None else ('left_censored' if at == 0 else 'attained'),
                budget=None if at is None else budgets[at],
                lower_budget=budgets[-1] if at is None else (0 if at == 0 else budgets[at-1])))
    colors = {'raw': '#c44e52', 'truncated': '#4c72b0'}
    markers = {'attained': 'o', 'left_censored': 'v', 'right_censored': '^'}
    legend = [Line2D([0], [0], color=color, marker='o', label=method) for method, color in colors.items()]
    legend += [Line2D([0], [0], color='#555555', marker=marker, linestyle='None', label=label)
               for marker, label in (('v', 'already succeeds at smallest tested budget'),
                                     ('^', 'not attained through largest tested budget'))]
    preview = output/'preview'
    preview.mkdir(exist_ok=True)
    for epsilon in (1., .1):
        fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
        for row, algorithm in enumerate(('CE', 'PI-LSTD')):
            for col, n in enumerate((50, 100)):
                ax = axes[row, col]
                for method, color in colors.items():
                    selected = sorted([t for t in thresholds if t['algorithm'] == algorithm
                        and t['method'] == method and t['n'] == n and t['tail'] == 0
                        and t['epsilon'] == epsilon], key=lambda t: t['r'])
                    measured = [t for t in selected if t['budget'] is not None]
                    ax.plot([t['r'] for t in measured], [t['budget'] for t in measured], color=color, alpha=.6)
                    for t in selected:
                        # Tiny horizontal separation makes coincident censor markers visible;
                        # numeric rank ticks and JSON retain the actual rank.
                        offset = .97 if method == 'raw' else 1.03
                        ax.scatter(t['r']*offset, t['budget'] or t['lower_budget'],
                                   color=color, marker=markers[t['status']], s=48, zorder=3)
                ax.set(xscale='log', yscale='log', xlabel='Rank r', ylabel='Primitive transitions',
                       title=f'{algorithm}, n={n}, absolute gap <= {epsilon:g}')
                ax.set_xticks([1, 2, 4, 8, 16], labels=['1', '2', '4', '8', '16'])
                ax.grid(alpha=.2)
        fig.suptitle('Minimum tested fixed-output budget: 2/2 systems succeed at this and every higher tested budget')
        fig.legend(handles=legend, loc='outside lower center', ncol=2, fontsize=9)
        tag = '1' if epsilon == 1. else '0p1'
        fig.savefig(preview/f'pi_ce_fixed_precision_{tag}.png', dpi=180)
        fig.savefig(preview/f'pi_ce_fixed_precision_{tag}.pdf')
        plt.close(fig)
    atomic_json(preview/'pi_ce_fixed_precision.json', dict(thresholds=thresholds,
        endpoints=endpoints, complete_CE_PI=True, slurm_job_id=os.environ['SLURM_JOB_ID'],
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        interpretation='Coarse tested grid, two systems per cell. Planned cost of one fixed-output run, including burn. Early controller failures stay failures. Not exact population sample complexity; campaign search cost is separate.'))


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.release, args.output)
