"""Observation-only multi-order NPG, independent continuous states and audited counts."""
import os,time
import numpy as np
import engine as e

def execute(s,spec,cfg,ranks,path):
    assert not path.exists(), 'No learning replay into an existing result'
    start=time.monotonic();n,m=s['B'].shape
    methods={'dense':min(n,m)}
    methods.update({f'k{k}':k for k in ranks if k<min(n,m)})
    states={mode:np.zeros(n) for mode in methods};policies={mode:s['K0'].copy() for mode in methods}
    dead={mode:False for mode in methods};counts={mode:0 for mode in methods};padding={mode:0 for mode in methods}
    independent_counts={mode:0 for mode in methods};rows=[];matrices={};active=None
    pulse_original=e.pulse_batch
    def counted(*args,**kwargs):
        value=pulse_original(*args,**kwargs)
        independent_counts[active]+=int(args[5].shape[0]*args[5].shape[1])
        return value
    def evaluated(mode,gain,stage):
        identity=str(len(matrices));matrices['K_'+identity]=gain.copy()
        return dict(spec,algorithm='NPG',mode=mode,k=methods[mode],stage=stage,
          transitions=counts[mode],padding_transitions=padding[mode],assessment_id=identity,**e.assess(s,gain))
    for mode in methods:rows.append(evaluated(mode,policies[mode],0))
    e.pulse_batch=counted
    try:
        for stage,batch in enumerate(cfg['npg_batches'],1):
            for mode,rank in methods.items():
                active=mode;behavior=s['K0'] if dead[mode] else policies[mode]
                random=e.rng(20,n,m,spec['system'],spec['trial'],stage)
                states[mode],g,z=e.collect(s,behavior,states[mode],batch,random,cfg)
                used=(cfg['burn_blocks']+1+batch)*cfg['H'];counts[mode]+=used
                if dead[mode]:
                    padding[mode]+=used
                    row=dict(spec,algorithm='NPG',mode=mode,k=rank,stage=stage,transitions=counts[mode],
                      padding_transitions=padding[mode],stable=False,gap=None,relative_gap=None,failure='absorbing_failure_budget_padding')
                else:
                    candidate=e.actor_learner(policies[mode],s['R'],g,z,'dense' if mode=='dense' else 'truncated',rank,'NPG',cfg['eta'])
                    row=evaluated(mode,candidate,stage);policies[mode]=candidate;dead[mode]=not row['stable']
                rows.append(row)
                assert counts[mode]==independent_counts[mode]
            assert len(set(counts.values()))==1
        status='COMPLETE';error=None
    except Exception as exc:
        status='FAILED_NO_REPLAY';error=repr(exc)
    finally:e.pulse_batch=pulse_original
    path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path.with_suffix('.npz'),A=s['A'],B=s['B'],K0=s['K0'],**matrices)
    data=dict(status=status,error=error,spec=spec,certificate=s['certificate'],records=rows,
      seconds=time.monotonic()-start,actual_transitions=counts,independently_counted_transitions=independent_counts,
      padding_transitions=padding,planned_transitions_per_arm=sum((cfg['burn_blocks']+1+b)*cfg['H'] for b in cfg['npg_batches']),
      candidate_archive_sha256=e.sha(path.with_suffix('.npz')),engine_sha256=e.sha(e.__file__),
      multi_source_sha256=e.sha(__file__),job=os.environ['SLURM_JOB_ID'])
    e.save(path,data)
    if status!='COMPLETE':raise RuntimeError('NPG multi-order failed; saved partial observations, no replay: '+error)
    return data
