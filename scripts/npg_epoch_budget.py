"""Frozen epoch-budget pilot; all numerical work runs on Slurm compute nodes."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
from dense_scaling import system, evaluate, targets, eta, trunc, rng_for, atomic_json, require_compute
from npg_batched_collector import collect


def identity(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance(manifest):
    return dict(manifest_sha256=identity(manifest), source_sha256=identity(__file__),
                engine_sha256=identity(system.__code__.co_filename),
                collector_sha256=identity(collect.__code__.co_filename),
                slurm_job_id=os.environ['SLURM_JOB_ID'])


def load(manifest):
    config = json.loads(Path(manifest).read_text())
    assert config['methods'] == ['raw', 'truncated']
    assert config['stages'] == 128 and config['epoch_length'] == 16
    for final in config['final_batches']:
        geometric = config['schedules'][f'geometric-{final}']
        flat = config['schedules'][f'constant-{final}']
        assert len(geometric) == len(flat) == config['stages']
        assert sum(geometric) == sum(flat)
        assert geometric[-1] == final and len(set(flat)) == 1
        assert all(n >= config['minimum_batch'] and n % 256 == 0 for n in geometric + flat)
    return config


def specification(task):
    return {key:task[key] for key in ('n','m','r','system_seed','trial_seed','family','tail','tail_shape','stabilizer')}


def reference(manifest, output):
    config = load(manifest)
    specs = {json.dumps(specification(task), sort_keys=True): specification(task) for task in config['tasks']}
    records = []
    for spec in specs.values():
        s = system(spec)
        step = config['step_multiplier']*eta(s)
        for finite in (False, True):
            k = s['K0'].copy()
            for stage in range(config['stages']+1):
                quality, p = evaluate(s,k)
                assert quality['stable']
                records.append(dict(**spec, stage=stage, finite_horizon=finite, eta=step, **quality))
                if stage < config['stages']:
                    true = targets(s,k,config['horizon'],p)
                    k -= step*(s['R']@k+true['ZH' if finite else 'Z'])
    atomic_json(Path(output)/'reference.json', dict(records=records, **provenance(manifest)))
    print(json.dumps(dict(reference='PASS', systems=len(specs))), flush=True)


def verify(manifest, output):
    config = load(manifest)
    from npg_precision_audit import verify as verify_identities
    from npg_batched_collector import verify as verify_collector
    verify_identities()
    verify_collector()
    for rank in (1,4):
        spec = specification(next(task for task in config['tasks'] if task['r'] == rank))
        s = system(spec)
        k = s['K0'].copy()
        step = config['step_multiplier']*eta(s)
        for _ in range(4):
            quality,p = evaluate(s,k)
            true = targets(s,k,config['horizon'],p)
            direct = k-step*(s['R']@k+true['Z'])
            low_rank = k-step*(s['R']@k+trunc(true['Z'],rank))
            assert np.allclose(direct,low_rank,rtol=1e-10,atol=1e-11)
            k = direct
    atomic_json(Path(output)/'verification.json',dict(status='PASS',
        tests=['equal total budgets','frozen schedules and NPG-only methods','pulse critic identities',
               'continuous batched collector equivalence','rank truncation preserves exact RK update'],
        **provenance(manifest)))
    print('EPOCH_BUDGET_VERIFICATION_PASS',flush=True)


def run(manifest, task_id, output):
    config = load(manifest)
    task = config['tasks'][task_id]
    s = system(specification(task))
    schedule = config['schedules'][task['schedule_id']]
    step = config['step_multiplier']*eta(s)
    planned = sum(config['burn']+(count+1)*config['horizon'] for count in schedule)
    records = []
    start = time.monotonic()
    for method in config['methods']:
        k,x,total = s['K0'].copy(),np.zeros(task['n']),0
        quality,p = evaluate(s,k)
        records.append(dict(method=method,stage=0,N=0,transitions=0,observed=True,**quality))
        failed = False
        for stage,count in enumerate(schedule,1):
            if failed:
                records.append(dict(method=method,stage=stage,N=count,transitions=total,
                                    observed=False,stable=False,gap=None))
                continue
            # These truth-based diagnostics never select a count, step, or update.
            before = quality['gap']
            true = targets(s,k,config['horizon'],p)
            residual = s['R']@k+true['Z']
            _,x,raw,_,gram,used = next(collect(s,k,x,[count],config['horizon'],config['sigma'],
                rng_for(882731,task['n'],task['system_seed'],task['trial_seed'],stage-1),burn=config['burn']))
            assert used == config['burn']+(count+1)*config['horizon']
            total += used
            z = raw if method == 'raw' else trunc(raw,task['r'])
            error = z-true['Z']
            direction = s['R']@k+z
            k -= step*direction
            quality,p = evaluate(s,k)
            row = dict(method=method,stage=stage,N=count,transitions=total,observed=True,
                before_gap=before,eta=step,critic_error_fro2=float(np.sum(error**2)),
                critic_error_op=float(np.linalg.norm(error,2)),residual_fro2=float(np.sum(residual**2)),
                horizon_bias_fro2=float(np.sum((true['ZH']-true['Z'])**2)),
                direction_cosine=float(np.sum(direction*residual)/max(np.linalg.norm(direction)*np.linalg.norm(residual),1e-30)),
                gram_condition=float(np.linalg.cond(gram)),elapsed_seconds=time.monotonic()-start,**quality)
            records.append(row)
            failed = not quality['stable']
            if stage % config['epoch_length'] == 0 or failed:
                payload = dict(task=task,records=records,diagnostics=s['diagnostics'],
                               planned_total_transitions=planned,**provenance(manifest))
                atomic_json(Path(output)/'raw'/f'progress-{task_id:03d}.json',payload)
                print(json.dumps(dict(task_id=task_id,**row)),flush=True)
        if not failed:
            assert total == planned
    atomic_json(Path(output)/'raw'/f'task-{task_id:03d}.json',
        dict(task=task,records=records,diagnostics=s['diagnostics'],
             planned_total_transitions=planned,**provenance(manifest)))


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode',choices=['verify','reference','run'])
    parser.add_argument('--manifest',required=True); parser.add_argument('--output',required=True)
    parser.add_argument('--task-id',type=int,default=0)
    args = parser.parse_args()
    if args.mode == 'run':run(args.manifest,args.task_id,args.output)
    else:globals()[args.mode](args.manifest,args.output)
