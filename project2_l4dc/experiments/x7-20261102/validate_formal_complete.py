"""Stdlib-only X7 coverage/count/source proof;matrix checks deferred REPORT."""
import argparse,datetime,hashlib,json,subprocess
from pathlib import Path
BASE=Path('/scratch/user/changze/lqr_experiments/results/x7-20261102')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True)
    p.add_argument('--raw',type=Path,required=True);a=p.parse_args()
    assert a.raw.resolve()==BASE/'formal-v1'
    cfg=json.loads(a.config.read_text());assert cfg['status']=='FORMAL_FROZEN'
    for name,digest in cfg['scientific_sources'].items():assert sha(a.config.parent/name)==digest
    ledger=json.loads((BASE/'budget/ledger.json').read_text())
    submissions=[r for r in ledger['submissions'] if r['stage']=='FORMAL']
    assert len(submissions)==1 and submissions[0]['status']=='SUBMITTED'
    job=submissions[0]['job']
    raw=subprocess.check_output(['sacct','-X','--array','-j',job,'-n','-P','--format=JobID%48,State'],text=True)
    states={parts[0]:parts[1] for line in raw.splitlines() if len(parts:=line.split('|'))>=2}
    if not all(states.get(job+'_'+str(i))=='COMPLETED' for i in range(32)):
        print(json.dumps(dict(status='NOT_ALL_COMPLETED',states=states)));return
    counts=dict(tasks=0,paths=0,outputs=0,fit_policy_archives=0,primitive_transitions=0)
    receipts=[]
    for index in range(32):
        system=cfg['formal_systems'][index//4];trial=cfg['formal_seeds'][index%4]
        task=a.raw/f'task-{index}';bundle_path=task/'BUNDLE_DONE.json'
        bundle=json.loads(bundle_path.read_text())
        assert bundle['status']=='COMPLETE' and bundle['index']==index
        assert bundle['system']==system and bundle['trial']==trial
        assert bundle['config_sha256']==sha(a.config)
        assert bundle['source_sha256']==cfg['scientific_sources']['x7_driver.py']
        expected={f'n{n}-{s}' for n in cfg['n_values'] for s in cfg['spectra']}
        assert {v['case'] for v in bundle['paths']}==expected
        for entry in bundle['paths']:
            path=task/entry['path'];assert entry['path']==entry['case']
            done_path=path/'DONE.json';assert sha(done_path)==entry['done_sha256']
            done=json.loads(done_path.read_text());spec=done['spec'];n=spec['n']
            assert done['status']=='COMPLETE' and spec['system']==system and spec['trial']==trial
            assert spec['experiment']=='X7' and spec['n']==spec['m']==spec['r']
            assert f'n{n}-{spec["spectrum"]}'==entry['case']
            assert done['config_sha256']==sha(a.config)
            assert done['source_sha256']==cfg['scientific_sources']['ce_fullrank.py']
            assert done['engine_sha256']==cfg['scientific_sources']['frozen_engine.py']
            assert done['model_sha256']==cfg['model_registry'][f'{entry["case"]}-s{system}']['sha256']
            budgets=[8*n*v for v in cfg['multiplier_grid']]
            arms=len([k for k in cfg['fixed_rank_pool'] if k<n])+5
            assert len(done['records'])==6*arms and len(done['artifacts'])==6
            assert [v['N'] for v in done['artifacts']]==budgets
            seen=[]
            for artifact in done['artifacts']:
                N=artifact['N'];assert (path/artifact['path']).is_file()
                prefix=json.loads((path/f'prefix-{N:09d}.json').read_text())
                assert prefix['status']=='COMPLETE_PREFIX' and prefix['artifact']==artifact
                assert prefix['config_sha256']==sha(a.config) and prefix['spec']==spec
                assert len(prefix['records'])==arms
                assert all(r['N']==N and r['transitions']==N+512 for r in prefix['records'])
                seen.extend(prefix['records'])
            assert seen==done['records']
            assert done['primitive_transitions']==max(budgets)+512==entry['primitive_transitions']
            counts['paths']+=1;counts['outputs']+=len(done['records'])
            counts['fit_policy_archives']+=6;counts['primitive_transitions']+=done['primitive_transitions']
            receipts.append(dict(path=str(done_path),sha256=entry['done_sha256']))
        counts['tasks']+=1
    assert counts==dict(tasks=32,paths=128,outputs=10752,fit_policy_archives=768,primitive_transitions=37814272)
    result=dict(status='COMPLETE_COVERAGE_COUNTS_SOURCES',counts=counts,
        checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        config_sha256=sha(a.config),source_sha256=sha(Path(__file__)),job=job,
        receipts=receipts,zero_new_transitions=True,
        numerical_checks='PENDING frozen compute-node REPORT:archive hashes,OLS/policy equivalence,cost identities')
    path=a.raw/'FORMAL_COMPLETE_v1.json';assert not path.exists()
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='receipts'}))

if __name__=='__main__':main()
