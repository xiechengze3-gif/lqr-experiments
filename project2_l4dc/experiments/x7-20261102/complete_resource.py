"""Stdlib-only own-pilot completeness and resource readout;no gap inspection."""
import argparse
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/x7-20261102'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True)
    a=p.parse_args();config=json.loads(a.config.read_text())
    assert config['status']=='PROTOCOL_FROZEN'
    ledger=json.loads((OUT/'budget/ledger.json').read_text())
    assert ledger['study']=='X7' and ledger['cap_requested_SU']==15
    rows=[r for r in ledger['submissions'] if r['stage']=='PILOT']
    assert len(rows)==1 and rows[0]['status']=='SUBMITTED'
    job=rows[0]['job'];expected={job+'_'+str(i) for i in range(4)}
    raw=subprocess.check_output(['sacct','-X','--array','-j',job,'-n','-P',
        '--format=JobID%48,State,ElapsedRaw,AllocTRES'],text=True)
    states={}
    for line in raw.splitlines():
        parts=line.split('|')
        if parts[0] in expected:states[parts[0]]=parts[1:]
    if set(states)!=expected or any(row[0]!='COMPLETED' for row in states.values()):
        print(json.dumps(dict(status='NOT_ALL_COMPLETED',states=states)));return
    cases=[];registry={};physical=0
    for n in config['n_values']:
        for spectrum in config['spectra']:
            case=f'n{n}-{spectrum}';path=OUT/'resource-v1'/case/'timing.json'
            data=json.loads(path.read_text())
            assert data['status']=='COMPLETE_RESOURCE_ONLY' and data['no_performance_readout']
            assert data['source_sha256']==config['scientific_sources']['x7_driver.py']
            assert data['core_sha256']==config['scientific_sources']['ce_fullrank.py']
            assert data['engine_sha256']==config['scientific_sources']['frozen_engine.py']
            assert data['config_sha256']==sha(a.config)
            assert data['equivalence']['status']=='PASS'
            assert data['equivalence']['full_and_half_fits_bitwise']
            assert data['equivalence']['final_state_and_rng_bitwise']
            assert len(data['rows'])==4 and data['formal_model_count']==8
            assert data['formal_model_training_transitions']==0
            assert {(r['system'],r['trial']) for r in data['rows']}=={
                (s,t) for s in config['pilot_systems'] for t in config['pilot_seeds']}
            assert all(r['newly_collected_transitions']==r['primitive_transitions']==8*n*1024+512 for r in data['rows'])
            for system in config['formal_systems']:
                key=f'{case}-s{system}';model=data['formal_model_registry'][key]
                model_path=Path(model['path'])
                assert model_path.resolve().is_relative_to(OUT/'resource-v1/models')
                assert sha(model_path)==model['sha256']
                registry[key]=dict(path=str(model_path),sha256=model['sha256'])
            physical+=data['primitive_transitions']
            cases.append(dict(case=case,n=n,spectrum=spectrum,timing_sha256=sha(path),
                worst_full_path_seconds=max(r['seconds'] for r in data['rows']),
                maximum_RSS_KiB=data['peak_RSS_KiB'],job=data['job'],
                equivalence=data['equivalence'],model_preparation_seconds=data['model_preparation_seconds'],
                actual_task_seconds=data['seconds']))
    billing=[]
    for row in states.values():
        tres=dict(piece.split('=',1) for piece in row[2].split(',') if '=' in piece)
        assert 'billing' in tres
        billing.append(float(tres['billing']))
    assert len(registry)==32 and physical==5908480
    result=dict(status='COMPLETE_RESOURCE_ONLY',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        config_sha256=sha(a.config),source_sha256=sha(Path(__file__)),job=job,states=states,
        cases=cases,model_registry=registry,effective_billing_cores=billing,
        elapsed_billing_SU=sum(float(s[1])*b/3600 for s,b in zip(states.values(),billing)),
        physical_pilot_transitions=physical,formal_training_transitions=0,
        zero_performance_readout=True,requested_SU=ledger['cumulative_requested_SU'])
    path=OUT/'resource-v1/RESOURCE_COMPLETE_v1.json'
    assert not path.exists(),'Download existing proof;do not replay.'
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='model_registry'}))

if __name__=='__main__':main()
