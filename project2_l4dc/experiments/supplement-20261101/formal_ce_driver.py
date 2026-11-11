"""X1 CE-only formal driver; explicitly excludes all actor learning."""
import argparse,json,os,time
from pathlib import Path
import engine as e
from formal_driver import execute

def main():
    e.require_compute();p=argparse.ArgumentParser();p.add_argument('--bundle',type=int,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent;config=json.loads((root/'configs/X1_v1.json').read_text())
    approval=json.loads((root/'X1/ACCEPTED_CE.json').read_text())
    assert approval['decision']=='ACCEPTED' and approval['scope']=='CE_ONLY'
    assert approval['engine_sha256']==e.sha(e.__file__)
    assert approval['config_sha256']==e.sha(root/'configs/X1_v1.json')
    pairs=[(s,t) for s in config['formal_systems'] for t in config['formal_trials']]
    system,trial=pairs[a.bundle];dest=e.OUT/'X1/formal/CE';dest.mkdir(parents=True,exist_ok=True);items=[];begin=time.monotonic()
    for null in (0.,.25):
        for m in config['ms']:
            if null!=0 and m==2:continue
            spec=dict(experiment='X1',n=12,m=m,r=2,system=system,trial=trial,null_scale=null)
            path=dest/f's{system}-t{trial}-m{m}-null{int(null*100)}.json'
            data=execute(e.plant(12,m,2,system,null_scale=null),spec,config,'CE',path)
            items.append(dict(path=str(path),sha256=e.sha(path),seconds=data['seconds']))
    e.save(e.OUT/'X1/ce_bundles'/f'bundle-{a.bundle:03d}.json',dict(status='COMPLETE',items=items,
      seconds=time.monotonic()-begin,job=os.environ['SLURM_JOB_ID'],approval=approval))
    print(json.dumps({'bundle':a.bundle,'status':'COMPLETE','CE_trajectories':len(items),'seconds':time.monotonic()-begin}))

if __name__=='__main__':main()
