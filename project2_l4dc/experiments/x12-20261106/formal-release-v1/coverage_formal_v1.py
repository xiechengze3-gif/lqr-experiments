"""X12 whole-grid receipt/source/count audit; no numerical reanalysis."""
import datetime,hashlib,json,subprocess
from pathlib import Path
B=Path('/scratch/user/changze/lqr_experiments');O=B/'results/x12-20261106';R=B/'releases/x12-20261106-formal-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def main():
    target=O/'formal-v1/FORMAL_COVERAGE_v1.json';assert not target.exists(),'Reconcile any existing proof; never overwrite.'
    cfgpath=R/'formal-config.json';cfg=load(cfgpath)
    assert cfg['status']=='FORMAL_FROZEN' and cfg['n_values']==[60] and len(cfg['rungs'])==9
    chain=load(O/'submissions/followon-formal-v1/DONE.json');assert len(chain['jobs'])==2
    for name,h in cfg['scientific_sources'].items():assert sha(R/name)==h
    for m in cfg['model_registry'].values():assert sha(R/m['path'])==m['sha256']
    raw=subprocess.check_output(['sacct','-X','--array','-j',','.join(x['job'] for x in chain['jobs']),'-n','-P','--format=JobID,State,ElapsedRaw,AllocTRES'],text=True)
    slurm=[x.split('|')[:4] for x in raw.splitlines() if x];assert len(slurm)==64 and all(x[1]=='COMPLETED' for x in slurm)
    elapsed=0
    for jid,state,secs,tres in slurm:
        t=dict(x.split('=',1) for x in tres.split(',') if '=' in x)
        assert int(t['billing'])==int(t['cpu'])==1;elapsed+=int(secs)/3600
    bundles=[];keys=set();primitive=0
    for group,submitted in zip(cfg['formal_groups'],chain['jobs']):
        assert group['id']==submitted['group'] and len(group['runs'])==9
        assert [x['rung'] for x in group['runs']]==cfg['rungs']
        for index in range(32):
            folder=O/'formal-v1'/group['id']/('task-'+str(index));assert not (folder/'HARD_FAILURE.json').exists()
            donepath=folder/'DONE.json';done=load(donepath)
            assert done['status']=='COMPLETE' and done['group']==group and done['index']==index
            assert done['config_sha256']==sha(cfgpath) and done['source_sha256']==cfg['scientific_sources']['formal_driver.py']
            assert done['actor_sha256']==cfg['scientific_sources']['actor_paths.py'] and done['engine_sha256']==cfg['scientific_sources']['frozen_engine.py']
            system,seed=cfg['formal_systems'][index//4],cfg['formal_sampling_seeds'][index%4]
            assert done['spec']==dict(experiment='X12',n=60,m=60,r=2,system=system,seed=seed)
            assert len(done['paths'])==9;refs=[]
            for run,item in zip(group['runs'],done['paths']):
                assert Path(item['path']).name==item['path'];p=folder/item['path']/'DONE.json';d=load(p)
                assert sha(p)==item['done_sha256'] and d['status']=='COMPLETE' and d['algorithm']==run['algorithm']
                spec=d['spec'];assert (spec['n'],spec['m'],spec['r'],spec['system'],spec['seed'],spec['rung'])==(60,60,2,system,seed,run['rung'])
                assert d['source_sha256']==cfg['scientific_sources']['actor_paths.py'] and d['engine_sha256']==cfg['scientific_sources']['frozen_engine.py']
                s=next(x for x in cfg['all_schedules'] if x['rung']==run['rung']);M=s['primitive_per_arm_per_algorithm'];T=16 if run['algorithm']=='NPG' else 8
                assert d['primitive_transitions']==dict(dense=M,truncated=M) and item['primitive_per_arm']==M
                assert len(d['records'])==2*(T+1) and len(d['artifacts'])==2*T
                key=(run['algorithm'],system,seed,run['rung']);assert key not in keys;keys.add(key);primitive+=2*M
                refs.append(dict(path=str(p),sha256=sha(p),primitive_per_arm=M))
            bundles.append(dict(group=group['id'],index=index,receipt_sha256=sha(donepath),paths=refs))
    assert len(bundles)==64 and len(keys)==576 and primitive==193644738560
    result=dict(status='FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                config_sha256=sha(cfgpath),bundles=64,paired_paths=576,arm_paths=1152,primitive_transitions=primitive,
                formal_Slurm_elapsed_SU=elapsed,science_sources=cfg['scientific_sources'],audits=bundles,slurm=slurm,
                no_new_training_transitions=True,full_stage_array_update_audit_pending_report=True)
    with target.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(status=result['status'],path=str(target),sha256=sha(target),bundles=64,paired_paths=576,
                          primitive_transitions=primitive,formal_Slurm_elapsed_SU=elapsed)))
if __name__=='__main__':main()
