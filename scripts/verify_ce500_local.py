"""Verify complete local immutable CE500 artifacts and independently count N90."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bundles',type=Path,required=True);a=p.parse_args();out=a.output
    manifest=read(out/'artifact_sha256.json');cfg=read(out/'frozen/config.json')
    assert cfg['n']==500 and cfg['initial_gap']==1 and cfg['ranks']==[2,8,32,64,500]
    for label in ['common']+['formal-%02d'%i for i in range(6)]+['final']:
        assert read(a.bundles/(label+'-local-verification.json'))['status']=='PASS'
    for relative,digest in manifest.items():
        pp=PurePosixPath(relative)
        assert not pp.is_absolute() and '..' not in pp.parts
        assert sha(out/relative)==digest,relative
    actual={str(f.relative_to(out)).replace('\\','/') for f in out.rglob('*') if f.is_file()}
    assert actual==set(manifest)|{'artifact_sha256.json'},actual.symmetric_difference(set(manifest)|{'artifact_sha256.json'})
    verification=read(out/'verification.json');identity=verification['identity']
    for relative,digest in identity['sources'].items():assert sha(out/'frozen'/relative)==digest
    for rank,digest in verification['system_hashes'].items():assert sha(out/'systems'/('r%03d.npz'%int(rank)))==digest
    assert max(abs(q['initial_gap']-1) for q in verification['systems'])<1e-9
    plan=read(out/'formal_plan.json');summary=read(out/'report-confirm/summary.json')
    budgets=[v+cfg['burn'] for v in plan['budgets']]
    assert summary['budgets']==budgets and summary['seeds']==cfg['confirm_seeds']
    assert set(cfg['pilot_seeds']).isdisjoint(cfg['confirm_seeds'])
    assert summary['audit']['status']==read(out/'identification-audit/audit.json')['status']=='PASS'
    assert summary['audit']['paired_tasks']==150 and summary['audit']['final_joint_OLS_recomputed']==150
    assert summary['audit']['full_rank_paired_budget_checks']==450
    assert summary['audit']['unique_policies_reevaluated']==4050,'The original complete independent audit must be retained'
    curves={};records=0;job_ids=set();physical=0
    for rank in cfg['ranks']:
        for seed in cfg['confirm_seeds']:
            raw=read(out/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json')
            assert raw['identity']==identity and raw['budgets']==plan['budgets']
            assert raw['physical_transitions']==budgets[-1]
            assert len(raw['records'])==2*len(budgets)
            physical+=raw['physical_transitions'];job_ids.add(raw['slurm_job_id'])
            for q in raw['records']:
                assert q['policy_sha256']==manifest[q['policy_file']]
                assert q['actual_transitions']==q['transitions']==q['ols_samples']+cfg['burn']
                records+=1
            for method in ('dense','truncated'):
                rr=[q for q in raw['records'] if q['method']==method]
                assert [q['transitions'] for q in rr]==budgets
                curves[rank,method,seed]=rr
    assert len(job_ids)==150 and physical==summary['audit']['physical_transitions'] and records==4500
    verified_thresholds=[]
    for req in summary['requirements']:
        rank,method,target=req['rank'],req['method'],req['relative_target']
        hits=[]
        for j,budget in enumerate(budgets):
            wins=0
            for seed in cfg['confirm_seeds']:
                row=curves[rank,method,seed][j]
                wins+=int(row['stable'] and row['gap'] is not None and row['gap']<=target)
            if wins>=27:hits.append((budget,wins))
        expected=hits[0][0] if hits else None
        assert req['N_hat_90']==expected,(rank,method,target,req['N_hat_90'],expected)
        if hits:assert req['threshold_or_endpoint_successes']==hits[0][1]
        verified_thresholds.append(dict(rank=rank,method=method,target=target,N90=expected))
    execution=read(out/'report-confirm/execution_cost_audit.json')
    assert execution['all_twenty_N90_values_unchanged'] and execution['all_seed_success_events_at_all_budgets_unchanged']
    result=dict(status='PASS',global_files_verified=len(manifest),bundle_groups_verified=8,
        formal_tasks=150,distinct_final_output_writer_jobs=150,formal_method_outputs=records,
        learning_job_attempts=150+read(out/'formal_submission.json').get('recovery_attempts',1),resource_timeout_attempts_retained=execution['resource_timeout_attempts_retained'],
        actual_primitive_transition_interval=[execution['total_primitive_transitions_lower'],execution['total_primitive_transitions_upper']],
        original_full_independent_policy_audit_count=4050,independently_counted_sample_thresholds=verified_thresholds,
        primitive_transitions_formal=physical,verifier_source_sha256=sha(Path(__file__)))
    dest=a.bundles/'global-local-verification.json';dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='independently_counted_sample_thresholds'}))


if __name__=='__main__':main()
