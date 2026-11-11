"""X1 actor formal only, conditional acceptance plus successful R3 required."""
import argparse,json,os,time
from pathlib import Path
import numpy as np
import engine as e

def audited_actor(s,spec,cfg,alg,path):
    assert not path.exists();original_assess=e.assess;original_collect=e.collect;original_pulse=e.pulse_batch
    candidates={};evaluations=[];transitions={'dense':0,'truncated':0};context={'mode':None,'collect_calls':0};error=None;data=None
    def assess(plant,k):
        ident=str(len(evaluations));q=original_assess(plant,k);candidates['K_'+ident]=k.copy();evaluations.append(dict(assessment_id=ident,**q))
        return dict(q,assessment_id=ident)
    def pulse(*args,**kwargs):
        result=original_pulse(*args,**kwargs)
        transitions[context['mode']]+=int(args[5].shape[0]*args[5].shape[1])
        return result
    def collect(*args,**kwargs):
        context['mode']='dense' if context['collect_calls']%2==0 else 'truncated'
        context['collect_calls']+=1
        return original_collect(*args,**kwargs)
    e.assess,e.collect,e.pulse_batch=assess,collect,pulse
    try:data=e.actor_run(s,spec,cfg,alg,path)
    except Exception as exc:error=repr(exc)
    finally:e.assess,e.collect,e.pulse_batch=original_assess,original_collect,original_pulse
    ap=path.with_name(path.stem+'.audit.npz');np.savez_compressed(ap,A=s['A'],B=s['B'],K0=s['K0'],**candidates)
    audit=dict(spec=spec,algorithm=alg,calls=evaluations,committed_transition_counts=transitions,
      error=error,candidate_archive_sha256=e.sha(ap),engine_sha256=e.sha(e.__file__),driver_sha256=e.sha(__file__),job=os.environ['SLURM_JOB_ID'])
    e.save(path.with_name(path.stem+'.audit.json'),audit)
    if data:
        expected=sum((17+b)*32 for b in cfg['npg_batches'])
        assert transitions==data['actual_transitions']=={'dense':expected,'truncated':expected}
    return data,audit

def main():
    e.require_compute();p=argparse.ArgumentParser();p.add_argument('--bundle',type=int,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent;cfgpath=root/'configs/X1_actor_base2048_v2.json';cfg=json.loads(cfgpath.read_text())
    approval=json.loads((root/'X1/ACCEPTED_ACTOR.json').read_text())
    assert approval['decision']=='ACCEPTED_CONDITIONS_SATISFIED' and approval['selected_base']==2048
    assert approval['engine_sha256']==e.sha(e.__file__) and approval['config_sha256']==e.sha(cfgpath)
    pairs=[(s,t) for s in cfg['formal_systems'] for t in cfg['formal_trials']];system,trial=pairs[a.bundle]
    begun=time.monotonic();items=[]
    for null in (0.,.25):
        for m in cfg['ms']:
            if null and m==2:continue
            s=e.plant(12,m,2,system,null_scale=null)
            for alg in ('NPG','PI'):
                spec=dict(experiment='X1',n=12,m=m,r=2,system=system,trial=trial,null_scale=null,
                  base_blocks=2048,update_rule='NPG_eta' if alg=='NPG' else 'full_greedy',config_sha256=e.sha(cfgpath))
                path=e.OUT/'X1/formal'/alg/f's{system}-t{trial}-m{m}-null{int(null*100)}.json';path.parent.mkdir(parents=True,exist_ok=True)
                data,audit=audited_actor(s,spec,cfg,alg,path)
                items.append(dict(algorithm=alg,path=str(path),status='COMPLETE' if data else 'NUMERICAL_FAILURE',
                  seconds=data['seconds'] if data else None,error=audit['error']))
                print(json.dumps(items[-1]),flush=True)
    e.save(e.OUT/'X1/actor_bundles'/f'bundle-{a.bundle:03d}.json',dict(status='COMPLETE_ATTEMPTS',items=items,system=system,trial=trial,
      seconds=time.monotonic()-begun,job=os.environ['SLURM_JOB_ID'],approval=approval))

if __name__=='__main__':main()
