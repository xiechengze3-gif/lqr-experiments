"""Accepted and dense-qualified NPG formal suite; exact paired transition counts."""
import argparse,json,os,time
from pathlib import Path
import engine as e
import npg_multi

def main():
    e.require_compute();p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--bundle',type=int,required=True);a=p.parse_args()
    cfg=json.loads(a.config.read_text());exp=cfg['experiment'];assert cfg['phase']=='FORMAL'
    approval=json.loads((Path(__file__).parent/exp/'ACCEPTED_NPG.json').read_text())
    assert approval['decision']=='ACCEPTED_CONDITIONS_SATISFIED' and approval['config_sha256']==e.sha(a.config)
    assert approval['engine_sha256']==e.sha(e.__file__) and approval['multi_source_sha256']==e.sha(npg_multi.__file__)
    pairs=[(s,t) for s in cfg['formal_systems'] for t in cfg['formal_trials']];system,trial=pairs[a.bundle]
    start=time.monotonic();items=[]
    for case in cfg['cases']:
        n,r,sp=case['n'],case['r'],case['spectrum'];null=.25 if exp=='X2' else 0.
        for multiplier in cfg['budget_multipliers']:
            s=e.plant(n,n,r,system,spectrum=sp,null_scale=null)
            spec=dict(experiment=exp,n=n,m=n,r=r,system=system,trial=trial,spectrum=sp,null_scale=null,
                 base=cfg['base'],budget_multiplier=multiplier)
            resolved=dict(cfg,eta=case['eta'],npg_batches=[multiplier*b for b in case['npg_batches']])
            path=e.OUT/exp/'formal/NPG'/f'n{n}-{sp}-b{multiplier}-s{system}-t{trial}.json'
            try:
                d=npg_multi.execute(s,spec,resolved,[r] if exp=='X2' else [1,2,4,6,12],path)
                status=d['status'];error=None
            except Exception as exc:
                status='FAILED_NO_REPLAY';error=repr(exc)
                assert path.exists(), 'No result receipt; do not continue an unknown attempt'
                d=json.loads(path.read_text())
            item=dict(path=str(path),sha256=e.sha(path),seconds=d['seconds'],status=status,error=error,
                      actual_transitions=d['actual_transitions'],planned_transitions_per_arm=d['planned_transitions_per_arm'])
            items.append(item);print(json.dumps(item),flush=True)
    e.save(e.OUT/exp/'formal-npg-bundles'/f'bundle-{a.bundle:03d}.json',dict(status='COMPLETE_ATTEMPTS',items=items,
      failed_attempts=sum(x['status']!='COMPLETE' for x in items),seconds=time.monotonic()-start,
      config_sha256=e.sha(a.config),approval=approval,job=os.environ['SLURM_JOB_ID']))

if __name__=='__main__':main()
