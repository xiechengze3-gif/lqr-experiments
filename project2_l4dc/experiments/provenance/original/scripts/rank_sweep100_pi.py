"""Full original-coordinate LSTD policy iteration for the fixed100d rank sweep.

Truth is confined to simulation, oracle references and evaluation. The policy
update receives only the complete fitted critic's action blocks, R and rank.
"""
import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from threadpoolctl import threadpool_limits
import rank_sweep100 as e
from full_lstd_precision import solve, verify as precision_verify
from full_lstd import verify as equation_verify
from dense_scaling import nominal_chunk, ce_chunk, pi_gain

SOURCES=e.SOURCES+['scripts/full_lstd.py','scripts/full_lstd_precision.py',
                   'scripts/rank_sweep100_pi.py','scripts/rank_sweep100_pi_data.py']


def load_system(cfg,rank):
    path=ROOT/'system_inputs'/f'r{rank:03d}.npz'
    assert e.sha(path)==cfg['system_artifact_sha256'][str(rank)]
    with np.load(path,allow_pickle=False) as a:
        return {name:(float(a[name]) if a[name].ndim==0 else a[name].copy())
                for name in ('A','B','Q','R','W','K0','Kstar','Pstar','Jstar','initial_gap')}


def innovations(cfg,seed,stage):
    return e.rng_for(cfg['sampling_seed'],2,seed,stage,0),e.rng_for(cfg['sampling_seed'],2,seed,stage,1)


def collect(s,k,x,count,cfg,seed,stage):
    """Same complete (x,u) observations for paired methods before they fork."""
    n=k.shape[1];pulse_rng,noise_rng=innovations(cfg,seed,stage)
    f=np.ascontiguousarray(s['A']-s['B']@k)
    x,_=nominal_chunk(f,x,noise_rng.normal(size=(cfg['burn'],n)))
    z=np.empty((count,2*n));nxt=np.empty_like(z);costs=np.empty(count)
    for lo in range(0,count,2048):
        size=min(2048,count-lo)
        x,zz,yy=ce_chunk(f,s['B'],k,x,pulse_rng.normal(scale=cfg['sigma'],size=(size,n)),
                         noise_rng.normal(size=(size,n)))
        z[lo:lo+size]=zz;nxt[lo:lo+size,:n]=yy;nxt[lo:lo+size,n:]=-yy@k.T
        costs[lo:lo+size]=np.einsum('ij,ij->i',zz[:,:n]@s['Q'],zz[:,:n])
        costs[lo:lo+size]+=np.einsum('ij,ij->i',zz[:,n:]@s['R'],zz[:,n:])
    return x,z,nxt,costs


def update(g,c,r,method,rank):
    # Full-rank truncation is exactly the identity, with shared arithmetic.
    return pi_gain({'R':r},g,c,None if method=='dense' or rank==r.shape[0] else rank)[0]


def fit(z,nxt,costs,cfg):
    h,diag=solve(z,nxt,costs,rtol=cfg['solver_rtol'],attempts=cfg['solver_attempts'])
    n=z.shape[1]//2
    return h,diag


def estimate(s,k,x,count,cfg,seed,stage,method,identity):
    import rank_sweep100_pi_data as data
    folder=Path(cfg['temp'])/f'stage-{stage:03d}-{method}'
    expected=data.tag(k,x,count,identity)
    fitted=folder/'fit.json'
    if fitted.exists():
        meta=e.read(fitted);assert meta['tag']==expected
        with np.load(folder/'fit.npz',allow_pickle=False) as a:h=a['h'].copy()
        data.release_observations(folder,cfg['temp'])
        return np.array(meta['x']),h,meta['solver'],meta['actual'],folder
    endpoint,z,nxt,costs,used=data.collect(s,k,x,count,cfg,seed,stage,folder,identity)
    h,diag=fit(z,nxt,costs,cfg);del z,nxt,costs
    gc.collect()
    e.save_npz(folder/'fit.npz',h=h if h is not None else np.full((2*len(k),2*len(k)),np.nan))
    e.atomic_json(fitted,dict(tag=expected,x=endpoint.tolist(),solver=diag,actual=used))
    data.release_observations(folder,cfg['temp'])
    return endpoint,h,diag,used,folder


