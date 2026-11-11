"""Audited extension of a fixed sampling prefix; never relabel scientific results silently."""
import argparse
import json
import os
import shutil
from pathlib import Path
import numpy as np
import rank_sweep100 as e
import rank_sweep100_remote as remote


def migrate(cfg,manifest):
    out,ident=remote.bootstrap(cfg,manifest)
    old=Path(cfg['prefix_source_output']); old_cfg=e.read(old/'resolved_config.json')
    old_ident=e.read(old/'verification.json')['identity']
    # All numerical learner, model, sampling and seed fields are unchanged.
    allowed={'experiment','output','cache','temp','local_output','compute_budget','schedule_segments',
             'prefix_source_output','identity','epsilon'}
    left={k:v for k,v in old_cfg.items() if k not in allowed}
    right={k:v for k,v in cfg.items() if k not in allowed}
    assert left==right,(left.keys() ^ right.keys())
    old_schedule=e.schedule(old_cfg);new_schedule=e.schedule(cfg)
    assert new_schedule[:len(old_schedule)]==old_schedule and len(new_schedule)>len(old_schedule)
    assert old_ident['sources']==ident['sources'],'Learner/simulator sources must be unchanged'
    checks=[];reused_physical=0
    for seed in cfg['pilot_seeds']:
        for rank in cfg['ranks']:
            name=f'npg-r{rank:03d}-s{seed:04d}.npz'
            path=old/'checkpoints'/name
            with np.load(path,allow_pickle=False) as a:
                items={key:a[key].copy() for key in a.files}
            meta=json.loads(str(items['meta']));assert meta['identity']==old_ident
            assert meta['next_stage']==len(old_schedule)
            meta['identity']=ident
            items['meta']=json.dumps(meta)
            target=out/'checkpoints'/name
            assert not target.exists(),'Migration is a single explicitly recorded operation'
            e.save_npz(target,**items)
            reused_physical+=meta['physical']
            checks.append(dict(route='npg',rank=rank,seed=seed,reused_stages=len(old_schedule),
                               physical_transitions=meta['physical'],source_checkpoint_sha256=e.sha(path)))
    # CE has the identical complete OLS protocol, budgets, observations and policies.
    for seed in cfg['pilot_seeds']+cfg['confirm_seeds']:
        for rank in cfg['ranks']:
            name=f'ce-r{rank:03d}-s{seed:04d}.json';path=old/'raw'/name
            data=e.read(path);assert data['identity']==old_ident
            data['source_identity']=old_ident;data['identity']=ident
            data['reused_from']=str(path);data['source_json_sha256']=e.sha(path)
            source_policy=old/'policies'/Path(name).with_suffix('.npz').name
            assert e.sha(source_policy)==data['policy_sha256']
            target_policy=out/'policies'/source_policy.name;target_policy.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source_policy,target_policy)
            e.atomic_json(out/'raw'/name,data)
            reused_physical+=data['physical_transitions']
            checks.append(dict(route='ce',rank=rank,seed=seed,source_json_sha256=e.sha(path),
                               physical_transitions=data['physical_transitions']))
    result=dict(status='PASS',old_identity=old_ident,new_identity=ident,checks=checks,
                reused_physical_transitions=reused_physical,
                note='All old artifacts preserved. NPG resumes exact K/x/failed/rows/count states. CE observations and policies are unchanged.')
    e.atomic_json(out/'prefix_reuse.json',result)
    print(json.dumps(dict(status='PASS',checks=len(checks),reused_physical_transitions=reused_physical)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    migrate(e.read(a.manifest),a.manifest)
