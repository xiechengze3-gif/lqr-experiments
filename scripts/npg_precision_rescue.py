"""Matched-iteration NPG precision intervention at saved sampled policies."""
import argparse
import csv
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
from dense_scaling import system, targets, trunc, eta, evaluate, pulse_moments, rng_for, atomic_json, require_compute
from npg_precision_audit import context, update_diagnostic


def run(manifest, task_id, audit_root, output):
    config = json.loads(Path(manifest).read_text())
    spec = config['tasks'][task_id]
    audit_manifest = Path(config['audit_manifest'])
    audit = json.loads(audit_manifest.read_text())
    task = audit['actor_tasks'][spec['actor_task']]
    s = system(task)
    s['audit_rank'] = task['r']
    path = Path(audit_root) / 'policies' / f"actor-{spec['actor_task']:02d}.npz"
    prior = json.loads((Path(audit_root) / 'raw' / f"actor-{spec['actor_task']:02d}.json").read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != prior['policy_archive_sha256']:
        raise RuntimeError('Policy provenance mismatch')
    with np.load(path) as archive:
        initial = archive[spec['policy']].copy()
    method = 'raw' if spec['policy'].startswith('raw') else 'truncated'
    records = []
    for multiplier in (1, 4, 0):
        k, x, total = initial.copy(), np.zeros(task['n']), 0
        initial_quality = evaluate(s, k)[0]
        records.append(dict(multiplier=multiplier, method=method, stage=0, transitions=0, observed=True, **initial_quality))
        for stage in range(8):
            ctx = context(s, k, 16)
            count = multiplier * 262144
            if multiplier:
                # Shared innovations; first N blocks are paired at stage one.
                _, x, raw, _, _, used = next(pulse_moments(s, k, x, [count], 16, 1.,
                    rng_for(331779, spec['actor_task'], task['system_seed'], stage), burn=1024))
                total += used
            else:
                raw = targets(s, k, 16)['Z']
            z = raw if method == 'raw' else trunc(raw, task['r'])
            quality = update_diagnostic(s, ctx, z, method)
            records.append(dict(multiplier=multiplier, stage=stage + 1, N=count, transitions=total, observed=True, **quality))
            k = k - eta(s) * (s['R'] @ k + z)
            atomic_json(Path(output) / 'raw' / f'progress-{task_id:02d}.json', dict(task=task, spec=spec, records=records))
            if not quality['stable']:
                for remaining in range(stage + 2, 9):
                    records.append(dict(multiplier=multiplier, method=method, stage=remaining, N=count,
                                        transitions=remaining*(1024+(count+1)*16), observed=False, stable=False, gap=None))
                break
        print(json.dumps(dict(task_id=task_id, multiplier=multiplier, final=records[-1])), flush=True)
    atomic_json(Path(output) / 'raw' / f'rescue-{task_id:02d}.json',
                dict(task=task, spec=spec, records=records,
                     policy_archive_sha256=prior['policy_archive_sha256'],
                     source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
                     slurm_job_id=os.environ['SLURM_JOB_ID'],
                     design='Eight NPG updates from the SAME saved policy. Each sampled arm starts a NEW independent continuous trajectory with zero state and counted burn-in; do not claim continuation of the original trajectory. Multiplier 0 is an exact-critic reference, not a sampled learner.'))


def report(manifest, output):
    config = json.loads(Path(manifest).read_text())
    root = Path(output)
    rows = []
    for task_id, spec in enumerate(config['tasks']):
        path = root / 'raw' / f'rescue-{task_id:02d}.json'
        payload = json.loads(path.read_text())
        if payload['spec'] != spec or payload['manifest_sha256'] != hashlib.sha256(Path(manifest).read_bytes()).hexdigest():
            raise RuntimeError('Rescue provenance mismatch')
        rows.extend(dict(task_id=task_id, n=payload['task']['n'], system_seed=payload['task']['system_seed'], policy=spec['policy'], **r) for r in payload['records'])
    out = root / 'report'
    out.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (out / 'records.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    groups = defaultdict(list)
    for r in rows:
        groups[r['method'], r['multiplier'], r['stage']].append(r)
    aggregate = []
    for (method, multiplier, stage), values in sorted(groups.items()):
        aggregate.append(dict(method=method, multiplier=multiplier, stage=stage, expected=len(values),
            stable_rate=float(np.mean([r['stable'] for r in values])), transitions=values[0]['transitions'],
            gap_mean=float(np.mean([r['gap'] for r in values])) if all(r['stable'] for r in values) else None))
    finals = [r for r in aggregate if r['stage'] == 8]
    summary = dict(complete=True, tasks=len(config['tasks']), final_means=finals,
        exact_reference='Same starting K and 8 updates, zero samples; diagnostic only',
        inference='Precision intervention at matched update count, not a sample-complexity gain',
        uncertainty='Two system seeds, one trajectory per precision arm',
        slurm_job_id=os.environ['SLURM_JOB_ID'])
    (out / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, method in zip(axes, ('raw', 'truncated')):
        for multiplier, color, label in [(1, '#777777', 'Original batch'), (4, '#12699c', '4x batch'), (0, '#35a477', 'Exact critic')]:
            points = sorted([r for r in aggregate if r['method'] == method and r['multiplier'] == multiplier and r['gap_mean'] is not None], key=lambda r:r['stage'])
            ax.plot([r['stage'] for r in points], [r['gap_mean'] for r in points], 'o-', color=color, label=label)
        ax.set_title(f'n=100, r=4: {method} NPG')
        ax.set_xlabel('Additional updates from saved stage-24 policy')
        ax.set_ylabel('Absolute cost gap')
        ax.grid(alpha=.2); ax.legend()
    fig.suptitle('Matched step size and update count; two systems\nSampled arms start independent continuous trajectories at the same saved policy', fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, .90))
    fig.savefig(out / 'precision_intervention.png', dpi=160)
    plt.close(fig)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    require_compute()
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['run', 'report'])
    p.add_argument('--manifest', required=True)
    p.add_argument('--task-id', type=int)
    p.add_argument('--audit-root')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if args.mode == 'run':
        run(args.manifest, args.task_id, args.audit_root, args.output)
    else:
        report(args.manifest, args.output)
