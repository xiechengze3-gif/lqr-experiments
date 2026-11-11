"""Freeze X12 gates and new releases from saved receipts; no simulation or submit."""
import argparse, ast, datetime, hashlib, io, json, math, re, tarfile
from pathlib import Path

R=Path(__file__).resolve().parent; C=R.parents[1]; P=R/'pilot-release-v1'
REMOTE='/scratch/user/changze/lqr_experiments'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(b):return hashlib.sha256(b).hexdigest()
def encode(d):return (json.dumps(d,indent=2)+'\n').encode()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def new(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(b)
def review(expected):
    p=C/'CLAUDE_TASK.md'; b=p.read_bytes(); assert digest(b)==expected
    assert b'X12 resource rule accepted' in b and b'proceed to FORMAL without waiting for another review' in b
    return b
def verified_pilot():
    cfg=load(P/'config-protocol-v1.json')
    for line in (P/'SHA256SUMS').read_text().splitlines():
        h,n=line.split('  ',1); assert sha(P/n)==h,n
    for n,h in cfg['sources'].items():assert sha(P/n)==h
    identity=load(P/'SOURCE_IDENTITY.json')
    assert identity['engine_byte_identical'] and identity['estimator_byte_identical'] and identity['actor_numerical_source_literal_identity']
    old=R.parent/'x10-20261106/prepared-actor-formal-v1'
    assert (P/'frozen_engine.py').read_bytes()==(old/'frozen_engine.py').read_bytes()
    assert (P/'estimation.py').read_bytes()==(old/'estimation.py').read_bytes()
    assert (P/'actor_paths.py').read_text().replace('/results/x12-20261106','/results/x10-20261106/X10b')==(old/'actor_paths.py').read_text()
    return cfg
def package(stage,files,expected):
    rb=review(expected); name='x12-20261106-'+stage+'-v1'
    folder=R/(stage+'-release-v1'); archive=R/(name+'.tar.gz')
    assert not folder.exists() and not archive.exists()
    for n,b in files.items():
        assert not Path(n).is_absolute() and '..' not in Path(n).parts
        if n.endswith('.py'):ast.parse(b.decode(),filename=n)
    files['CLAUDE_TASK_authorized.md']=rb
    hashes={n:digest(b) for n,b in files.items()}
    files['SHA256SUMS']=''.join(h+'  '+n+'\n' for n,h in hashes.items()).encode()
    assert (C/'CLAUDE_TASK.md').read_bytes()==rb
    for n,b in files.items():new(folder/n,b)
    with tarfile.open(archive,'x:gz') as tf:
        for n,b in files.items():
            m=tarfile.TarInfo(n);m.size=len(b);tf.addfile(m,io.BytesIO(b))
    result=dict(status='NEW_RELEASE_FROZEN_NOT_SUBMITTED',stage=stage,name=name,archive=str(archive),
                archive_sha256=sha(archive),source_manifest_sha256=sha(folder/'SHA256SUMS'),files=hashes,
                review_sha256=expected)
    new(R/(stage.upper()+'_MANIFEST_v1.json'),encode(result));print(json.dumps(result))
def script(stage,command):
    t=(P/'NPG.sbatch').read_text()
    t=t.replace('releases/x12-20261106-pilot-v1','releases/x12-20261106-'+stage+'-v1')
    before='pilot_driver.py --config config-protocol-v1.json --role NPG'
    assert t.count(before)==1
    return t.replace(before,command).encode()
def gate(a):
    rb=review(a.expected_review_sha256); cfg=verified_pilot(); audit=load(a.audit)
    assert audit['status']=='PASS_FIXED_PILOT_METADATA_HASHES_COUNTS_RNG_RSS_SLURM'
    assert audit['protocol_sha256']==sha(P/'config-protocol-v1.json') and audit['pilot_requested_upper_SU']==8.75
    assert audit['new_formal_transitions']==0 and audit['no_performance_gate'] and audit['automatic_retries']==0
    age=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(audit['checked_utc'])).total_seconds()
    assert 0<=age<=900,'Refresh completed-pilot readonly audit.'
    calpath=R/'raw-deliveries-v1/calibration-v1/calibration-resolution-v1/DONE.json';cal=load(calpath)
    assert audit['calibration_sha256']==sha(calpath) and audit['N_cal']==cal['N_cal']
    floors=load(R/'RESOURCE_HISTORY_FLOOR_v1.json');groups=[];raw=[]
    for alg in ['NPG','PI']:
        folder=R/('raw-deliveries-v1/timing-'+alg+'-v1')
        receipt=folder/('timing-v1/'+alg+'/PILOT_DONE.json')
        d=load(receipt); assert sha(receipt)==audit['timings'][alg]['done_sha256']
        verified=load(folder.with_suffix('.verified.json'))
        assert verified['status']=='VERIFIED_EXTRACTED_COMPLETE_X12_RAW_SNAPSHOT'
        measured=d['body_seconds']; floor=next(x for x in floors['rules'] if x['algorithm']==alg)['historical_body_floor_seconds']
        body=max(measured,floor);wall=math.ceil((1.2*body+30)/60)
        partition='short' if wall<=120 else 'medium'
        assert 'State=UP' in audit['partitions'][partition]
        groups.append(dict(id='n60-nine-'+alg,n=60,algorithm=alg,tasks=32,cpus=1,memory_MiB=2048,
                           measured_body_seconds=measured,historical_floor_seconds=floor,body_seconds=body,
                           wall_minutes=wall,partition=partition,requested_SU=32*wall/60,wall_guard_pass=60*wall>=1.2*body+30))
        raw.append(dict(algorithm=alg,local_path=str(folder),receipt_sha256=sha(receipt),verification_sha256=sha(folder.with_suffix('.verified.json'))))
    forecast=32*sum(x['body_seconds'] for x in groups)/3600+audit['pilot_actual_elapsed_SU']+5/60+8
    upper=8.75+5/60+sum(x['requested_SU'] for x in groups)+8
    checks=dict(all_fixed_pilot_checks_pass=True,all_raw_on_E_verified=True,actual_forecast_under_230=forecast<=230,
                requested_upper_under_300=upper<=300,all_wall_guards_pass=all(x['wall_guard_pass'] for x in groups),
                walls_within_medium_24h=all(x['wall_minutes']<=1440 for x in groups),account_can_cover_requested= audit['account_balance_SU']>=upper-8.75)
    status='ALL_PILOT_COST_GATES_PASS' if all(checks.values()) else 'STOP_FIXED_GATE_FAILED'
    result=dict(status=status,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,groups=groups,
                actual_forecast_SU=forecast,requested_upper_SU=upper,pilot_actual_elapsed_SU=audit['pilot_actual_elapsed_SU'],
                pilot_requested_upper_SU=8.75,model_prep_reserved_SU=5/60,report_reserved_SU=8,N_cal=cal['N_cal'],
                pilot_audit_sha256=sha(a.audit),calibration_sha256=sha(calpath),resource_floor_sha256=sha(R/'RESOURCE_HISTORY_FLOOR_v1.json'),
                review_sha256=digest(rb),global_concurrency=64,paired_paths=576,arm_paths=1152,
                primitive_transitions=64*2*sum(x['primitive_per_arm_per_algorithm'] for x in cal['all_schedules']),
                raw_delivery_proofs=raw,no_outcome_selection=True,automatic_retries=0)
    assert result['primitive_transitions']==193644738560
    assert (C/'CLAUDE_TASK.md').read_bytes()==rb
    new(R/'PILOT_COST_GATES_v1.json',encode(result)); new(R/'PILOT_AUDIT_v1.json',a.audit.read_bytes())
    print(json.dumps(result)); assert status=='ALL_PILOT_COST_GATES_PASS','Stop/report; no tuning/cuts/retries.'
