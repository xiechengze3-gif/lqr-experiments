"""Compare unaffected routes against the previous frozen learning engine."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--old-manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    import fixed_value_run as current
    from threadpoolctl import threadpool_limits
    from dense_scaling import atomic_json
    cfg=json.loads(args.manifest.read_text());old=json.loads(args.old_manifest.read_text())
    normalized=json.loads(json.dumps(cfg))
    for profile,settings in normalized['profiles'].items():
        del settings['NPG']['batches']
        sequence=cfg['profiles'][profile]['NPG']['batches'];setting=old['profiles'][profile]['NPG']
        assert len(sequence)==setting['stages'] and sum(sequence)==setting['batch']*setting['stages']
        assert all(a<=b for a,b in zip(sequence,sequence[1:]))
    assert normalized==old, 'Only NPG batches may change'
    ident=current.identity(args.manifest)
    old_path=args.old_manifest.parent.parent/'scripts'/'fixed_value_run.py'
    spec=importlib.util.spec_from_file_location('previous_fixed_value_engine',old_path)
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    task=dict(cfg['tasks'][0],id=0,n=6,r=2,system_seed=901,profile='audit',scenario='audit')
    small_cfg=dict(cfg,tasks=[task],profiles={'audit':{a:dict(batch=4096,stages=3) for a in cfg['algorithms']}})
    roots=[args.output/'compatibility_audit'/'previous',args.output/'compatibility_audit'/'current']
    with threadpool_limits(limits=cfg['threads']):
        for root in roots:current.cache_systems(small_cfg,root,ident)
        for algorithm in ('CE','LSTD_PI','DIRECT_PI'):
            previous.run(task,algorithm,small_cfg,roots[0],ident)
            current.run(task,algorithm,small_cfg,roots[1],ident)
            records=[json.loads((root/algorithm/'raw'/'task-000.json').read_text())['records'] for root in roots]
            strip=lambda rows:[{k:v for k,v in row.items() if k!='solver'} for row in rows]
            assert strip(records[0])==strip(records[1]),algorithm
    result=dict(status='PASS',identity=ident,config_changed_only_NPG_batches=True,
                identical_total_transitions_all_profiles=True,
                CE_LSTD_DIRECT_previous_current_records_exact_match=True,
                audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    atomic_json(args.output/'compatibility_verification.json',result)
    print(json.dumps(result))


if __name__=='__main__':main()
