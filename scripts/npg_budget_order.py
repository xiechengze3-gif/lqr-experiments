"""NPG total-transition versus precision/rank study, Slurm compute only."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import numpy as np
from dense_scaling import evaluate, targets, eta, trunc, rng_for, atomic_json, require_compute, pulse_moments
from npg_batched_collector import collect
from npg_budget_system import system


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance(manifest):
    return dict(manifest_sha256=digest(manifest),source_sha256=digest(__file__),
        system_sha256=digest(system.__code__.co_filename),
        engine_sha256=digest(evaluate.__code__.co_filename),
        collector_sha256=digest(collect.__code__.co_filename),
        slurm_job_id=os.environ['SLURM_JOB_ID'])


def load(manifest):
    config = json.loads(Path(manifest).read_text())
    assert config['methods'] == ['raw','truncated']
    assert config['ranks'][-1] == config['n']
    assert config['stages'] % config['epoch_length'] == 0
    for name,schedule in config['schedules'].items():
        profile=config['profiles'][name]
        assert len(schedule) == config['stages'] and schedule[-1] == profile['final_batch']
        assert all(count>=profile['minimum_batch'] and count%256==0 for count in schedule)
        assert schedule == sorted(schedule)
    return config


def specification(task):
    return {key:task[key] for key in ('n','m','r','system_seed','trial_seed')}


def verify(manifest, output):
    config = load(manifest)
    from npg_precision_audit import verify as verify_identities
    verify_identities()
    systems,reference,checks = [],[],[]
    smallest = min(config['tolerances'])
    for seed in config['system_seeds']:
        common = None
        previous_b = None
        for rank in config['ranks']:
            task = dict(n=config['n'],m=config['n'],r=rank,system_seed=seed,trial_seed=0)
            s = system(task)
            assert all(d>.999 for d in s['diagnostics']['density'].values())
            hashes = {name:s['diagnostics']['hashes'][name] for name in ('A','Q','R','K0')}
            if common is None: common = hashes
            else: assert common == hashes
            singular = np.linalg.svd(s['B'],compute_uv=False)
            np.testing.assert_allclose(singular[:rank],1.2,rtol=1e-12,atol=1e-12)
            np.testing.assert_allclose(singular[rank:],0.,atol=1e-12)
            if previous_b is not None:
                # Nested orthogonal input/state factors, fixed strength per direction.
                np.testing.assert_allclose(previous_b.T@(s['B']-previous_b),0.,atol=1e-12)
            previous_b = s['B']
            step = config['step_multiplier']*eta(s)
            endpoint = {}
            for finite in (False,True):
                k = s['K0'].copy()
                for stage in range(config['stages']+1):
                    quality,p = evaluate(s,k)
                    assert quality['stable']
                    reference.append(dict(**task,stage=stage,finite_horizon=finite,eta=step,**quality))
                    if stage < config['stages']:
                        true = targets(s,k,config['horizon'],p)
                        z = true['ZH' if finite else 'Z']
                        np.testing.assert_allclose(trunc(z,rank),z,rtol=1e-9,atol=1e-10)
                        k -= step*(s['R']@k+z)
                endpoint[str(finite)] = quality['gap']
            assert max(endpoint.values()) < smallest/config['reference_margin'], (task,endpoint)
            assert abs(endpoint['True']-endpoint['False']) < smallest/50., (task,endpoint)
            systems.append(dict(**task,**s['diagnostics'],reference_endpoint=endpoint))
    # Check the actual new dense family with the sequential collector, too.
    for rank in (1,config['n']):
        task=dict(n=config['n'],m=config['n'],r=rank,system_seed=0,trial_seed=0)
        s=system(task); outputs=[]
        for collector in (pulse_moments,collect):
            outputs.append(list(collector(s,s['K0'],np.zeros(config['n']),[256,1024],
                config['horizon'],config['sigma'],rng_for(9423,rank),burn=config['burn'])))
        for old,new in zip(*outputs):
            assert old[0]==new[0] and old[-1]==new[-1]
            for index in (1,2,4):
                np.testing.assert_allclose(old[index],new[index],rtol=2e-10,atol=2e-10)
        checks.append(dict(rank=rank,continuous_collector='PASS'))
    atomic_json(Path(output)/'reference.json',dict(records=reference,systems=systems,**provenance(manifest)))
    atomic_json(Path(output)/'verification.json',dict(status='PASS',systems=len(systems),checks=checks,
        tests=['same dense A/Q/R/K0 across rank','nested B, constant nonzero singular values',
               'common stability/step bounds','all exact and finite-H references below target margin',
               'rank projection preserves exact RK update','new-family sequential/batched equivalence',
               'adjacent-return identities'],**provenance(manifest)))
    print(json.dumps(dict(verification='PASS',systems=len(systems))),flush=True)


def run(manifest, task_id, output):
    config=load(manifest);task=config['tasks'][task_id]
    s=system(specification(task));schedule=config['schedules'][task['schedule_id']]
    step=config['step_multiplier']*eta(s)
    planned=sum(config['burn']+(count+1)*config['horizon'] for count in schedule)
    records=[]; start=time.monotonic()
    for method in config['methods']:
        k=s['K0'].copy();x=np.zeros(task['n']);total=0
        quality,p=evaluate(s,k);failed=False
        records.append(dict(method=method,stage=0,N=0,transitions=0,observed=True,**quality))
        for stage,count in enumerate(schedule,1):
            if failed:
                records.append(dict(method=method,stage=stage,N=count,transitions=total,
                    observed=False,stable=False,gap=None))
                continue
            true=targets(s,k,config['horizon'],p); before=quality['gap']
            _,x,raw,_,gram,used=next(collect(s,k,x,[count],config['horizon'],config['sigma'],
                rng_for(663897,task['n'],task['system_seed'],task['trial_seed'],stage-1),burn=config['burn']))
            assert used==config['burn']+(count+1)*config['horizon'];total+=used
            z=raw if method=='raw' else trunc(raw,task['r'])
            error=z-true['Z']; k-=step*(s['R']@k+z)
            quality,p=evaluate(s,k)
            row=dict(method=method,stage=stage,N=count,transitions=total,observed=True,
                eta=step,before_gap=before,critic_error_fro2=float(np.sum(error*error)),
                horizon_bias_fro2=float(np.sum((true['ZH']-true['Z'])**2)),
                critic_error_op=float(np.linalg.norm(error,2)),
                gram_condition=float(np.linalg.cond(gram)),elapsed_seconds=time.monotonic()-start,**quality)
            records.append(row);failed=not quality['stable']
            if stage%config['epoch_length']==0 or failed:
                atomic_json(Path(output)/'raw'/f'progress-{task_id:03d}.json',
                    dict(task=task,records=records,diagnostics=s['diagnostics'],
                         planned_total_transitions=planned,**provenance(manifest)))
                print(json.dumps(dict(task_id=task_id,**row)),flush=True)
        if not failed:assert total==planned
    if task['r']==task['n']:
        raw=[row for row in records if row['method']=='raw']
        low=[row for row in records if row['method']=='truncated']
        assert all(a['stable']==b['stable'] for a,b in zip(raw,low))
        for a,b in zip(raw,low):
            if a['stable']:np.testing.assert_allclose(a['gap'],b['gap'],rtol=1e-7,atol=1e-8)
    atomic_json(Path(output)/'raw'/f'task-{task_id:03d}.json',
        dict(task=task,records=records,diagnostics=s['diagnostics'],
             planned_total_transitions=planned,**provenance(manifest)))


def smoke_check(manifest,output):
    config=load(manifest)
    for tid in config['smoke_ids']:
        data=json.loads((Path(output)/'raw'/f'task-{tid:03d}.json').read_text())
        assert data['manifest_sha256']==digest(manifest)
        assert len(data['records'])==2*(config['stages']+1)
        assert all(row['stable'] for row in data['records']),tid
    print('BUDGET_ORDER_SMOKE_PASS',flush=True)


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['verify','run','smoke_check'])
    p.add_argument('--manifest',required=True);p.add_argument('--output',required=True)
    p.add_argument('--task-id',type=int,default=0);a=p.parse_args()
    if a.mode=='run':run(a.manifest,a.task_id,a.output)
    else:globals()[a.mode](a.manifest,a.output)
