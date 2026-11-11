"""Draft resource-only actor benchmarks and frozen-engine equivalence.

No gaps, rho_op, projection, rank-error or arm-performance readouts are printed
or used for hyperparameter selection. Population R2 has its own accepted job.
"""
import argparse
import json
import os
import resource
import time
from pathlib import Path
import numpy as np
import frozen_engine as e
import estimation
import actor_paths as actor

BASE=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101/X6b')


def equivalence(out):
    s=estimation.model('S',24,9101);checks=[]
    config=dict(H=16,nu=1.,burn_blocks=16,eta=.2,
                npg_batches=[256,512],pi_batches=[256,512],
                schedules=dict(NPG=[256,512],PI=[256,512]))
    spec=dict(experiment='X6b',n=24,m=24,r=2,system=9101,seed=9802,trial=9802)
    original=e.assess
    for algorithm in ['NPG','PI']:
        gains=[]
        def capture(s,k):gains.append(k.copy());return original(s,k)
        e.assess=capture
        try:reference=e.actor_run(s,spec,config,algorithm,out/(algorithm+'-reference.json'))
        finally:e.assess=original
        expected=[k.copy() for k in gains];gains.clear();e.assess=capture
        try:actual=actor.run(s,spec,config,algorithm,out/(algorithm+'-new'))
        finally:e.assess=original
        assert len(expected)==len(gains) and all(np.array_equal(x,y) for x,y in zip(expected,gains))
        assert reference['actual_transitions']==actual['primitive_transitions']
        assert len(reference['records'])==len(actual['records'])
        for ref,new in zip(reference['records'],actual['records']):
            assert ref['stable']==new['stable'] and ref['gap']==new['gap']
            assert ref['relative_gap']==new['relative_gap']
            assert ref['mode']==new['arm'] and ref['stage']==new['stage']
            assert ref['transitions']==new['primitive_transitions']
        checks.append(dict(algorithm=algorithm,status='PASS_BITWISE_GAINS_AND_COUNTS',
                           actual_primitive_transitions=actual['primitive_transitions']))
    e.save(out/'equivalence.json',dict(status='PASS',checks=checks,
        source_sha256=e.sha(__file__),actor_sha256=e.sha(actor.__file__)))


def timing(n,config,out):
    s=estimation.model('S',n,9102);rows=[]
    begin=time.monotonic()
    e.collect(s,s['K0'],np.zeros(n),256,e.rng(681,n,9102,9803),config)
    warmup_seconds=time.monotonic()-begin
    for rung_index,rung in enumerate(config['rungs']):
        schedules=actor.schedules(config['npg_bases'][str(n)],rung,
                                  config['selected_NPG_T'],config['selected_PI_T'])
        for algorithm in ['NPG','PI']:
            count=max(schedules[algorithm]);clock=time.monotonic()
            x,g,z=e.collect(s,s['K0'],np.zeros(n),count,
                e.rng(680,n,9102,9801,rung_index,0 if algorithm=='NPG' else 1),config)
            collect_seconds=time.monotonic()-clock
            for arm in ['dense','truncated']:
                begin=time.monotonic()
                candidate=e.actor_learner(s['K0'],s['R'],g,z,arm,2,algorithm,config['eta'])
                update_seconds=time.monotonic()-begin
                assert np.isfinite(candidate).all() and np.isfinite(g).all() and np.isfinite(z).all()
                begin=time.monotonic();path=out/(algorithm+'-'+str(rung_index)+'-'+arm+'.npz')
                np.savez_compressed(path,Ghat=g,Zhat=z,K=candidate,x=x)
                write_seconds=time.monotonic()-begin
                rows.append(dict(n=n,rung=rung,algorithm=algorithm,arm=arm,max_stage_blocks=count,
                    primitive_transitions=(count+17)*16,collector_seconds=collect_seconds,
                    update_seconds=update_seconds,artifact_write_seconds=write_seconds,
                    max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    e.save(out/'timing.json',dict(status='COMPLETE_RESOURCE_ONLY',rows=rows,
        warmup_seconds=warmup_seconds,warmup_primitive_transitions=(256+17)*16,
        source_sha256=e.sha(__file__),actor_sha256=e.sha(actor.__file__),job=os.environ['SLURM_JOB_ID'],
        note='One collector per algorithm/rung; formal paired cost has two collectors plus two updates. No performance readout.'))


if __name__=='__main__':
    e.require_compute();p=argparse.ArgumentParser()
    p.add_argument('--config',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--n',type=int);a=p.parse_args()
    assert a.out.resolve().is_relative_to(BASE) and not a.out.exists()
    a.out.mkdir(parents=True);config=json.loads(a.config.read_text(encoding='utf-8-sig'))
    if a.n is None:equivalence(a.out)
    else:timing(a.n,config,a.out)
