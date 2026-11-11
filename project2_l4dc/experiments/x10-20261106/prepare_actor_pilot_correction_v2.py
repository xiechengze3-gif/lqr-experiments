"""Prepare a reviewable correction proposal. Does NOT authorize or run a pilot."""
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    original=HERE/'actor-draft-v2/actor_pilot.py'
    config=json.loads((HERE/'actor-draft-v2/actor-config-protocol-v1.json').read_text())
    text=original.read_text();assert sha(original.read_bytes())==config['scientific_sources']['actor_pilot.py']
    failure=json.loads((HERE/'ACTOR_PILOT_FAILURE_RECON_v1.json').read_text())
    assert failure['NPG_stored_artifact_hash_matches']==32 and failure['NPG_records_bitwise_equal']
    baseline=json.loads((HERE/'actor-replay-baseline-v2/MANIFEST_v2.json').read_text())
    assert baseline['original_stage_arrays']==48 and baseline['original_receipts']==2
    text=text.replace("OUT/'resource-v1/equivalence/PILOT_DONE.json'","OUT/'resource-v2/equivalence/PILOT_DONE.json'")
    text=text.replace("destination = OUT/'resource-v1'/role","destination = OUT/'resource-v2'/role")
    old="        old_path = Path(ref['remote_path'])"
    new="        old_path = ROOT/'replay-baseline'/ref['algorithm']/'DONE.json'"
    assert text.count(old)==1;text=text.replace(old,new)
    old="""        path = destination/(ref['algorithm']+'-validation-replay')
        actual = actor.run(s, expected['spec'], stage_config(schedule['batches']), ref['algorithm'], path)"""
    new="""        if ref['algorithm'] == 'NPG':
            path = OUT/'resource-v1/equivalence/NPG-validation-replay'
            assert e.sha(path/'DONE.json') == config['reuse_completed_v1_NPG_done_sha256']
            actual = json.loads((path/'DONE.json').read_text())
            assert actual['source_sha256'] == config['scientific_sources']['actor_paths.py']
            assert actual['engine_sha256'] == config['scientific_sources']['frozen_engine.py']
        else:
            path = destination/(ref['algorithm']+'-validation-replay')
            actual = actor.run(s, expected['spec'], stage_config(schedule['batches']), ref['algorithm'], path)"""
    assert text.count(old)==1;text=text.replace(old,new)
    old="                           replay_done_sha256=e.sha(path/'DONE.json')))"
    new="""                           replay_done_sha256=e.sha(path/'DONE.json'),
                           actual_origin='REUSED_COMPLETE_V1_NPG' if ref['algorithm']=='NPG' else 'NEW_V2_PI',
                           actual_done_path=str(path/'DONE.json')))"""
    assert text.count(old)==1;text=text.replace(old,new)
    old="                primitive_transitions=sum(sum(c['primitive_transitions'].values()) for c in checks),"
    new="""                primitive_transitions=sum(sum(c['primitive_transitions'].values()) for c in checks if c['algorithm']=='PI'),
                reused_completed_NPG_transitions=sum(sum(c['primitive_transitions'].values()) for c in checks if c['algorithm']=='NPG'),
                all_completed_equivalence_transitions=sum(sum(c['primitive_transitions'].values()) for c in checks),"""
    assert text.count(old)==1;text=text.replace(old,new)
    old="""    for key, meta in config['model_registry'].items():
        assert e.sha(ROOT/meta['path']) == meta['sha256'], key"""
    new=old+"""
    assert e.sha(__file__) == config['validation_wrapper_sha256']
    manifest_path = ROOT/'replay-baseline/MANIFEST_v2.json'
    assert e.sha(manifest_path) == config['reference_baseline_manifest_sha256']
    manifest = json.loads(manifest_path.read_text())
    assert manifest['original_stage_arrays'] == 48 and manifest['original_receipts'] == 2
    for name, meta in manifest['files'].items():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert e.sha(ROOT/'replay-baseline'/name) == meta['sha256'], name"""
    assert text.count(old)==1;text=text.replace(old,new)
    ast.parse(text)
    before=ast.parse(original.read_text());after=ast.parse(text)
    unchanged=[]
    for name in ['save_new','model','stage_config']:
        a=next(n for n in before.body if isinstance(n,ast.FunctionDef) and n.name==name)
        b=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name==name)
        assert ast.get_source_segment(original.read_text(),a)==ast.get_source_segment(text,b);unchanged.append(name)
    a=next(n for n in before.body if isinstance(n,ast.FunctionDef) and n.name=='timing')
    b=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name=='timing')
    assert ast.get_source_segment(text,b).replace('resource-v2','resource-v1')==ast.get_source_segment(original.read_text(),a)
    destination=HERE/'actor-pilot-correction-v2';assert not destination.exists();destination.mkdir()
    with (destination/'actor_pilot_v2.py').open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
    proposal=dict(status='PREPARED_FOR_CLAUDE_REVIEW_NOT_AUTHORIZED_NOT_RUN',
        original_wrapper_sha256=sha(original.read_bytes()),corrected_wrapper_sha256=sha((destination/'actor_pilot_v2.py').read_bytes()),
        original_learning_sources=config['scientific_sources'],unchanged_functions=unchanged,
        timing_function_identical_except_output_namespace=True,
        reference_baseline_manifest_sha256=sha((HERE/'actor-replay-baseline-v2/MANIFEST_v2.json').read_bytes()),
        reuse_completed_v1_NPG_done_sha256=failure['complete_NPG_replay_done_sha256'],
        unchanged_ids_seeds_rungs_algorithms=True,planned_new_equivalence_transitions=5929952,
        reused_completed_NPG_transitions=5929952,proposed_additional_requested_SU=4+1/6,
        prior_actual_elapsed_SU=failure['pilot_actual_elapsed_SU'],prior_requested_upper_SU=4+1/6,
        proposed_cumulative_pilot_requested_upper_SU=8+1/3,
        no_numeric_execution=True,new_jobs=0,SU=0,
        scope='Compare all saved NPG arrays without resampling; only uncompleted PI replay and two untouched timing tasks after explicit corrected-pilot authorization. Full reference-file preflight before any submission.')
    with (destination/'CORRECTION_PROPOSAL_v2.json').open('x') as stream:json.dump(proposal,stream,indent=2)
    print(json.dumps({k:v for k,v in proposal.items() if k!='original_learning_sources'}))


if __name__=='__main__':main()