def task(cfg,rank,seed,out,identity):
    import rank_sweep100_pi_data as data
    s=load_system(cfg,rank);n=cfg['n'];out=Path(out);counts=cfg['batch_schedule']
    name=f'pi-r{rank:03d}-s{seed:04d}'
    cfg=dict(cfg,temp=str(Path(cfg['temp'])/name))
    dest=out/'raw'/(name+'.json');cp=out/'checkpoints'/(name+'.npz')
    if dest.exists():
        assert e.read(dest)['identity']==identity
        return dict(rank=rank,seed=seed,reused=True)
    k={m:s['K0'].copy() for m in ('dense','truncated')};x={m:np.zeros(n) for m in k}
    policies={m:[k[m].copy()] for m in k};critics={m:[np.full((2*n,2*n),np.nan)] for m in k}
    failed={m:False for m in k};actual={m:0 for m in k};physical=0;rows=[];first=0;start=time.monotonic()
    if cp.exists():
        with np.load(cp,allow_pickle=False) as a:
            meta=json.loads(str(a['meta']));assert meta['identity']==identity
            first=meta['next_stage'];failed=meta['failed'];actual=meta['actual'];physical=meta['physical'];rows=meta['rows']
            for m in k:
                k[m]=a[m+'_k'].copy();x[m]=a[m+'_x'].copy()
                policies[m]=list(a[m+'_policies']);critics[m]=list(a[m+'_critics'])
        for folder in Path(cfg['temp']).glob('stage-*'):
            if int(folder.name.split('-')[1])<first:data.cleanup(folder,cfg['temp'])
    else:
        rows=[e.quality_row(s,k[m],route='pi',method=m,rank=rank,seed=seed,stage=0,
               transitions=0,actual_transitions=0,observed=True,whole_path_stable=True) for m in k]
    total=sum(count+cfg['burn'] for count in counts[:first])
    for stage in range(first,len(counts)):
        count=counts[stage];total+=count+cfg['burn'];cache=None;folders=[]
        for method in k:
            base=dict(route='pi',method=method,rank=rank,seed=seed,stage=stage+1,
                      training_transitions=count,transitions=total)
            h=np.full((2*n,2*n),np.nan)
            if failed[method]:
                row=dict(base,observed=False,whole_path_stable=False,actual_transitions=actual[method],
                         stable=False,rho=None,cost=None,gap=None,relative_gap=None,failure='prior_failure')
            else:
                before_k=k[method].copy();before_x=x[method].copy()
                try:
                    if cache is not None and np.array_equal(before_k,cache[0]) and np.array_equal(before_x,cache[1]):
                        endpoint,h,diag,used,folder=cache[2]
                    else:
                        endpoint,h,diag,used,folder=estimate(s,before_k,before_x,count,cfg,seed,stage,method,identity)
                        physical+=used;folders.append(folder)
                        cache=(before_k,before_x,(endpoint.copy(),h,diag,used,folder))
                    actual[method]+=used;x[method]=endpoint.copy()
                    row=dict(base,observed=True,whole_path_stable=True,actual_transitions=actual[method],solver=diag)
                    if not diag['converged']:
                        failed[method]=True
                        row.update(whole_path_stable=False,stable=False,rho=None,cost=None,gap=None,
                                   relative_gap=None,failure='numerical_failure')
                    else:
                        g,c=h[n:,n:]-s['R'],h[n:,:n]
                        k[method]=update(g,c,s['R'],method,rank)
                        quality,_=e.evaluate(s,k[method]);row.update(quality)
                        row['failure']=None if quality['stable'] else 'controller_instability'
                        if not quality['stable']:failed[method]=True;row['whole_path_stable']=False
                        # This truth-only diagnostic never selects or changes an update.
                        _,pvalue=e.evaluate(s,before_k)
                        gt=s['B'].T@pvalue@s['B'];ct=s['B'].T@pvalue@s['A']
                        row['joint_estimator_error_fro2']=float(np.sum((g-gt)**2)+np.sum((c-ct)**2))
                        import hashlib
                        row['raw_critic_sha256']=hashlib.sha256(h.tobytes()).hexdigest()
                except (ValueError,np.linalg.LinAlgError,FloatingPointError) as error:
                    failed[method]=True
                    row=dict(base,observed=True,whole_path_stable=False,actual_transitions=actual[method],
                             stable=False,rho=None,cost=None,gap=None,relative_gap=None,
                             failure='numerical_failure',error=repr(error))
            rows.append(row);policies[method].append(k[method].copy())
            critics[method].append(h.copy() if h is not None else np.full((2*n,2*n),np.nan))
        if rank==n:
            np.testing.assert_array_equal(k['dense'],k['truncated']);np.testing.assert_array_equal(x['dense'],x['truncated'])
            np.testing.assert_array_equal(critics['dense'][-1],critics['truncated'][-1])
        arrays={m+suffix:value for m in k for suffix,value in
                (('_k',k[m]),('_x',x[m]),('_policies',np.asarray(policies[m])),('_critics',np.asarray(critics[m])))}
        e.save_npz(cp,meta=json.dumps(dict(identity=identity,next_stage=stage+1,failed=failed,
                    actual=actual,physical=physical,rows=rows)),**arrays)
        for folder in set(folders):data.cleanup(folder,cfg['temp'])
        print(json.dumps(dict(rank=rank,seed=seed,stage=stage+1,transitions=total,
              failed=failed,seconds_this_invocation=time.monotonic()-start)),flush=True)
    policy=out/'policies'/(name+'.npz');critic=out/'critics'/(name+'.npz')
    e.save_npz(policy,**{m:np.asarray(policies[m]) for m in k})
    e.save_npz(critic,**{m:np.asarray(critics[m]) for m in k})
    result=dict(identity=identity,route='pi',rank=rank,seed=seed,records=rows,physical_transitions=physical,
        algorithm_actual_transitions=actual,seconds_this_invocation=time.monotonic()-start,
        policy_sha256=e.sha(policy),critic_sha256=e.sha(critic),slurm_job_id=os.environ.get('SLURM_JOB_ID'))
    e.atomic_json(dest,result)
    return {key:result[key] for key in ('rank','seed','physical_transitions','seconds_this_invocation')}


