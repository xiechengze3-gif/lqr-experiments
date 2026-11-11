"""Metadata-only whole-grid X10b coverage proof after all 256 allocations finish."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/x10-20261106/X10b'
RELEASE=BASE/'releases/x10-20261106-b-formal-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target=OUT/'formal-v1/FORMAL_COVERAGE_v1.json'
    assert not target.exists(), 'Reconcile any existing proof; never overwrite.'
    cfgpath=RELEASE/'formal-config.json'
    cfg=json.loads(cfgpath.read_text())
    assert cfg['status']=='FORMAL_FROZEN'
    chain=json.loads((OUT/'submissions/FORMAL_CHAIN_v1.json').read_text())
    assert len(chain['jobs'])==8
    for name,digest in cfg['scientific_sources'].items():assert sha(RELEASE/name)==digest
    for meta in cfg['model_registry'].values():assert sha(RELEASE/meta['path'])==meta['sha256']
    raw=subprocess.check_output(['sacct','-X','--array','-j',','.join(r['job'] for r in chain['jobs']),
        '-n','-P','--format=JobID,State,ElapsedRaw,AllocTRES'],universal_newlines=True)
    slurm=[line.split('|')[:4] for line in raw.splitlines() if line.strip()]
    assert len(slurm)==256 and all(r[1]=='COMPLETED' for r in slurm)
    elapsed=0
    for row in slurm:
        alloc=dict(x.split('=',1) for x in row[3].split(',') if '=' in x)
        assert int(alloc['billing'])==int(alloc['cpu'])==1
        elapsed+=int(row[2])/3600
    bundles=[];path_count=0;primitive=0;keys=set()
    for position,group in enumerate(cfg['formal_groups']):
        assert chain['jobs'][position]['group']==group['id']
        assert len(group['runs'])==5 and [r['rung'] for r in group['runs']]==cfg['rungs']
        for index in range(32):
            folder=OUT/'formal-v1'/group['id']/('task-'+str(index))
            assert not (folder/'HARD_FAILURE.json').exists()
            donepath=folder/'DONE.json';done=json.loads(donepath.read_text())
            assert done['status']=='COMPLETE' and done['group']==group and done['index']==index
            assert done['config_sha256']==sha(cfgpath)
            assert done['source_sha256']==cfg['scientific_sources']['formal_driver.py']
            assert done['actor_sha256']==cfg['scientific_sources']['actor_paths.py']
            assert done['engine_sha256']==cfg['scientific_sources']['frozen_engine.py']
            system,seed=cfg['formal_systems'][index//4],cfg['formal_sampling_seeds'][index%4]
            assert done['spec']==dict(experiment='X10b',n=group['n'],m=group['n'],r=2,system=system,seed=seed)
            assert len(done['paths'])==5
            refs=[]
            for run,item in zip(group['runs'],done['paths']):
                assert Path(item['path']).name==item['path']
                path=folder/item['path']/'DONE.json'
                assert sha(path)==item['done_sha256']
                data=json.loads(path.read_text())
                assert data['status']=='COMPLETE' and data['algorithm']==run['algorithm']
                spec=data['spec']
                assert (spec['n'],spec['m'],spec['r'],spec['system'],spec['seed'],spec['rung'])==(group['n'],group['n'],2,system,seed,run['rung'])
                assert data['engine_sha256']==cfg['scientific_sources']['frozen_engine.py']
                assert data['source_sha256']==cfg['scientific_sources']['actor_paths.py']
                schedule=next(r for r in cfg['all_schedules'] if r['n']==group['n'] and r['rung']==run['rung'])
                M=schedule['primitive_per_arm_per_algorithm'];T=16 if run['algorithm']=='NPG' else 8
                assert data['primitive_transitions']==dict(dense=M,truncated=M)
                assert item['primitive_per_arm']==M
                assert len(data['records'])==2*(T+1) and len(data['artifacts'])==2*T
                key=(group['n'],run['algorithm'],system,seed,run['rung']);assert key not in keys;keys.add(key)
                path_count+=1;primitive+=2*M
                refs.append(dict(path=str(path),sha256=sha(path),primitive_per_arm=M))
            bundles.append(dict(group=group['id'],index=index,receipt_sha256=sha(donepath),paths=refs))
    assert len(bundles)==256 and path_count==1280 and primitive==243008280576
    proof=dict(status='FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS',
        checked_utc=datetime.datetime.utcnow().isoformat()+'Z',config_sha256=sha(cfgpath),
        bundles=256,paired_paths=1280,arm_paths=2560,primitive_transitions=primitive,
        formal_Slurm_elapsed_SU=elapsed,science_sources=cfg['scientific_sources'],
        audits=bundles,slurm=slurm,no_new_training_transitions=True)
    with target.open('x') as stream:json.dump(proof,stream,indent=2)
    print(json.dumps(dict(status=proof['status'],path=str(target),sha256=sha(target),
                         bundles=256,paired_paths=1280,primitive_transitions=primitive,formal_Slurm_elapsed_SU=elapsed)))


if __name__=='__main__':main()
