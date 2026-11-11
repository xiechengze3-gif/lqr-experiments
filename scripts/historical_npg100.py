"""Adaptive NPG with original 100d model, step, collector and stage seeds."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
import numpy as np
from dense_scaling import system as rank_system,eta,evaluate,rng_for,atomic_json,targets
from approx_tail_system import system as tail_system,ETA
from npg_batched_collector import collect
from adaptive_rank import select,noise_proxy


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(manifest):
    files=['historical_npg100.py','vendor/dense_scaling.py','vendor/approx_tail_system.py',
           'vendor/npg_batched_collector.py','vendor/adaptive_rank.py']
    return dict(manifest_sha256=sha(manifest),sources={name:sha(ROOT/name) for name in files})


def seeds(case,stage):
    t=case['original_task']
    return (773991,t['n'],t['system_seed'],t['trial_seed'],stage) if case['benchmark']=='rank80' else (202610083,t['n'],t['system_seed'],stage)


def estimate(s,k,x,count,case,stage,split=True):
    budgets=[count//2,count] if split else [count]
    parts=list(collect(s,k,x,budgets,case['horizon'],case['sigma'],rng_for(*seeds(case,stage)),burn=case['burn']))
    _,x,z,_,gram,used=parts[-1];scale=None
    if split:
        half=count//2;_,_,z1,_,g1,_=parts[0]
        second_gram=count*gram-half*g1
        second_cross=z@(count*gram)-z1@(half*g1)
        z2=np.linalg.solve(second_gram,second_cross.T).T
        scale=noise_proxy(z1,z2)
    return x,z,scale,used


def update(k,r,z,method,scale,rank,step):
    if method=='raw':corrected=z.copy();info=dict(retained_rank=len(k),threshold=None)
    else:corrected,_,info=select(z,'known_rank' if method=='truncated' else method,scale,rank)
    return k-step*(r@k+corrected),info


def make_system(case):
    os.environ.pop('LQR_TAIL_SYSTEM_CACHE',None)
    return rank_system(case['original_task']) if case['benchmark']=='rank80' else tail_system(case['original_task'])


def step_size(case,s):return case['step_multiplier']*eta(s) if case['benchmark']=='rank80' else ETA


def cached(case,out,ident):
    path=out/'systems'/f"case-{case['id']:03d}.npz"
    meta=json.loads(path.with_suffix('.json').read_text())
    assert meta['identity']==ident and meta['case']==case and meta['npz_sha256']==sha(path)
    with np.load(path,allow_pickle=False) as archive:
        s={key:archive[key].copy() if archive[key].ndim else archive[key].item() for key in archive.files}
    return s,meta['step']


def checkpoint(path,ident,k,x,actual,failed,rows,next_stage):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.tmp')
    with temporary.open('wb') as stream:
        np.savez(stream,identity=np.array(json.dumps(ident,sort_keys=True)),k=k,x=x,actual=actual,
                 failed=failed,records=np.array(json.dumps(rows,allow_nan=False)),next_stage=next_stage)
    temporary.replace(path)


def run(case,cfg,out,ident,max_stages=None):
    final=out/'adaptive'/'raw'/f"case-{case['id']:03d}.json"
    if final.exists():assert json.loads(final.read_text())['identity']==ident;return True
    s,step=cached(case,out,ident);k=s['K0'].copy();x=np.zeros(len(k));actual=0;failed=False;start_stage=0
    quality,_=evaluate(s,k)
    rows=[dict(method='adaptive_1',stage=0,N=0,transitions=0,actual_transitions=0,observed=True,**quality)]
    path=out/'adaptive'/'checkpoints'/f"case-{case['id']:03d}.npz"
    if path.exists():
        with np.load(path,allow_pickle=False) as archive:
            assert json.loads(str(archive['identity']))==ident
            k,x=archive['k'].copy(),archive['x'].copy();actual=int(archive['actual'])
            failed=bool(archive['failed']);start_stage=int(archive['next_stage']);rows=json.loads(str(archive['records']))
    uses=[case['burn']+(n+1)*case['horizon'] for n in case['schedule']]
    cumulative=np.cumsum(uses).tolist();total=sum(uses);started=time.monotonic()
    for stage in range(start_stage,len(uses)):
        count=case['schedule'][stage]
        row=dict(method='adaptive_1',stage=stage+1,N=count,transitions=cumulative[stage],
                 assigned_total_budget=total,eta=step,observed=not failed)
        if failed:row.update(stable=False,cost=None,gap=None,failure='prior_failure')
        else:
            actual+=uses[stage]
            try:
                x,z,scale,used=estimate(s,k,x,count,case,stage)
                assert used==uses[stage]
                candidate,info=update(k,s['R'],z,'adaptive_1',scale,None,step)
                quality,_=evaluate(s,candidate);row.update(info,**quality)
                row['policy_sha256']=hashlib.sha256(candidate.tobytes()).hexdigest()
                failed=not quality['stable'];k=candidate
                if failed:row['failure']='controller_instability'
            except np.linalg.LinAlgError as error:
                failed=True;row.update(stable=False,cost=None,gap=None,failure='estimation_exception',failure_detail=str(error))
        row['actual_transitions']=actual;rows.append(row)
        checkpoint(path,ident,k,x,actual,failed,rows,stage+1)
        atomic_json(out/'progress.json',dict(case=case,stage=stage+1,stages=len(uses),current_batch=count,
            actual_transitions=actual,assigned_total_budget=total,stable=not failed,
            seconds_this_segment=time.monotonic()-started))
        print(json.dumps(dict(case=case['id'],stage=stage+1,stages=len(uses),stable=not failed)),flush=True)
        if max_stages is not None and stage+1-start_stage>=max_stages and stage+1<len(uses):return False
    atomic_json(final,dict(case=case,identity=ident,records=rows,step=step,assigned_total_budget=total,
        actual_total_budget=actual,execution=dict(location='local',threads=cfg['threads'])))
    return True


def verify(cfg,out,ident):
    source=json.loads((ROOT/'source_provenance.json').read_text())
    checks=[];out.mkdir(parents=True,exist_ok=True)
    for case in cfg['tasks']:
        old=json.loads(Path(case['old_raw']).read_text());assert sha(case['old_raw'])==case['old_sha256']
        engine=next(x for x in source if x['file']=='dense_scaling.py')
        assert old['engine_sha256']==engine['original_sha256']
        if case['benchmark']=='tail256':
            assert old['system_sha256']==next(x for x in source if x['file']=='approx_tail_system.py')['original_sha256']
            assert old['collector_sha256']==next(x for x in source if x['file']=='npg_batched_collector.py')['original_sha256']
        s=make_system(case);step=step_size(case,s);quality,_=evaluate(s,s['K0'])
        path=out/'systems'/f"case-{case['id']:03d}.npz";path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as stream:np.savez(stream,**{key:value for key,value in s.items() if key!='diagnostics'})
        old_initial=next(r for r in old['records'] if r['method']=='raw' and r['stage']==0)
        for key in ('cost','gap','rho'):
            assert np.isclose(quality[key],old_initial[key],rtol=cfg['replay_rtol'],atol=cfg['replay_atol']),(case['id'],key)
        assert np.linalg.matrix_rank(s['K0'])==100 and quality['stable']
        x,z,scale,used=estimate(s,s['K0'],np.zeros(100),case['schedule'][0],case,0)
        expected_used=case['burn']+(case['schedule'][0]+1)*case['horizon'];assert used==expected_used
        differences={}
        for method in ('raw','truncated'):
            candidate,_=update(s['K0'],s['R'],z,method,scale,case['original_task']['r'],step)
            current,_=evaluate(s,candidate)
            expected=next(r for r in old['records'] if r['method']==method and r['stage']==1)
            assert current['stable']==expected['stable']
            assert expected['eta']==step
            for key in ('cost','gap','rho'):
                assert np.isclose(current[key],expected[key],rtol=cfg['replay_rtol'],atol=cfg['replay_atol']),(case['id'],method,key,current[key],expected[key])
            differences[method]={key:abs(current[key]-expected[key]) for key in ('cost','gap','rho')}
        matrix_hashes={key:hashlib.sha256(np.ascontiguousarray(s[key]).tobytes()).hexdigest() for key in ('A','B','Q','R','W','K0')}
        old_hashes=old['diagnostics'].get('matrix_sha256',{})
        atomic_json(path.with_suffix('.json'),dict(case=case,identity=ident,npz_sha256=sha(path),step=step,
            matrix_sha256=matrix_hashes,historical_matrix_hash_available=bool(old_hashes),
            historical_matrices_bitwise_match=all(matrix_hashes[key]==value for key,value in old_hashes.items()) if old_hashes else None,
            diagnostics=s['diagnostics']))
        legacy=dict(old);legacy['reuse_provenance']=dict(new_identity=ident,original_file=case['old_raw'],
            original_sha256=case['old_sha256'],source_and_first_step_verified=True,
            cross_platform_reproduction='Numerical match, not a claim of bitwise trajectory equality',first_step_differences=differences)
        atomic_json(out/'baselines'/f"case-{case['id']:03d}.json",legacy)
        checks.append(dict(case=case['id'],initial_and_first_step_replay=True,step_exact_match=True,first_step_differences=differences))
        atomic_json(out/'verification_progress.json',dict(status='RUNNING',complete=len(checks),planned=len(cfg['tasks']),last=checks[-1]))
        print(json.dumps(dict(verified_case=case['id'],complete=len(checks),planned=len(cfg['tasks']))),flush=True)
    small=dict(cfg['tasks'][0],id=0,original_task=dict(cfg['tasks'][0]['original_task'],n=6,m=6,r=2),schedule=[1024,2048,4096])
    s=make_system(small);step=step_size(small,s)
    a=estimate(s,s['K0'],np.zeros(6),2048,small,0,True)
    b=estimate(s,s['K0'],np.zeros(6),2048,small,0,False)
    assert a[-1]==b[-1] and np.allclose(a[0],b[0],rtol=1e-11,atol=1e-11)
    assert np.allclose(a[1],b[1],rtol=1e-11,atol=1e-11)
    one,info=update(s['K0'],s['R'],a[1],'adaptive_1',a[2],2,step)
    two,other=update(s['K0'],s['R'],a[1],'adaptive_1',a[2],5,step)
    assert np.array_equal(one,two) and info==other
    roots=[out/'resume_audit'/'whole',out/'resume_audit'/'resumed']
    for target in roots:
        path=target/'systems'/'case-000.npz';path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as stream:np.savez(stream,**{key:value for key,value in s.items() if key!='diagnostics'})
        atomic_json(path.with_suffix('.json'),dict(case=small,identity=ident,npz_sha256=sha(path),step=step))
    assert run(small,cfg,roots[0],ident)
    assert not run(small,cfg,roots[1],ident,1)
    assert not run(small,cfg,roots[1],ident,1)
    assert run(small,cfg,roots[1],ident,1)
    records=[json.loads((target/'adaptive/raw/case-000.json').read_text())['records'] for target in roots]
    assert records[0]==records[1]
    atomic_json(out/'verification.json',dict(status='PASS',identity=ident,cases=checks,
        original_scalar_steps_preserved=True,original_batch_schedules_and_seeds_preserved=True,
        adaptive_rank_argument_invariance=True,no_model_or_test_cost_inputs_to_update=True,
        split_prefix_preserves_full_estimator_and_trajectory=True,checkpoint_replay=True,
        historical_baseline_reuse='Original sources, initial values and first stochastic updates matched numerically for each case. Old records and provenance retained.'))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['verify','run'])
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case-id',type=int);p.add_argument('--max-stages',type=int)
    a=p.parse_args();cfg=json.loads(a.manifest.read_text());ident=identity(a.manifest)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=cfg['threads']):
        if a.mode=='verify':verify(cfg,a.output,ident)
        else:
            proof=json.loads((a.output/'verification.json').read_text());assert proof['status']=='PASS' and proof['identity']==ident
            run(cfg['tasks'][a.case_id],cfg,a.output,ident,a.max_stages)


if __name__=='__main__':main()