def verify_runtime(cfg,out,identity):
    """Independent array equality and interruption tests, using excluded seeds."""
    import rank_sweep100_pi_data as data
    proof=dict(equation=equation_verify(),precision=precision_verify())
    oracle_reference(cfg,out,identity)
    s=load_system(cfg,8);mini=dict(cfg,data_chunk=128,burn=7)
    endpoint,z,nxt,costs=collect(s,s['K0'],np.zeros(cfg['n']),512,mini,9004,0)
    folder=Path(cfg['temp'])/'verification-data'/'stage-000-dense'
    interrupted=[False]
    def fault(meta):
        if meta['filled']>=128 and not interrupted[0]:
            interrupted[0]=True;raise RuntimeError('Injected collection interruption after durable chunk')
    try:data.collect(s,s['K0'],np.zeros(cfg['n']),512,mini,9004,0,folder,identity,hook=fault)
    except RuntimeError as error:assert str(error).startswith('Injected collection')
    assert interrupted[0]
    a,zz,nn,cc,used=data.collect(s,s['K0'],np.zeros(cfg['n']),512,mini,9004,0,folder,identity)
    np.testing.assert_array_equal(a,endpoint);np.testing.assert_array_equal(zz,z)
    np.testing.assert_allclose(nn,nxt,rtol=2e-13,atol=2e-13)
    np.testing.assert_allclose(cc,costs,rtol=2e-13,atol=2e-13);assert used==519
    del zz,nn,cc,z,nxt,costs;data.cleanup(folder,cfg['temp'])
    # Check the actual larger production I/O chunk against the original
    # collector without restricting or transforming the critic coordinates.
    chunk_count=16384;chunk_cfg=dict(cfg,burn=7)
    endpoint,z,nxt,costs=collect(s,s['K0'],np.zeros(cfg['n']),chunk_count,chunk_cfg,9007,0)
    folder=Path(cfg['temp'])/'verification-large-chunk'/'stage-000-dense'
    a,zz,nn,cc,used=data.collect(s,s['K0'],np.zeros(cfg['n']),chunk_count,chunk_cfg,9007,0,folder,identity)
    np.testing.assert_array_equal(a,endpoint);np.testing.assert_array_equal(zz,z)
    np.testing.assert_allclose(nn,nxt,rtol=2e-13,atol=2e-13)
    np.testing.assert_allclose(cc,costs,rtol=2e-13,atol=2e-13)
    assert used==chunk_count+7
    del zz,nn,cc,z,nxt,costs;data.cleanup(folder,cfg['temp'])
    # A full100d policy update must also survive an interruption immediately
    # after its atomic stage checkpoint, retaining exact policies and counts.
    testcfg=dict(cfg,batch_schedule=[32768],temp=str(Path(cfg['temp'])/'verification-update'))
    reference=out/'diagnostics'/'uninterrupted';resumed=out/'diagnostics'/'interrupted'
    task(testcfg,100,9005,reference,identity)
    saved=e.save_npz;faulted=[False]
    def save_then_interrupt(path,**arrays):
        saved(path,**arrays)
        if Path(path).parent.name=='checkpoints' and not faulted[0]:
            faulted[0]=True;raise RuntimeError('Injected interruption after PI checkpoint')
    # Use a separate temporary dataset root for the second complete run.
    second=dict(testcfg,temp=str(Path(cfg['temp'])/'verification-update-resumed'))
    saved_json=e.atomic_json;fit_fault=[False]
    def save_fit_then_interrupt(path,value):
        saved_json(path,value)
        if Path(path).name=='fit.json' and not fit_fault[0]:
            fit_fault[0]=True;raise RuntimeError('Injected interruption after fitted critic')
    e.atomic_json=save_fit_then_interrupt
    try:task(second,100,9005,resumed,identity)
    except RuntimeError as error:assert str(error).startswith('Injected interruption')
    finally:e.atomic_json=saved_json
    assert fit_fault[0]
    saved_fit=globals()['fit']
    def forbidden_refit(*args,**kwargs):raise AssertionError('Resume repeated a completed LSTD solve')
    globals()['fit']=forbidden_refit
    e.save_npz=save_then_interrupt
    try:task(second,100,9005,resumed,identity)
    except RuntimeError as error:assert str(error).startswith('Injected interruption')
    finally:e.save_npz=saved
    assert faulted[0]
    try:task(second,100,9005,resumed,identity)
    finally:globals()['fit']=saved_fit
    d=e.read(next((reference/'raw').glob('*.json')));r=e.read(next((resumed/'raw').glob('*.json')))
    def science(value):
        if isinstance(value,dict):return {key:science(v) for key,v in value.items() if key!='seconds'}
        if isinstance(value,list):return [science(v) for v in value]
        return value
    assert science(d['records'])==science(r['records'])
    for key in ('physical_transitions','algorithm_actual_transitions'):assert d[key]==r[key]
    for kind in ('policies','critics'):
        with np.load(next((reference/kind).glob('*.npz')),allow_pickle=False) as aa,np.load(next((resumed/kind).glob('*.npz')),allow_pickle=False) as bb:
            for key in aa.files:np.testing.assert_array_equal(aa[key],bb[key])
    proof.update(status='PASS',identity=identity,chunk_checkpoint_resume=True,full_update_checkpoint_resume=True,
        fitted_critic_resume_without_resolve=True,scientific_records_exact_excluding_measured_wall_seconds=True,
        original_data_match=True,full_rank_bitwise_policy_and_critic=True,
        large_production_chunk_matches_original_observations=True,
        primitive_transitions=2*519+2*(chunk_count+7)+d['physical_transitions']+r['physical_transitions'],
        note='All data-collection and full-update tests use excluded seeds9004/9005/9007')
    e.atomic_json(out/'verification.json',proof)


