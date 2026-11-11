"""Prepared formal dispatcher. No job is authorized before FORMAL acceptance.

Loads the exact frozen X6a S plant for each ID, so every arm/rung/algorithm
shares identical model bytes even across nodes. Only simulation/evaluation uses
truth; actor_learner receives the frozen observation-only inputs.
"""
import argparse
import json
import os
import time
from pathlib import Path
import numpy as np
import frozen_engine as e
import actor_paths as actor


def main():
    e.require_compute()
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--group',required=True);parser.add_argument('--index',required=True,type=int)
    parser.add_argument('--out',required=True,type=Path);a=parser.parse_args()
    allowed=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101/X6b')
    assert a.out.resolve().is_relative_to(allowed)
    config=json.loads(a.config.read_text(encoding='utf-8-sig'))
    assert config['status']=='FORMAL_FROZEN' and config['family']=='S'
    assert config['eta']==.2 and config['selected_NPG_T']==16 and config['selected_PI_T']==8
    group=next(g for g in config['formal_groups'] if g['id']==a.group)
    assert 0<=a.index<32
    system=config['formal_systems'][a.index//4];seed=config['formal_sampling_seeds'][a.index%4]
    n=group['n'];meta=config['model_registry'][f'n{n}-s{system}']
    model=a.config.parent/meta['path'];assert e.sha(model)==meta['sha256']
    with np.load(model) as archive:s={key:archive[key].copy() for key in archive.files}
    s['certificate']=meta['certificate']
    assert s['A'].shape==(n,n) and s['B'].shape==(n,n) and s['basis'].shape==(n,2)
    dest=a.out/a.group/('task-'+str(a.index));assert not dest.exists()
    dest.mkdir(parents=True);start=time.monotonic()
    base=dict(experiment='X6b',n=n,m=n,r=2,system=system,seed=seed)
    header=dict(group=group,index=a.index,spec=base,model=meta,job=os.environ['SLURM_JOB_ID'],
        config_sha256=e.sha(a.config),source_sha256=e.sha(__file__),actor_sha256=e.sha(actor.__file__),
        engine_sha256=e.sha(e.__file__))
    e.save(dest/'BEGIN.json',header);completed=[]
    try:
        for run in group['runs']:
            entry=next(x for x in config['all_schedules'] if x['n']==n and x['rung']==run['rung'])
            expected=entry['primitive_per_arm_per_algorithm']
            assert 16*(sum(entry['batches']['NPG'])+17*16)==expected
            assert 16*(sum(entry['batches']['PI'])+17*8)==expected
            stage_config=dict(H=16,nu=1.,burn_blocks=16,eta=.2,schedules=entry['batches'])
            spec=dict(base,rung=run['rung'],rung_label=run['rung_label'])
            path=dest/(run['algorithm']+'-'+run['rung_label'])
            result=actor.run(s,spec,stage_config,run['algorithm'],path)
            assert result['primitive_transitions']==dict(dense=expected,truncated=expected)
            completed.append(dict(algorithm=run['algorithm'],rung=run['rung'],
                path=path.name,done_sha256=e.sha(path/'DONE.json'),primitive_per_arm=expected,
                final_stable={arm:next(r['stable'] for r in reversed(result['records']) if r['arm']==arm)
                              for arm in ['dense','truncated']}))
    except Exception as exc:
        e.save(dest/'HARD_FAILURE.json',dict(header,completed_paths=completed,error=repr(exc),
            partial_path_transitions='See complete-stage checkpoints; no invented partial count',
            automatic_retry=False))
        raise
    e.save(dest/'DONE.json',dict(status='COMPLETE',**header,paths=completed,seconds=time.monotonic()-start))
    print(json.dumps(dict(status='COMPLETE',group=a.group,index=a.index,paths=len(completed),
                         seconds=time.monotonic()-start)),flush=True)


if __name__=='__main__':main()
