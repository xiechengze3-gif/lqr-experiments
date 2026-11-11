"""Finite-data dense-only base qualification; disjoint pilot systems/seeds."""
import argparse,json,os,time
from pathlib import Path
import engine as e
import npg_multi

def main():
    e.require_compute();p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);p.add_argument('--bundle',required=True,type=int);a=p.parse_args()
    cfg=json.loads(a.config.read_text());exp=cfg['experiment'];assert cfg['phase']=='PILOT'
    proof=json.loads((e.OUT/'budget/NPG_resource_pilot_v1.json').read_text())
    assert proof['status']=='COMPLETE' and proof['equivalence']['status']=='PASS_BITWISE'
    assert proof['engine_sha256']==e.sha(e.__file__) and proof['multi_source_sha256']==e.sha(npg_multi.__file__)
    pairs=[(s,t) for s in cfg['pilot_systems'] for t in cfg['pilot_trials']];system,trial=pairs[a.bundle]
    start=time.monotonic();items=[]
    for case in cfg['cases']:
        n,rank,sp=case['n'],case['r'],case['spectrum'];null=.25 if exp=='X2' else 0.
        s=e.plant(n,n,rank,system,spectrum=sp,null_scale=null)
        spec=dict(experiment=exp,n=n,m=n,r=rank,system=system,trial=trial,spectrum=sp,null_scale=null,base=cfg['base'])
        resolved=dict(cfg,eta=case['eta'],npg_batches=case['npg_batches'])
        path=e.OUT/exp/f'pilot-npg-base{cfg["base"]}'/f'n{n}-{sp}-s{system}-t{trial}.json'
        result=npg_multi.execute(s,spec,resolved,[],path)
        items.append(dict(path=str(path),sha256=e.sha(path),seconds=result['seconds'],endpoint=result['records'][-1]))
        print(json.dumps(items[-1]),flush=True)
    e.save(e.OUT/exp/f'pilot-npg-base{cfg["base"]}-bundles'/f'{cfg["label"]}-{a.bundle:03d}.json',dict(status='COMPLETE',items=items,
      seconds=time.monotonic()-start,config_sha256=e.sha(a.config),job=os.environ['SLURM_JOB_ID']))

if __name__=='__main__':main()
