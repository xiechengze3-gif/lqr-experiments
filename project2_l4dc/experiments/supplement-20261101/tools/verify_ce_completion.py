"""Login-node coverage/hash verification only, no scientific evaluation."""
import hashlib,json,sys,time
from pathlib import Path

base=Path('/scratch/user/changze/lqr_experiments');out=base/'results/supplement-20261101'
exp=sys.argv[1];assert exp in ['X2','X3'];release=base/'releases'/f'supplement-20261101-{exp.lower()}-ce-formal-v13'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cfgpath=release/f'configs/{exp}_CE_resolved_v2.json';cfg=json.loads(cfgpath.read_text())
approval=json.loads((release/exp/'ACCEPTED_CE.json').read_text());assert approval['decision']=='ACCEPTED' and approval['config_sha256']==sha(cfgpath)
bundles=sorted((out/exp/'formal-ce-bundles').glob('bundle-*.json'));assert len(bundles)==32
raw=[];outputs=0;failures=0;failure_modes={};jobs=set();identities=set();archives=0
for p in bundles:
    d=json.loads(p.read_text());assert d['status']=='COMPLETE' and d['config_sha256']==sha(cfgpath);jobs.add(d['job'])
    assert len(d['items'])==len(cfg['ce_cases'])
    for item in d['items']:
        path=Path(item['path']);assert sha(path)==item['sha256'];value=json.loads(path.read_text());spec=value['spec']
        case=next(c for c in cfg['ce_cases'] if c['n']==spec['n'] and c['r']==spec['r'] and c.get('spectrum','exact')==spec['spectrum'])
        identity=(spec['n'],spec['r'],spec['spectrum'],spec['system'],spec['trial']);assert identity not in identities;identities.add(identity)
        assert spec['system'] in cfg['formal_systems'] and spec['trial'] in cfg['formal_trials']
        modes=['dense','truncated'] if exp=='X2' else ['dense']+[f'k{k}' for k in case['fixed_ranks'] if k<case['n']]+['adaptive_paper','adaptive_split']
        expected={(N,mode) for N in case['prefixes'] for mode in modes}
        actual={(r['N'],r['mode']) for r in value['records']};assert actual==expected and len(actual)==len(value['records'])
        assert value['source_sha256']==sha(release/'engine.py') and value['transitions']==512+max(case['prefixes'])
        for row in value['records']:
            assert row['transitions']==512+row['N'];outputs+=1
            if not row['stable']:
                failures+=1;k=f"n{spec['n']}-r{spec['r']}-{spec['spectrum']}-N{row['N']}-{row['mode']}"
                failure_modes[k]=failure_modes.get(k,0)+1
        ap=path.with_name(path.stem+'.audit.json');audit=json.loads(ap.read_text());archive=path.with_name(path.stem+'.audit.npz')
        assert sha(archive)==audit['candidate_archive_sha256'];archives+=1
        raw.append(dict(path=str(path),sha256=sha(path),audit_json_sha256=sha(ap),candidate_archive_sha256=sha(archive)))
expected=len(cfg['ce_cases'])*32;assert len(raw)==expected
result=dict(status='COMPLETE',scope='CE_ONLY',experiment=exp,bundles=32,trajectories=expected,outputs=outputs,
   failed_outputs=failures,failures_by_cell=failure_modes,candidate_archives_hash_verified=archives,
   independent_numerical_policy_check='REPORT_PENDING',config_sha256=sha(cfgpath),engine_sha256=sha(release/'engine.py'),
   approval=approval,jobs=sorted(jobs),raw_hashes=raw,verified_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
path=out/exp/'FORMAL_CE_COMPLETE.json';assert not path.exists();path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['raw_hashes','failures_by_cell','approval','jobs']}))
