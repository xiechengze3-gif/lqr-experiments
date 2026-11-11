"""SHA-audit and package complete old paths only; no outcomes select membership."""
import hashlib,io,json,tarfile
from pathlib import Path
R=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def new(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2)
def main():
    receipt=load(R/'delivery-failed-formal-v1.verified.json')
    assert receipt['status']=='VERIFIED_FAILED_X12_PARTIAL_EVIDENCE_ON_E'
    manifestpath=R/'downloads-failed-formal-v1/x12-failed-formal-v1.tar.json';manifest=load(manifestpath)
    assert sha(manifestpath)==receipt['manifest_sha256'] and manifest['archive_sha256']==receipt['archive_sha256']
    cfgpath=R/'formal-release-v1/formal-config.json';cfg=load(cfgpath)
    assert sha(cfgpath)=='194f34ba2af8bd822396a9ae1e2317219ee5beb2da4f9a54df1d3eb479097d14'
    root=R/'delivery-failed-formal-v1';lookup={m['path']:m for m in manifest['files']}
    assert len(lookup)==len(manifest['files']);reused=[];tasks=[];accepted=0;generated=0
    target=R/'reused-complete-paths-v2.tar';assert not target.exists()
    def verified(path):
        name=path.relative_to(root).as_posix();assert name in lookup and sha(path)==lookup[name]['sha256'];return lookup[name]
    with tarfile.open(target,'x:',format=tarfile.USTAR_FORMAT) as tf:
        for group in cfg['formal_groups']:
            alg=group['runs'][0]['algorithm'];T=16 if alg=='NPG' else 8
            for index in range(32):
                system,seed=cfg['formal_systems'][index//4],cfg['formal_sampling_seeds'][index%4]
                task=dict(group=group['id'],algorithm=alg,index=index,system=system,seed=seed,runs=[])
                for run in group['runs']:
                    label=alg+'-'+run['rung_label'];prefix=group['id']+'/task-'+str(index)+'/'+label
                    folder=root/'results/formal-v1'/prefix;donepath=folder/'DONE.json'
                    s=next(x for x in cfg['all_schedules'] if x['rung']==run['rung']);M=s['primitive_per_arm_per_algorithm']
                    entry=dict(run,primitive_per_arm=M)
                    if not donepath.exists():
                        entry['origin']='RESTART_OR_START_FROM_K0';generated+=2*M;task['runs'].append(entry);continue
                    verified(donepath);done=load(donepath)
                    assert done['status']=='COMPLETE' and done['algorithm']==alg
                    assert done['source_sha256']==cfg['scientific_sources']['actor_paths.py']
                    assert done['engine_sha256']==cfg['scientific_sources']['frozen_engine.py']
                    spec=done['spec'];assert (spec['n'],spec['m'],spec['r'],spec['system'],spec['seed'],spec['rung'])==(60,60,2,system,seed,run['rung'])
                    assert done['primitive_transitions']==dict(dense=M,truncated=M)
                    assert len(done['records'])==2*(T+1) and len(done['artifacts'])==2*T
                    files={'DONE.json'};arts={(a['stage'],a['arm']):a for a in done['artifacts']};assert len(arts)==2*T
                    used=0
                    for stage,count in enumerate(s['batches'][alg],1):
                        used+=(count+17)*16;cpname='checkpoint-%03d'%stage
                        cpjson=folder/(cpname+'.json');verified(cpjson);cp=load(cpjson)
                        assert cp['status']=='COMPLETE_STAGE' and cp['stage']==stage
                        assert cp['spec']==spec and cp['total_primitive_transitions']==dict(dense=used,truncated=used)
                        assert cp['source_sha256']==cfg['scientific_sources']['actor_paths.py'] and cp['engine_sha256']==cfg['scientific_sources']['frozen_engine.py']
                        npz=folder/(cpname+'.npz');assert verified(npz)['sha256']==cp['checkpoint_sha256']
                        files.update([cpname+'.json',cpname+'.npz'])
                        for arm in ['dense','truncated']:
                            a=arts[stage,arm];assert a['path']=='stage-%03d-%s.npz'%(stage,arm)
                            assert verified(folder/a['path'])['sha256']==a['sha256'];files.add(a['path'])
                        assert arts[stage,'dense']['rng_state']==arts[stage,'truncated']['rng_state']
                    assert used==M and len(files)==4*T+1
                    members=[]
                    for name in sorted(files):
                        p=folder/name;meta=verified(p);data=p.read_bytes();member=prefix+'/'+name
                        info=tarfile.TarInfo(member);info.size=len(data);info.mode=0o600;tf.addfile(info,io.BytesIO(data))
                        members.append(dict(path=member,bytes=len(data),sha256=meta['sha256']))
                    r=dict(group=group['id'],algorithm=alg,index=index,system=system,seed=seed,rung=run['rung'],rung_label=run['rung_label'],
                           member_prefix=prefix,done_sha256=sha(donepath),actor_sha256=done['source_sha256'],engine_sha256=done['engine_sha256'],
                           primitive_per_arm=M,files=members,selection='COMPLETE_AND_SHA_VERIFIED_ONLY_NO_POLICY_QUALITY_CRITERION')
                    reused.append(r);accepted+=2*M;entry.update(origin='REUSED_COMPLETE_V1_SHA_VERIFIED',done_sha256=r['done_sha256'],member_prefix=prefix)
                    task['runs'].append(entry)
                assert len(task['runs'])==9;tasks.append(task)
    assert len(tasks)==64 and accepted+generated==193644738560
    result=dict(status='COMPLETE_OLD_PATHS_ONLY_SHA_VERIFIED',archive=str(target),archive_sha256=sha(target),archive_bytes=target.stat().st_size,
                old_failed_evidence_archive_sha256=receipt['archive_sha256'],source_config_sha256=sha(cfgpath),
                complete_reused_paired_paths=len(reused),reused_accepted_primitive_transitions=accepted,new_accepted_primitive_transitions=generated,
                final_logical_primitive_transitions=193644738560,reused_paths=reused,
                no_mid_path_resume=True,no_learner_or_collector_called=True,no_deletion=True,source_sha256=sha(Path(__file__)))
    new(R/'REUSED_COMPLETE_PATHS_v2.json',result)
    new(R/'RECOVERY_WORK_PLAN_v2.json',dict(status='FROZEN_COMPLETION_BASED_WORK_MEMBERSHIP',tasks=tasks,
        original_formal_config_sha256=sha(cfgpath),reused_manifest_sha256=sha(R/'REUSED_COMPLETE_PATHS_v2.json'),
        original_config_values=cfg,all_old_partial_data_retained=True,no_mid_path_resume=True,new_training_transitions_by_this_preparation=0))
    print(json.dumps({k:v for k,v in result.items() if k!='reused_paths'}))
if __name__=='__main__':main()
