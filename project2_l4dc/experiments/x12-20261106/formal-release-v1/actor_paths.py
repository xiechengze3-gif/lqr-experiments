"""Draft X6b paired actor with raw-estimate/stage checkpoints.

Core updates/collection call the unchanged engine. No simulator diagnostic is
an input to the learner; stability is only absorbing failure recording.
"""
from __future__ import annotations
import json
import math
import os
import time
from pathlib import Path
import numpy as np
import frozen_engine as e


def schedules(base,rung,npg_T,pi_T):
    npg=[math.ceil(base*rung*2**(t/16)) for t in range(npg_T)]
    budget=sum(npg)+17*(npg_T-pi_T)
    weights=[2**(4*t/pi_T) for t in range(pi_T)]
    desired=[budget*w/sum(weights) for w in weights]
    pi=[math.floor(v) for v in desired]
    order=sorted(range(pi_T),key=lambda t:(-(desired[t]-pi[t]),t))
    remainder=budget-sum(pi);assert 0<=remainder<=pi_T
    for t in order[:remainder]:pi[t]+=1
    assert min(npg)>0 and min(pi)>0
    assert sum(npg)+17*npg_T==sum(pi)+17*pi_T
    return dict(NPG=npg,PI=pi)


def save_npz(path,**values):
    temp=path.with_suffix('.tmp.npz')
    assert not path.exists() and not temp.exists()
    np.savez_compressed(temp,**values);temp.replace(path)


def run(s,spec,config,algorithm,destination):
    e.require_compute()
    start=time.monotonic();n,m=s['B'].shape
    allowed=Path('/scratch/user/changze/lqr_experiments/results/x12-20261106')
    assert destination.resolve().is_relative_to(allowed) and not destination.exists()
    destination.mkdir(parents=True)
    arms=['dense','truncated'];states={a:np.zeros(n) for a in arms}
    gains={a:s['K0'].copy() for a in arms};dead={a:False for a in arms}
    totals={a:0 for a in arms};padding={a:0 for a in arms};records=[];artifacts=[]
    schedule=config['schedules'][algorithm]
    for arm in arms:
        records.append(dict(spec,algorithm=algorithm,arm=arm,stage=0,primitive_transitions=0,
            padding_transitions=0,**e.assess(s,gains[arm])))
    for stage,count in enumerate(schedule,1):
        stage_counts={}
        for arm in arms:
            was_dead=dead[arm]
            before=gains[arm].copy();behavior=s['K0'] if was_dead else before
            random=e.rng(20 if algorithm=='NPG' else 21,n,m,spec['system'],spec['seed'],stage)
            states[arm],g,z=e.collect(s,behavior,states[arm],count,random,config)
            used=(count+config['burn_blocks']+1)*config['H'];totals[arm]+=used
            if was_dead:
                padding[arm]+=used
                result=dict(stable=False,gap=None,relative_gap=None,rho=None,
                            failure='absorbing_failure_budget_padding')
            else:
                gains[arm]=e.actor_learner(before,s['R'],g,z,arm,2,algorithm,config['eta'])
                result=e.assess(s,gains[arm]);dead[arm]=not result['stable']
            row=dict(spec,algorithm=algorithm,arm=arm,stage=stage,N=count,
                primitive_transitions=totals[arm],padding_transitions=padding[arm],
                padding_stage=was_dead,**result)
            records.append(row)
            path=destination/f'stage-{stage:03d}-{arm}.npz'
            save_npz(path,K_before=before,behavior=behavior,K_after=gains[arm],
                     Ghat=g,Zhat=z,x_after=states[arm])
            artifacts.append(dict(path=path.name,sha256=e.sha(path),
                rng_state=random.bit_generator.state,stage=stage,arm=arm,padding_stage=was_dead))
            stage_counts[arm]=used
        assert totals['dense']==totals['truncated'] and len(stage_counts)==2
        checkpoint=destination/f'checkpoint-{stage:03d}.npz'
        save_npz(checkpoint,**{'K_'+a:gains[a] for a in arms},
                 **{'x_'+a:states[a] for a in arms})
        e.save(destination/f'checkpoint-{stage:03d}.json',dict(status='COMPLETE_STAGE',
            stage=stage,dead=dead.copy(),total_primitive_transitions=totals.copy(),
            padding_transitions=padding.copy(),checkpoint_sha256=e.sha(checkpoint),
            source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),
            spec=spec,config=config,records=records.copy(),artifacts=artifacts.copy()))
    data=dict(status='COMPLETE',spec=spec,algorithm=algorithm,records=records,artifacts=artifacts,
        primitive_transitions=totals,padding_transitions=padding,seconds=time.monotonic()-start,
        source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),
        job=os.environ['SLURM_JOB_ID'])
    e.save(destination/'DONE.json',data)
    return data
