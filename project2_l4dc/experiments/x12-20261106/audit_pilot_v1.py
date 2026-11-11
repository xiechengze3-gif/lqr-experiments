"""Read-only completed X12 pilot audit. Metadata/hashes only; no outcome gate."""
import datetime, hashlib, json, subprocess
from pathlib import Path

B=Path('/scratch/user/changze/lqr_experiments')
O=B/'results/x12-20261106'; R=B/'releases/x12-20261106-pilot-v1'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text())
def call(a): return subprocess.check_output(a,text=True,stderr=subprocess.STDOUT)

def check_path(folder,alg,schedule,cfg,system,seed,job):
    p=folder/'DONE.json'; d=load(p); T=16 if alg=='NPG' else 8
    assert d['status']=='COMPLETE' and d['algorithm']==alg and d['job']==job
    assert d['source_sha256']==cfg['sources']['actor_paths.py']
    assert d['engine_sha256']==cfg['sources']['frozen_engine.py']
    assert (d['spec']['n'],d['spec']['m'],d['spec']['r'],d['spec']['system'],d['spec']['seed'],d['spec']['rung'])==(60,60,2,system,seed,schedule['rung'])
    M=schedule['primitive_per_arm_per_algorithm']
    assert d['primitive_transitions']==dict(dense=M,truncated=M)
    assert len(d['records'])==2*(T+1) and len(d['artifacts'])==2*T
    records={(r['stage'],r['arm']):r for r in d['records']}; assert len(records)==2*(T+1)
    artifacts={(a['stage'],a['arm']):a for a in d['artifacts']}; assert len(artifacts)==2*T
    files=0; used=0
    for stage,count in enumerate(schedule['batches'][alg],1):
        used+=(count+17)*16
        cp=load(folder/('checkpoint-%03d.json'%stage))
        assert cp['status']=='COMPLETE_STAGE' and cp['stage']==stage
        assert cp['source_sha256']==cfg['sources']['actor_paths.py']
        assert cp['engine_sha256']==cfg['sources']['frozen_engine.py']
        assert cp['spec']==d['spec'] and cp['config']==dict(H=16,nu=1.,burn_blocks=16,eta=.2,schedules=schedule['batches'])
        assert cp['total_primitive_transitions']==dict(dense=used,truncated=used)
        assert sha(folder/('checkpoint-%03d.npz'%stage))==cp['checkpoint_sha256']; files+=1
        assert len(cp['artifacts'])==2*stage and len(cp['records'])==2*(stage+1)
        for arm in ['dense','truncated']:
            a=artifacts[stage,arm]; r=records[stage,arm]
            assert a['path']=='stage-%03d-%s.npz'%(stage,arm)
            assert sha(folder/a['path'])==a['sha256']; files+=1
            assert r['N']==count and r['primitive_transitions']==used
            assert r['padding_transitions']==cp['padding_transitions'][arm]
            assert 0<=r['padding_transitions']<=used
            assert a['rng_state']['bit_generator']=='PCG64'
            assert a['rng_state']==artifacts[stage,'dense']['rng_state'], 'Paired external draw receipts differ.'
            assert a['padding_stage']==r['padding_stage']
            assert cp['artifacts'][2*(stage-1)+(['dense','truncated'].index(arm))]==a
    assert used==M
    return dict(done_sha256=sha(p),artifact_hashes_checked=files,stages=T,primitive_transitions=2*M,
                RNG_check='Saved PCG64 end-state equality across paired arms at every stage; not an independent draw replay')