def oracle_reference(cfg,out,identity):
    references=[]
    for rank in cfg['ranks']:
        s=load_system(cfg,rank);k=s['K0'].copy()
        for stage in range(cfg['oracle_updates']+1):
            q,p=e.evaluate(s,k);assert q['stable']
            references.append(dict(rank=rank,stage=stage,**q))
            g=s['B'].T@p@s['B'];c=s['B'].T@p@s['A']
            dense=update(g,c,s['R'],'dense',rank);truncated=update(g,c,s['R'],'truncated',rank)
            np.testing.assert_allclose(dense,truncated,atol=2e-12)
            k=dense
        assert references[-1]['gap']<cfg['epsilon']/10
    e.atomic_json(out/'oracle.json',dict(status='PASS',references=references,identity=identity))


def preflight(cfg,out,identity):
    proof=dict(equation=equation_verify(),precision=precision_verify())
    oracle_reference(cfg,out,identity)
    rows=[]
    for rank in cfg['preflight_ranks']:
        s=load_system(cfg,rank)
        for count in cfg['preflight_counts']:
            start=time.monotonic()
            endpoint,z,nxt,costs=collect(s,s['K0'],np.zeros(cfg['n']),count,cfg,cfg['preflight_seed'],0)
            collect_seconds=time.monotonic()-start
            h,diag=fit(z,nxt,costs,cfg);del z,nxt,costs
            gc.collect()
            row=dict(rank=rank,count=count,collect_seconds=collect_seconds,solver=diag,
                     primitive_transitions=count+cfg['burn'],seconds=time.monotonic()-start)
            if diag['converged']:
                g,c=h[cfg['n']:,cfg['n']:]-s['R'],h[cfg['n']:,:cfg['n']]
                for method in ('dense','truncated'):
                    candidate=update(g,c,s['R'],method,rank);q,_=e.evaluate(s,candidate)
                    row[method]=q
            rows.append(row)
            e.atomic_json(out/'preflight_progress.json',dict(rows=rows,identity=identity))
            print(json.dumps(row),flush=True)
    import resource
    e.atomic_json(out/'preflight.json',dict(status='COMPLETE',identity=identity,checks=proof,rows=rows,
        primitive_transitions=sum(r['primitive_transitions'] for r in rows),
        peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        slurm_job_id=os.environ['SLURM_JOB_ID']))


