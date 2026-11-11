"""End-to-end NPG rank sweep. Simulation and reporting require real Slurm."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
from dense_scaling import (system, evaluate, targets, eta, trunc, pulse_moments,
                           rng_for, atomic_json, require_compute)
from npg_batched_collector import collect as batched_moments


def provenance(manifest):
    return dict(manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                engine_sha256=hashlib.sha256(Path(system.__code__.co_filename).read_bytes()).hexdigest(),
                slurm_job_id=os.environ['SLURM_JOB_ID'])


def step_size(s, config):
    # Frozen engine uses eta=1/(2*hbar). The inexact descent lemma allows
    # eta*H_K <= I; a common multiplier 2 gives 1/hbar, without model truth.
    return config['step_multiplier'] * eta(s)


def reference(manifest, output):
    config = json.loads(Path(manifest).read_text())
    rows = []
    for task in config['tasks']:
        s = system(task)
        for finite in (False, True):
            k = s['K0'].copy()
            for stage in range(config['stages'] + 1):
                quality, p = evaluate(s, k)
                rows.append(dict(n=task['n'], r=task['r'], system_seed=task['system_seed'],
                                 finite_horizon=finite, stage=stage, eta=step_size(s, config), **quality))
                if not quality['stable']:
                    raise RuntimeError('Exact reference unstable')
                if stage < config['stages']:
                    t = targets(s, k, config['horizon'], p)
                    k -= step_size(s, config) * (s['R'] @ k + t['ZH' if finite else 'Z'])
        print(json.dumps(dict(reference=task, final=rows[-1])), flush=True)
    atomic_json(Path(output) / 'reference.json', dict(records=rows, **provenance(manifest)))


def run(manifest, task_id, output):
    config = json.loads(Path(manifest).read_text())
    task = config['tasks'][task_id]
    collector = batched_moments if config['collector'] == 'batched_equivalent' else pulse_moments
    s = system(task)
    records = []
    started = time.monotonic()
    for method in ('raw', 'truncated'):
        k, x, total = s['K0'].copy(), np.zeros(task['n']), 0
        quality, p = evaluate(s, k)
        records.append(dict(method=method, stage=0, N=0, transitions=0, observed=True, **quality))
        for stage, count in enumerate(config['batch_schedule']):
            # The learning update uses ONLY R, K, sample statistics, r, and eta.
            # Model-dependent quantities below are retrospective diagnostics.
            before = quality['gap']
            true = targets(s, k, config['horizon'], p)
            residual = s['R'] @ k + true['Z']
            _, x, raw, _, gram, used = next(collector(s, k, x, [count],
                config['horizon'], config['sigma'],
                rng_for(773991, task['n'], task['system_seed'], task['trial_seed'], stage),
                burn=config['burn']))
            total += used
            z = raw if method == 'raw' else trunc(raw, task['r'])
            error = z - true['Z']
            direction = s['R'] @ k + z
            k -= step_size(s, config) * direction
            quality, p = evaluate(s, k)
            row = dict(method=method, stage=stage + 1, N=count, transitions=total,
                observed=True, before_gap=before, eta=step_size(s, config),
                critic_error_fro2=float(np.sum(error**2)),
                critic_error_op=float(np.linalg.norm(error, 2)),
                residual_fro2=float(np.sum(residual**2)),
                horizon_bias_fro2=float(np.sum((true['ZH'] - true['Z'])**2)),
                direction_cosine=float(np.sum(direction * residual) /
                    max(np.linalg.norm(direction) * np.linalg.norm(residual), 1e-30)),
                gram_condition=float(np.linalg.cond(gram)),
                elapsed_seconds=time.monotonic() - started, **quality)
            records.append(row)
            payload = dict(task=task, records=records, diagnostics=s['diagnostics'], **provenance(manifest))
            atomic_json(Path(output) / 'raw' / f'progress-{task_id:03d}.json', payload)
            if stage % 8 == 7 or not quality['stable']:
                print(json.dumps(dict(task_id=task_id, **row)), flush=True)
            if not quality['stable']:
                for rest in range(stage + 1, config['stages']):
                    total += config['burn'] + (config['batch_schedule'][rest] + 1) * config['horizon']
                    records.append(dict(method=method, stage=rest + 1,
                        N=config['batch_schedule'][rest], transitions=total,
                        observed=False, stable=False, gap=None))
                break
    atomic_json(Path(output) / 'raw' / f'task-{task_id:03d}.json',
        dict(task=task, records=records, diagnostics=s['diagnostics'], **provenance(manifest)))


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['run', 'reference'])
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--task-id', type=int)
    args = parser.parse_args()
    if args.mode == 'reference':
        reference(args.manifest, args.output)
    else:
        run(args.manifest, args.task_id, args.output)
