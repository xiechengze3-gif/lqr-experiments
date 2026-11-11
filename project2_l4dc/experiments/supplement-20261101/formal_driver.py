"""Audited X1 bundle driver. Requires an explicit local-review acceptance receipt."""
import argparse, json, os, time
from pathlib import Path
import numpy as np
import engine as e

def execute(s,spec,config,algorithm,path):
    # Capture every assessed candidate, including unstable candidates, without
    # changing any observations, learner decisions, RNG calls or evaluator result.
    assert not path.exists(),'No uncommitted learning replay'
    original=e.assess;matrices={};calls=[]
    def audited(plant,gain):
        identity=str(len(calls));q=original(plant,gain)
        matrices['K_'+identity]=gain.copy();calls.append(dict(assessment_id=identity,**q))
        return dict(q,assessment_id=identity)
    e.assess=audited
    try:
        data=e.ce_run(s,spec,config,path) if algorithm=='CE' else e.actor_run(s,spec,config,algorithm,path)
    finally:e.assess=original
    audit_path=path.with_name(path.stem+'.audit.npz')
    np.savez_compressed(audit_path,A=s['A'],B=s['B'],K0=s['K0'],**matrices)
    e.save(path.with_name(path.stem+'.audit.json'),dict(spec=spec,algorithm=algorithm,
      candidate_archive_sha256=e.sha(audit_path),calls=calls,engine_sha256=e.sha(e.__file__),driver_sha256=e.sha(__file__),job=os.environ['SLURM_JOB_ID']))
    return data

def main():
    e.require_compute();p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True)
    p.add_argument('--approval',type=Path,required=True);p.add_argument('--bundle',type=int,required=True);a=p.parse_args()
    config=json.loads(a.config.read_text());approval=json.loads(a.approval.read_text())
    assert approval['decision']=='ACCEPTED' and approval['experiment']=='X1'
    assert approval['resolved_config_sha256']==e.sha(a.config)
    assert approval['engine_sha256']==e.sha(e.__file__) and approval['driver_sha256']==e.sha(__file__)
    pairs=[(s,t) for s in config['formal_systems'] for t in config['formal_trials']]
    system,trial=pairs[a.bundle];out=e.OUT/'X1/formal';out.mkdir(parents=True,exist_ok=True)
    begun=time.monotonic();items=[]
    for null in (0.,.25):
        for m in config['ms']:
            if m==2 and null!=0:continue  # Exact same baseline, not new replication.
            s=e.plant(12,m,2,system,null_scale=null)
            spec=dict(experiment='X1',n=12,m=m,r=2,system=system,trial=trial,null_scale=null)
            stem=f's{system}-t{trial}-m{m}-null{int(null*100)}'
            for algorithm in ('CE','NPG','PI'):
                path=out/algorithm/(stem+'.json');path.parent.mkdir(parents=True,exist_ok=True)
                data=execute(s,spec,config,algorithm,path)
                items.append(dict(path=str(path),seconds=data['seconds'],sha256=e.sha(path)))
                print(json.dumps({'id':stem,'algorithm':algorithm,'seconds':data['seconds']}),flush=True)
    e.save(e.OUT/'X1/bundles'/f'bundle-{a.bundle:03d}.json',dict(status='COMPLETE',system=system,trial=trial,items=items,
      seconds=time.monotonic()-begun,config_sha256=e.sha(a.config),approval=approval,job=os.environ['SLURM_JOB_ID']))

if __name__=='__main__':main()
