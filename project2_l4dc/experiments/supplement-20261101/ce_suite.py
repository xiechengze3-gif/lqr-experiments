"""General single-trajectory CE suite; case-specific grids, no actor formal shortcut."""
import argparse,json,os,time
from pathlib import Path
import engine as e
from formal_driver import execute

def main():
    e.require_compute();p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--phase',choices=['pilot','formal'],required=True);p.add_argument('--bundle',type=int,required=True);a=p.parse_args()
    cfg=json.loads(a.config.read_text());exp=cfg['experiment'];phase=a.phase
    if phase=='formal':
        ap=json.loads((Path(__file__).parent/exp/'ACCEPTED_CE.json').read_text())
        assert ap['decision']=='ACCEPTED' and ap['experiment']==exp and ap['scope']=='CE_ONLY'
        assert ap['engine_sha256']==e.sha(e.__file__) and ap['config_sha256']==e.sha(a.config)
    pairs=[(s,t) for s in cfg[phase+'_systems'] for t in cfg[phase+'_trials']]
    system,trial=pairs[a.bundle];begin=time.monotonic();items=[]
    for case in cfg['ce_cases']:
        n,r=case['n'],case['r'];m=case.get('m',n);spectrum=case.get('spectrum','exact');null=case.get('null_scale',.25)
        spec=dict(experiment=exp,n=n,m=m,r=r,system=system,trial=trial,spectrum=spectrum,null_scale=null)
        resolved=dict(cfg,ce_prefixes=case['prefixes'])
        if 'fixed_ranks' in case:resolved['fixed_ranks']=case['fixed_ranks']
        stem=f'n{n}-r{r}-{spectrum}-s{system}-t{trial}'
        path=e.OUT/exp/phase/'CE'/(stem+'.json');path.parent.mkdir(parents=True,exist_ok=True)
        data=execute(e.plant(n,m,r,system,spectrum=spectrum,null_scale=null),spec,resolved,'CE',path)
        items.append(dict(path=str(path),seconds=data['seconds'],sha256=e.sha(path),n=n,r=r,spectrum=spectrum))
        print(json.dumps(items[-1]),flush=True)
    e.save(e.OUT/exp/(phase+'-ce-bundles')/f'bundle-{a.bundle:03d}.json',dict(status='COMPLETE',items=items,seconds=time.monotonic()-begin,
      job=os.environ['SLURM_JOB_ID'],config_sha256=e.sha(a.config),phase=phase))

if __name__=='__main__':main()
