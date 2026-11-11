"""X12 metadata deployment, once-only submission and read-only tracking."""
import argparse, datetime, fcntl, hashlib, json, re, subprocess, tarfile
from pathlib import Path, PurePosixPath
B=Path('/scratch/user/changze/lqr_experiments');O=B/'results/x12-20261106';TMP=B/'tmp/x12-20261106'
ACCOUNT='132685389143'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(p.read_text())
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(d,f,indent=2)
def call(a):return subprocess.check_output(a,text=True,stderr=subprocess.STDOUT)
def ledger():
    paths=list((O/'budget').glob('LEDGER_v*.json'));p=max(paths,key=lambda x:int(re.fullmatch(r'LEDGER_v(\d+)\.json',x.name)[1]))
    return p,load(p)
def nextledger(previous,d):
    version=int(re.fullmatch(r'LEDGER_v(\d+)\.json',previous.name)[1])+1
    path=previous.with_name('LEDGER_v'+str(version)+'.json')
    d=dict(d,previous_ledger_sha256=sha(previous),recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save(path,d);return path,d
def verify(root):
    for line in (root/'SHA256SUMS').read_text().splitlines():
        h,name=line.split('  ',1);assert sha(root/name)==h,name
def states(job):
    raw=call(['sacct','-X','--array','-n','-P','-j',job,'--format=JobID,State,ElapsedRaw,AllocTRES'])
    rows=[]
    for line in raw.splitlines():
        if not line:continue
        jid,state,secs,tres=line.split('|')[:4];t=dict(x.split('=',1) for x in tres.split(',') if '=' in x)
        assert '.' not in jid and (jid==job or jid.startswith(job+'_'))
        if int(secs):assert float(t.get('billing',0))==int(t.get('cpu',0))==1
        rows.append(dict(job=jid,state=state,seconds=int(secs),tres=tres,billing=float(t.get('billing',0))))
    assert rows;return rows
def require_complete(d):
    evidence=[]
    for e in d['allocations']:
        assert e.get('job'),'Unresolved prior sbatch reservation; reconcile, never replay.'
        rows=states(e['job']);assert len(rows)==e['tasks'] and all(r['state']=='COMPLETED' for r in rows)
        evidence.extend(rows)
    return evidence
def empty_queue():
    q=call(['squeue','-r','-h','-u','changze','-o','%i|%T|%j']);assert not q.strip(),'Wait for every own allocation, including pending reservations.'
    return q
def balance(required):
    s=call(['myproject']);a=next(x for x in s.splitlines() if '|'+ACCOUNT+'|' in x)
    assert float(a.split('|')[6])>=required;return s
def deploy(a):
    assert re.fullmatch(r'x12-20261106-(models|formal|report)-v1',a.name)
    archive=TMP/(a.name+'.tar.gz');assert sha(archive)==a.archive_sha256
    root=B/'releases'/a.name;assert not root.exists(),'Deployment already attempted; reconcile.'
    with tarfile.open(archive,'r:gz') as tf:
        ms=tf.getmembers();names=[m.name for m in ms];assert len(names)==len(set(names)) and 'SHA256SUMS' in names
        manifest=tf.extractfile('SHA256SUMS').read().decode()
        expected=dict((n,h) for h,n in (x.split('  ',1) for x in manifest.splitlines()))
        assert set(names)==set(expected)|{'SHA256SUMS'}
        for m in ms:
            p=PurePosixPath(m.name);assert m.isfile() and not p.is_absolute() and '..' not in p.parts and ':' not in m.name and '\\' not in m.name
            if m.name!='SHA256SUMS':assert hashlib.sha256(tf.extractfile(m).read()).hexdigest()==expected[m.name]
        root.mkdir()
        for m in ms:
            dest=root/m.name;dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:f.write(tf.extractfile(m).read())
            if m.name.endswith('.sbatch'):dest.chmod(0o700)
    verify(root);receipt=dict(status='NEW_X12_RELEASE_DEPLOYED_HASH_VERIFIED',release=str(root),archive_sha256=sha(archive),files=len(ms))
    save(O/'deployments'/(a.name+'.json'),receipt);print(json.dumps(receipt))
def submit(a):
    root=B/'releases'/('x12-20261106-'+a.stage+'-v1');verify(root)
    gate=load(root/'gate.json');assert gate['status']=='ALL_PILOT_COST_GATES_PASS' and all(gate['checks'].values())
    assert gate['actual_forecast_SU']<=230 and gate['requested_upper_SU']<=300 and gate['global_concurrency']==64
    review=(root/'CLAUDE_TASK_authorized.md').read_text(encoding='utf-8-sig')
    assert 'proceed to FORMAL without waiting for another review' in review
    begin_dir=O/'submissions'/('followon-'+a.stage+'-v1');assert not begin_dir.exists(),'Prior submission attempt; reconcile, never replay.'
    with (O/'followon-submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        lp,d=ledger();prior=require_complete(d);empty_queue()
        assert d['cumulative_requested_SU']<300
        if a.stage=='models':
            assert d['cumulative_requested_SU']==8.75 and not (O/'formal-models-v1').exists()
            jobs=[dict(role='models',tasks=1,partition='short',wall_minutes=5,requested_SU=5/60,script='models.sbatch')]
        elif a.stage=='formal':
            assert not (O/'formal-v1').exists()
            models=load(O/'formal-models-v1/DONE.json')
            assert models['status']=='FORMAL_MODELS_FIXED_NO_OBSERVATIONS' and models['simulated_transitions']==0
            assert sha(O/'formal-models-v1/DONE.json')==sha(root/'MODEL_REGISTRY_DONE.json')
            cfg=load(root/'formal-config.json');assert cfg['gate_sha256']==sha(root/'gate.json')
            for meta in cfg['model_registry'].values():assert sha(root/meta['path'])==meta['sha256']
            assert len(cfg['formal_groups'])==2 and cfg['n_values']==[60] and len(cfg['rungs'])==9
            jobs=[dict(role=g['algorithm'],group=g['id'],tasks=32,partition=g['partition'],wall_minutes=g['wall_minutes'],
                       requested_SU=g['requested_SU'],script='formal-g'+str(i)+'.sbatch') for i,g in enumerate(gate['groups'])]
            assert abs(d['cumulative_requested_SU']+sum(x['requested_SU'] for x in jobs)+8-gate['requested_upper_SU'])<1e-8
        else:raise AssertionError('Report submission not enabled in this version.')
        assert sum(x['tasks'] for x in jobs)<=64
        begin_dir.mkdir();save(begin_dir/'PREFLIGHT.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            prior_allocations=prior,prior_ledger_sha256=sha(lp),release_manifest_sha256=sha(root/'SHA256SUMS'),gate_sha256=sha(root/'gate.json'),
            own_queue_empty=True,all_reserved_new_slots=sum(x['tasks'] for x in jobs),global_limit=64,automatic_retries=0))
        submitted=[]
        for spec in jobs:
            part=call(['scontrol','show','partition',spec['partition'],'-o']);assert 'State=UP' in part
            assert spec['partition'] in ['short','medium'] and spec['wall_minutes']<=(120 if spec['partition']=='short' else 1440)
            bound=spec['requested_SU'];assert d['cumulative_requested_SU']+bound+8<=300
            name='x12-'+a.stage+'-v1-'+spec['role'];money=balance(bound)
            assert not call(['sacct','-X','--array','-n','-P','-u','changze','-S','2026-11-06T00:00:00','--name='+name,'--format=JobID']).strip()
            command=['sbatch','--parsable','--account='+ACCOUNT,'--partition='+spec['partition'],'--ntasks=1','--cpus-per-task=1',
                     '--mem=2048M','--time='+str(spec['wall_minutes']),'--no-requeue','--job-name='+name,
                     '--output='+str(O/'logs'/(name+'-%A_%a.out'))]
            if spec['tasks']==32:command.append('--array=0-31%32')
            command.append(str(root/spec['script']))
            record=dict(spec,stage=a.stage,job=None,status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',command=command,
                        cpus=1,memory_MiB=2048,release=str(root),balance_snapshot=money)
            save(begin_dir/(spec['role']+'-BEGIN.json'),record)
            d=dict(d,allocations=d['allocations']+[record],cumulative_requested_SU=d['cumulative_requested_SU']+bound,
                   report_reserved_SU=8,measured_actual_forecast_SU=gate['actual_forecast_SU'])
            lp,d=nextledger(lp,d)
            response=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            result=dict(record,returncode=response.returncode,stdout=response.stdout,stderr=response.stderr)
            save(begin_dir/(spec['role']+'-RESPONSE.json'),result)
            assert response.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',response.stdout.strip()),'Uncertain/rejected sbatch; stop, no replay.'
            result.update(job=response.stdout.strip().split(';')[0],status='SUBMITTED_ONCE')
            save(begin_dir/(spec['role']+'-SUBMITTED.json'),result)
            d=dict(d,allocations=d['allocations'][:-1]+[result]);lp,d=nextledger(lp,d);submitted.append(result)
            print(json.dumps(dict(status='SUBMITTED_ONCE',stage=a.stage,role=spec['role'],job=result['job'],requested_SU=bound)),flush=True)
        result=dict(status='X12_'+a.stage.upper()+'_SUBMITTED_ONCE',jobs=submitted,requested_upper_SU=d['cumulative_requested_SU'],
                    report_reserve_SU=8,global_concurrency=64,automatic_retries=0)
        save(begin_dir/'DONE.json',result);print(json.dumps(result),flush=True)
def status(a):
    lp,d=ledger();alloc=[];elapsed=0;uncertain=[]
    for entry in d['allocations']:
        if not entry.get('job'):uncertain.append(entry);continue
        rows=states(entry['job']);elapsed+=sum(x['seconds']*x['billing']/3600 for x in rows)
        alloc.append(dict(job=entry['job'],role=entry.get('role','calibration' if entry['tasks']==8 else 'resolution'),rows=rows))
    own=call(['squeue','-r','-h','-u','changze','-o','%i|%T|%j']).splitlines()
    active=sum(x.split('|')[1] in ['RUNNING','COMPLETING','CONFIGURING'] for x in own);assert active<=64
    groups={}
    for alg in ['NPG','PI']:
        base=O/'formal-v1'/('n60-nine-'+alg)
        groups[alg]=dict(complete=[i for i in range(32) if (base/('task-'+str(i))/'DONE.json').exists()],
                        hard_failures=[str(p) for p in base.glob('task-*/HARD_FAILURE.json')])
    print(json.dumps(dict(status='X12_READONLY_METADATA_STATUS',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        ledger_path=str(lp),ledger_sha256=sha(lp),allocations=alloc,uncertain_reservations=uncertain,Slurm_elapsed_SU=elapsed,
        requested_upper_SU=d['cumulative_requested_SU'],report_reserved_SU=d.get('report_reserved_SU'),own_queue=own,own_running=active,
        formal_groups=groups,model_registry_done=(O/'formal-models-v1/DONE.json').exists(),no_performance_readout=True)))
if __name__=='__main__':
    p=argparse.ArgumentParser();sp=p.add_subparsers(dest='command',required=True)
    q=sp.add_parser('deploy');q.add_argument('--name',required=True);q.add_argument('--archive-sha256',required=True)
    q=sp.add_parser('submit');q.add_argument('--stage',choices=['models','formal'],required=True)
    sp.add_parser('status');a=p.parse_args();globals()[a.command](a)