def models(a):
    review(a.expected_review_sha256); verified_pilot();g=load(R/'PILOT_COST_GATES_v1.json')
    assert g['status']=='ALL_PILOT_COST_GATES_PASS'
    files={n:(P/n).read_bytes() for n in ['frozen_engine.py','estimation.py']}
    files.update({'protocol.json':(P/'config-protocol-v1.json').read_bytes(),'gate.json':(R/'PILOT_COST_GATES_v1.json').read_bytes(),
                  'model_registry_driver.py':(R/'model_registry_driver.py').read_bytes(),'remote_followon_v1.py':(R/'remote_followon_v1.py').read_bytes()})
    files['models.sbatch']=script('models','model_registry_driver.py --protocol protocol.json --gate gate.json --out "$base/results/x12-20261106/formal-models-v1"')
    package('models',files,a.expected_review_sha256)
def formal(a):
    review(a.expected_review_sha256);p=verified_pilot();g=load(R/'PILOT_COST_GATES_v1.json')
    assert g['status']=='ALL_PILOT_COST_GATES_PASS'
    folder=R/'formal-models-v1';receipt=load(folder/'DONE.json')
    assert receipt['status']=='FORMAL_MODELS_FIXED_NO_OBSERVATIONS' and receipt['simulated_transitions']==0
    assert receipt['gate_sha256']==sha(R/'PILOT_COST_GATES_v1.json') and receipt['protocol_sha256']==sha(P/'config-protocol-v1.json')
    assert receipt['source_sha256']==sha(R/'model_registry_driver.py')
    assert receipt['engine_sha256']==p['sources']['frozen_engine.py'] and receipt['estimator_sha256']==p['sources']['estimation.py']
    assert set(receipt['models'])=={'n60-s'+str(x) for x in range(301,309)}
    files={n:(P/n).read_bytes() for n in ['frozen_engine.py','estimation.py','actor_paths.py','SOURCE_IDENTITY.json']}
    runtime=R/'runtime-prepared-v1'
    for n in ['formal_driver.py','analyze_actor.py','paper_cross.py','ADAPTER_SOURCE_PROOF.json']:files[n]=(runtime/n).read_bytes()
    files['remote_followon_v1.py']=(R/'remote_followon_v1.py').read_bytes()
    files['coverage_formal_v1.py']=(R/'coverage_formal_v1.py').read_bytes()
    registry={}
    for key,meta in receipt['models'].items():
        name=meta['path'];assert Path(name).name==name and sha(folder/name)==meta['sha256']
        registry[key]=dict(meta,path='models/'+name);files['models/'+name]=(folder/name).read_bytes()
    cal=load(R/'raw-deliveries-v1/calibration-v1/calibration-resolution-v1/DONE.json')
    groups=[]
    for resource in g['groups']:
        alg=resource['algorithm']
        groups.append(dict(id=resource['id'],n=60,runs=[dict(algorithm=alg,rung=s['rung'],rung_label=s['rung_label']) for s in cal['all_schedules']],
                           wall_minutes=resource['wall_minutes'],partition=resource['partition']))
    cfg=dict(status='FORMAL_FROZEN',experiment='X12',family='S',n_values=[60],rank=2,k=2,eta=.2,p0_bound=2,H=16,nu=1.,burn_blocks=16,
             baseline_blocks=1,selected_NPG_T=16,selected_PI_T=8,formal_systems=p['formal_systems'],formal_sampling_seeds=p['formal_sampling_seeds'],
             npg_bases={'60':cal['N_cal']},rungs=p['rungs'],all_schedules=cal['all_schedules'],formal_groups=groups,model_registry=registry,
             scientific_sources={n:digest(files[n]) for n in ['frozen_engine.py','estimation.py','actor_paths.py','formal_driver.py','analyze_actor.py']},
             bootstrap_repetitions=5000,bootstrap_tag=621,relative_epsilons=[.1,.05],required_successes=29,
             actual_forecast_cap_SU=230,requested_upper_cap_SU=300,global_concurrency=64,automatic_retries=0,
             protocol_sha256=sha(P/'config-protocol-v1.json'),gate_sha256=sha(R/'PILOT_COST_GATES_v1.json'),
             model_registry_receipt_sha256=sha(folder/'DONE.json'))
    files['formal-config.json']=encode(cfg);files['gate.json']=(R/'PILOT_COST_GATES_v1.json').read_bytes()
    files['MODEL_REGISTRY_DONE.json']=(folder/'DONE.json').read_bytes()
    for name in ['PILOT_AUDIT_v1.json','RESOURCE_HISTORY_FLOOR_v1.json','model_registry_driver.py','PROTOCOL_v1.md','accounting_v1.py','ACCOUNTING_SOURCE_PROOF_v1.json']:
        files[name]=(R/name).read_bytes()
    files['protocol.json']=(P/'config-protocol-v1.json').read_bytes()
    files['CALIBRATION_RESOLUTION_DONE.json']=(R/'raw-deliveries-v1/calibration-v1/calibration-resolution-v1/DONE.json').read_bytes()
    for index,group in enumerate(groups):
        command='formal_driver.py --config formal-config.json --group '+group['id']+' --index "$SLURM_ARRAY_TASK_ID" --out "$base/results/x12-20261106/formal-v1"'
        files['formal-g'+str(index)+'.sbatch']=script('formal',command)
    package('formal',files,a.expected_review_sha256)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['gate','models','formal']);ap.add_argument('--expected-review-sha256',required=True)
    ap.add_argument('--audit',type=Path);a=ap.parse_args();globals()[a.stage](a)
