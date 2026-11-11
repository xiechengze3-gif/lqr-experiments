"""Integrate completed NPG precision diagnostics; run only on Grace Slurm."""
import csv
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT = Path('/scratch/user/changze/lqr_experiments/results')
AUDIT = ROOT / 'npg-precision-e7ce4b139191d361'
RESCUE = ROOT / 'npg-precision-rescue-648c7b54441471c3'


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
        raise RuntimeError('Numerical analysis requires Grace Slurm')
    primary = json.loads((AUDIT / 'report/summary.json').read_text())
    intervention = json.loads((RESCUE / 'report/summary.json').read_text())
    if not primary['complete'] or not intervention['complete']:
        raise RuntimeError('Upstream report incomplete')
    actors = read(AUDIT / 'report/actor_records.csv')
    groups = defaultdict(list)
    for row in actors:
        if row['stage'] == 24:
            groups[row['n'], row['tail'], row['method']].append(row)
    endpoints = []
    for (n, tail, method), rows in sorted(groups.items()):
        endpoints.append(dict(n=n, tail=tail, method=method, systems=len(rows),
            gap_mean=float(np.mean([r['gap'] for r in rows])),
            relative_E_error_mean=float(np.mean([r['relative_E_error'] for r in rows])),
            direction_cosine_mean=float(np.mean([r['direction_cosine'] for r in rows])),
            horizon_bias_relative_E_max=max(r['horizon_bias_relative_E'] for r in rows),
            error_op_over_sigma_r_mean=float(np.mean([r['error_op_over_sigma_r'] for r in rows]))))
    refs = read(ROOT / 'dense-isotropic-overview-7f5c6de07fb244ab/report/actor_optimization_reference.csv')
    exact = []
    for n in (50, 100):
        rows = [r for r in refs if r['n'] == n and r['tail'] == 0 and r['stage'] == 24 and r['method'] == 'raw' and r['algorithm'] == 'NPG']
        if len(rows) != 2:
            raise RuntimeError('Missing exact-critic matched-iteration reference')
        exact.append(dict(n=n, updates=24, gap_mean=float(np.mean([r['gap'] for r in rows])), systems=2))
    aggregate = read(AUDIT / 'report/fixed_aggregate.csv')
    near = [r for r in aggregate if r['policy'] == 'exact128' and r['N'] in (16384, 262144, 1048576)]
    statistical_slopes = []
    groups = defaultdict(list)
    for row in aggregate:
        if row['tail'] == 0:
            groups[row['n'], row['policy'], row['method']].append(row)
    for (n, policy, method), rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda r:r['N'])
        x = np.log([r['N'] for r in rows])
        y = np.log([r['sampling_error_fro2_mean'] for r in rows])
        slope = np.polyfit(x, y, 1)[0]
        statistical_slopes.append(dict(n=n, policy=policy, method=method, gamma_N=float(-slope),
                                      interpretation='Descriptive within-policy sampling MSE slope over four prefixes, no dimension/rank exponent or asymptotic claim'))
    horizon_by_stage = []
    for lower in (1, 9, 17):
        rows = [r for r in actors if r['stage'] >= lower]
        horizon_by_stage.append(dict(stage_at_least=lower, maximum_relative_E_bias=max(r['horizon_bias_relative_E'] for r in rows),
                                    minimum_relative_E_sampling_error=min(r['relative_E_error'] for r in rows)))
    all_fixed = read(AUDIT / 'report/fixed_records.csv')
    summary = dict(complete=True, configurations=54, actor_replays=6, independent_fixed_policy_tasks=44,
        intervention_starting_policies=4, actor_endpoints=endpoints,
        exact_critic_from_K0_24_update_reference=exact,
        near_optimum_precision=near, sampling_MSE_slopes=statistical_slopes,
        horizon_bias_vs_sampling=horizon_by_stage,
        maximum_fixed_gram_condition=max(r['gram_condition'] for r in all_fixed),
        intervention_final_means=intervention['final_means'],
        replay_records_checked=primary['replay_records_checked'],
        maximum_replay_gap_difference=primary['maximum_replay_gap_difference'],
        caveats=['Relative error above one does not imply every update must increase cost; use actual one-step cost changes',
                 'Larger-batch intervention uses four times the samples at matched iteration count; not a sample-complexity gain',
                 'Two system seeds; near-optimum calibration has two independent collector seeds per system',
                 'Exact-critic continuation starts at the same sampled K, not at the original K0',
                 'Known RK remains exact; all exact matrices are diagnostics only',
                 'Some final gap is optimization residual even with exact critics'],
        slurm_job_id=os.environ['SLURM_JOB_ID'],
        analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (AUDIT / 'report/integrated_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k:v for k,v in summary.items() if k != 'sampling_MSE_slopes'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
