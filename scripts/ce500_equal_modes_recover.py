"""One bounded resume per interrupted task, using the unchanged frozen learner."""
import argparse
import json
import os
from pathlib import Path
import shutil
import time

import ce500_equal_modes as family
import ce500_matched_gap as run
import rank_sweep100 as e
import numpy as np
from threadpoolctl import threadpool_limits


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    cfg=e.read(a.manifest);out=Path(cfg['output']);ident=family.identity(cfg)
    task=int(os.environ['SLURM_ARRAY_TASK_ID']);plan=e.read(a.plan)
    case=next(c for c in plan['cases'] if c['task']==task)
    rank,seed=case['rank'],case['seed'];stem=f'ce-r{rank:03d}-s{seed:04d}'
    destination=out/'recovery-receipts'/(stem+'.json')
    assert not destination.exists(),'One resume per task; inspect receipts before any retry'
    cp=out/'checkpoints'/(stem+'.npz');budgets=e.read(out/'formal_plan.json')['budgets_by_rank'][str(rank)]
    assert e.sha(cp)==case['checkpoint_sha256']
    backup=out/'recovery-checkpoints'/(stem+'.npz');backup.parent.mkdir(exist_ok=True)
    assert not backup.exists();shutil.copyfile(cp,backup)
    with np.load(cp,allow_pickle=False) as arr:
        meta=json.loads(str(arr['meta']));assert meta['identity']==ident and meta['done']==case['done']
        gram=arr['gram'].copy();cross=arr['cross'].copy()
    oldrows=meta['rows'];assert all(e.sha(out/q['policy_file'])==q['policy_sha256'] for q in oldrows)
    receipt=dict(case,status='started',original_rows=oldrows,source_sha256=e.sha(Path(__file__)),
                 recovery_job=os.environ['SLURM_JOB_ID'],initial_rng_states={k:meta[k] for k in ('pulse_rng','noise_rng')},
                 backup_checkpoint=str(backup.relative_to(out)),burn_repeated=False,started_epoch=time.time())
    e.atomic_json(destination,receipt)
    with threadpool_limits(1):
        if meta['done']==budgets[-1] and not (out/'estimates'/(stem+'.npz')).exists():
            theta=run.cho_solve(run.cho_factor((gram+gram.T)/2),cross.T).T
            e.save_npz(out/'estimates'/(stem+'.npz'),Ahat=theta[:,:cfg['n']],Bhat=theta[:,cfg['n']:])
        run.task(cfg,ident,rank,seed,budgets)
    raw=e.read(out/'raw'/(stem+'.json'));assert raw['records'][:len(oldrows)]==oldrows
    assert raw['identity']==ident and raw['budgets']==budgets
    receipt.update(status='complete',new_committed_transitions=budgets[-1]-meta['done'],
                   prior_rows_and_policy_hashes_preserved=True,finished_epoch=time.time())
    e.atomic_json(destination,receipt);print(json.dumps({k:v for k,v in receipt.items() if k not in ('original_rows','initial_rng_states')},indent=2))


if __name__=='__main__':main()
