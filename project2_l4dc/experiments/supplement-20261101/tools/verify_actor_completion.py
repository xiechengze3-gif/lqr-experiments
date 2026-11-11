"""Actor completion coverage/source/count hashes; no numerical policy evaluations."""
import hashlib,json,sys,time
from pathlib import Path

base=Path('/scratch/user/changze/lqr_experiments');out=base/'results/supplement-20261101';exp=sys.argv[1]
assert exp in ['X1','X2','X3'];old=exp=='X1';scope='ACTOR' if old else 'NPG'
bundle_folder=out/exp/('actor_bundles' if old else 'formal-npg-bundles');bundles=sorted(bundle_folder.glob('bundle-*.json'))
if len(bundles)!=32:
    print(json.dumps(dict(status='PENDING',experiment=exp,scope=scope,complete_bundles=len(bundles),expected=32)));raise SystemExit(0)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if old:
    release=base/'releases/supplement-20261101-x1-actor-formal-v8';config=release/'configs/X1_actor_base2048_v2.json'
else:
    release=base/'releases'/f'supplement-20261101-{exp.lower()}-npg-formal-v18';config=release/f'configs/{exp}_NPG_formal_v1.json'
cfg=json.loads(config.read_text());approval=json.loads((release/exp/f'ACCEPTED_{scope}.json').read_text())
assert approval['decision']=='ACCEPTED_CONDITIONS_SATISFIED'
items=[];identities=set();hard_failures=0;unequal_counts=0;assessed=0;outputs=0;failed_outputs=0;endpoint_failures={};trajectories=0
for p in bundles:
    bundle=json.loads(p.read_text());assert bundle['status']=='COMPLETE_ATTEMPTS'
    assert len(bundle['items'])==({'X1':18,'X2':2,'X3':9}[exp])
    for item in bundle['items']:
        path=Path(item['path']);audit_path=path.with_name(path.stem+'.audit.json')
        if old:
            audit=json.loads(audit_path.read_text());archive=path.with_name(path.stem+'.audit.npz')
            assert sha(archive)==audit['candidate_archive_sha256'] and audit['engine_sha256']==sha(release/'engine.py')
            d=json.loads(path.read_text()) if path.exists() else None;error=audit['error'];modes=['dense','truncated']
            expected=sum((17+b)*32 for b in cfg['npg_batches']);actual=audit['committed_transition_counts']
            spec=audit['spec'];algorithm=audit['algorithm'];assessed+=len(audit['calls'])
            assert spec['config_sha256']==sha(config)
        else:
            d=json.loads(path.read_text());assert sha(path)==item['sha256'];archive=path.with_suffix('.npz')
            assert sha(archive)==d['candidate_archive_sha256'] and d['engine_sha256']==sha(release/'engine.py')
            assert d['multi_source_sha256']==sha(release/'npg_multi.py')
            error=d['error'];actual=d['independently_counted_transitions'];spec=d['spec'];algorithm='NPG'
            expected=d['planned_transitions_per_arm'];modes=sorted(d['actual_transitions']);assessed+=sum('assessment_id' in r for r in d['records'])
        key=(algorithm,spec['n'],spec['m'],spec.get('null_scale'),spec.get('spectrum'),spec.get('budget_multiplier',1),spec['system'],spec['trial'])
        assert key not in identities;identities.add(key)
        assert spec['system'] in cfg['formal_systems'] and spec['trial'] in cfg['formal_trials']
        trajectories+=len(modes)
        if error is not None:hard_failures+=1
        else:
            assert d is not None and all(actual[m]==expected for m in modes) and actual==d['actual_transitions']
        if len(set(actual.values()))!=1:unequal_counts+=1
        if d:
            outputs+=len(d['records']);failed_outputs+=sum(not r['stable'] for r in d['records'])
            for mode in modes:
                endpoint=next((r for r in reversed(d['records']) if r['mode']==mode),None)
                if endpoint is None or not endpoint['stable'] or error is not None:
                    label=algorithm+'-'+mode;endpoint_failures[label]=endpoint_failures.get(label,0)+1
        items.append(dict(path=str(path),status='HARD_FAILURE' if error is not None else 'COMPLETE',error=error,
          json_sha256=sha(path) if path.exists() else None,candidate_archive=str(archive),candidate_archive_sha256=sha(archive),
          audit_json_sha256=sha(audit_path) if old else None,expected_transitions_per_arm=expected,actual_transitions=actual))
assert len(items)=={'X1':576,'X2':64,'X3':288}[exp] and trajectories=={'X1':1152,'X2':128,'X3':1440}[exp]
result=dict(status='COMPLETE',scope=scope,experiment=exp,bundles=32,attempted_pair_or_multi_runs=len(items),planned_actor_trajectories=trajectories,
  source_and_coverage_verified=True,hard_failure_attempts=hard_failures,unequal_actual_transition_attempts=unequal_counts,
  assessed_candidates=assessed,recorded_outputs=outputs,failed_recorded_outputs=failed_outputs,failed_endpoints=endpoint_failures,
  items=items,engine_sha256=sha(release/'engine.py'),config_sha256=sha(config),approval=approval,
  verified_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),independent_numerical_check='REPORT_PENDING')
path=out/exp/f'FORMAL_{scope}_COMPLETE.json';assert not path.exists();path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['items','approval']}))