def main():
    for line in (R/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1); assert sha(R/name)==digest,name
    cfg=load(R/'config-protocol-v1.json'); calpath=O/'calibration-resolution-v1/DONE.json'; cal=load(calpath)
    assert cal['status']=='PASS_CALIBRATION' and cal['N_cal'] in cfg['calibration_grid']
    assert not cal['formal_data_used'] and not cal['truncated_readout']
    assert cal['config_sha256']==sha(R/'config-protocol-v1.json')
    assert cal['engine_sha256']==cfg['sources']['frozen_engine.py'] and cal['estimator_sha256']==cfg['sources']['estimation.py']
    assert len(cal['all_schedules'])==9 and [s['rung'] for s in cal['all_schedules']]==cfg['rungs']
    assert next(r['N'] for r in cal['summary'] if r['rho_op_median']<=1)==cal['N_cal']
    assert not list((O/'failures').glob('*.json'))
    ledgerpath=O/'budget/LEDGER_v4.json'; ledger=load(ledgerpath)
    assert ledger['cumulative_requested_SU']==8.75 and len(ledger['allocations'])==4
    slurm=[]; elapsed=0
    for entry in ledger['allocations']:
        raw=call(['sacct','-X','--array','-n','-P','-j',entry['job'],'--format=JobID,State,ElapsedRaw,AllocTRES'])
        rows=[x.split('|')[:4] for x in raw.splitlines() if x]; assert len(rows)==entry['tasks']
        for jid,state,seconds,tres in rows:
            t=dict(x.split('=',1) for x in tres.split(',') if '=' in x)
            assert state=='COMPLETED' and int(t['billing'])==int(t['cpu'])==1
            elapsed+=int(seconds)/3600; slurm.append(dict(job=jid,state=state,seconds=int(seconds),tres=tres))
    calibration=[]
    for index in range(8):
        p=O/'calibration-v1'/('task-'+str(index))/'DONE.json'; d=load(p)
        assert d['status']=='COMPLETE' and d['index']==index
        assert (d['system'],d['seed'])==(cfg['calibration_systems'][index//4],cfg['calibration_seeds'][index%4])
        assert [r['N'] for r in d['rows']]==cfg['calibration_grid']
        assert d['primitive_transitions']==(max(cfg['calibration_grid'])+17)*16
        assert d['peak_RSS_KiB']<.8*2*1024**2 and 1.2*d['seconds']+30<=20*60
        assert d['config_sha256']==sha(R/'config-protocol-v1.json') and d['source_sha256']==cfg['driver_sha256']
        assert d['engine_sha256']==cfg['sources']['frozen_engine.py'] and d['estimator_sha256']==cfg['sources']['estimation.py']
        assert sha(p.parent/'model.npz')==d['model_sha256']
        for a in d['artifacts']: assert sha(p.parent/a['path'])==a['sha256']
        assert cal['references'][index]['sha256']==sha(p)
        calibration.append(dict(index=index,done_sha256=sha(p),peak_RSS_KiB=d['peak_RSS_KiB']))
    timings={}
    for alg in ['NPG','PI']:
        p=O/'timing-v1'/alg/'PILOT_DONE.json'; d=load(p)
        assert d['status']=='PASS' and d['algorithm']==alg and not d['formal_data_used'] and d['no_performance_readout']
        assert d['config_sha256']==sha(R/'config-protocol-v1.json') and d['calibration_sha256']==sha(calpath)
        assert d['engine_sha256']==cfg['sources']['frozen_engine.py'] and d['actor_sha256']==cfg['sources']['actor_paths.py']
        assert d['peak_RSS_KiB']<.8*2*1024**2 and 1.2*d['body_seconds']+30<=180*60
        assert len(d['rows'])==9 and [r['rung'] for r in d['rows']]==cfg['rungs']
        assert abs(d['body_seconds']-sum(r['seconds'] for r in d['rows']))<1e-8
        paths=[]
        for row,s in zip(d['rows'],cal['all_schedules']):
            folder=p.parent/s['rung_label']; assert sha(folder/'DONE.json')==row['done_sha256']
            assert row['primitive_per_arm']==s['primitive_per_arm_per_algorithm']
            paths.append(check_path(folder,alg,s,cfg,9102,9801,d['job']))
        assert d['primitive_transitions']==sum(x['primitive_transitions'] for x in paths)
        timings[alg]=dict(body_seconds=d['body_seconds'],seconds=d['seconds'],peak_RSS_KiB=d['peak_RSS_KiB'],
                          done_sha256=sha(p),job=d['job'],paths=paths)
    balance=call(['myproject']); account=next(x for x in balance.splitlines() if '|132685389143|' in x)
    own=call(['squeue','-r','-h','-u','changze','-o','%i|%T|%j']).splitlines()
    assert not own,'Wait until all own allocations finish before reserving 64 formal slots.'
    parts={n:call(['scontrol','show','partition',n,'-o']) for n in ['short','medium']}
    result=dict(status='PASS_FIXED_PILOT_METADATA_HASHES_COUNTS_RNG_RSS_SLURM',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                protocol_sha256=sha(R/'config-protocol-v1.json'),calibration_sha256=sha(calpath),N_cal=cal['N_cal'],
                calibration=calibration,timings=timings,Slurm=slurm,pilot_actual_elapsed_SU=elapsed,pilot_requested_upper_SU=8.75,
                ledger_sha256=sha(ledgerpath),account_balance_SU=float(account.split('|')[6]),myproject=balance,
                partitions=parts,own_queue=own,new_formal_transitions=0,no_performance_gate=True,automatic_retries=0)
    print(json.dumps(result))

if __name__=='__main__':main()