def freeze(cfg,manifest,out,identity):
    import shutil
    frozen=out/'frozen'
    if (frozen/'identity.json').exists():assert e.read(frozen/'identity.json')==identity;return
    frozen.mkdir(parents=True,exist_ok=True)
    for name in SOURCES:
        dest=frozen/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    shutil.copytree(ROOT/'system_inputs',frozen/'system_inputs',dirs_exist_ok=True)
    shutil.copyfile(manifest,frozen/'config.json');e.atomic_json(frozen/'identity.json',identity)


def verify_maximum_memory(cfg,out,identity):
    import resource
    maximum=max(cfg['batch_schedule'])
    counts=cfg.get('memory_verification_schedule',[maximum,maximum])
    assert max(counts)==maximum and len(counts)>=2
    testcfg=dict(cfg,batch_schedule=counts,temp=str(Path(cfg['temp'])/'maximum-memory'))
    folder=out/'diagnostics'/'maximum-memory'
    result=task(testcfg,2,9006,folder,identity)
    raw=e.read(folder/'raw'/'pi-r002-s9006.json')
    assert all(r['failure'] is None for r in raw['records'])
    e.atomic_json(out/'maximum_memory_verification.json',dict(status='PASS',identity=identity,
        maximum_training_batch=maximum,verification_schedule=counts,consecutive_updates=len(counts),rank=2,excluded_seed=9006,
        peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        physical_transitions=raw['physical_transitions'],
        algorithm_actual_transitions=raw['algorithm_actual_transitions'],
        slurm_job_id=os.environ['SLURM_JOB_ID']))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','verify','task']);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--phase',choices=['pilot','confirm'],default='pilot');p.add_argument('--task-id',type=int,default=0)
    a=p.parse_args();cfg=e.read(a.manifest)
    assert os.environ.get('SLURM_JOB_ID'),'Numerical execution requires an actual Slurm compute allocation'
    for name,path in [('NUMBA_CACHE_DIR',str(Path(cfg['cache'])/'numba')),
                      ('MPLCONFIGDIR',str(Path(cfg['cache'])/'matplotlib')),('TMPDIR',cfg['temp'])]:
        assert os.environ.get(name)==path,(name,path);Path(path).mkdir(parents=True,exist_ok=True)
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    identity=dict(manifest_sha256=e.sha(a.manifest),sources={name:e.sha(ROOT/name) for name in SOURCES},
                  algorithm='full_original_coordinate_LSTD_PI',whitening=False,low_rank_critic=False)
    if not (out/'resolved_config.json').exists():e.atomic_json(out/'resolved_config.json',dict(cfg,identity=identity))
    else:assert e.read(out/'resolved_config.json')['identity']==identity
    with threadpool_limits(limits=1):
        if a.mode=='preflight':preflight(cfg,out,identity)
        elif a.mode=='verify':
            freeze(cfg,a.manifest,out,identity)
            if (out/'verification.json').exists():assert e.read(out/'verification.json')['identity']==identity
            else:verify_runtime(cfg,out,identity)
            if (out/'maximum_memory_verification.json').exists():assert e.read(out/'maximum_memory_verification.json')['identity']==identity
            else:verify_maximum_memory(cfg,out,identity)
        else:
            assert e.read(out/'verification.json')['status']=='PASS'
            assert e.read(out/'maximum_memory_verification.json')['status']=='PASS'
            jobs=[(rank,seed) for seed in cfg[a.phase+'_seeds'] for rank in cfg['ranks']]
            rank,seed=jobs[a.task_id]
            print(json.dumps(task(cfg,rank,seed,out,identity)),flush=True)


if __name__=='__main__':main()
