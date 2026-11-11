"""Approved supplement: unchanged learner definitions, continuous trajectories, no truth selection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import atomic_json,dare,evaluate,op,orth,pulse_chunk,require_compute,rng_for,targets,trunc
from manuscript_three_groups import ce_chunk,fit_model,plant as old_plant,collect as old_collect
from npg_batched_collector import batched_chunk,prepare
from ce_npg_argument_grid import CFG,CFG_PATH,NAME,OUT,OLD,specs,bundles,all_specs,schedule

SPECTRUM_KEYS={'exact':0,'gapped':1,'smooth':2,'gapped001':3,'gapped02':4,'flat':5}
ERRORS=(np.linalg.LinAlgError,ValueError,ArithmeticError,FloatingPointError)
DIAGNOSTIC_STAGES={1,24,48}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity():
    paths=['scripts/ce_npg_argument_grid.py','scripts/ce_npg_argument_run.py',
        'scripts/manuscript_three_groups.py','scripts/npg_batched_collector.py','dense_scaling.py',
        'configs/ce_npg_argument_revision_20261027.json','docs/CE_NPG_ARGUMENT_PROTOCOL_20261027.md']
    return dict(study=NAME,sources={p:sha(ROOT/p) for p in paths})


def provenance():
    return dict(job=os.environ['SLURM_JOB_ID'],array=os.environ.get('SLURM_ARRAY_TASK_ID'),
        host=socket.gethostname(),temp=os.environ['TMPDIR'],cache=os.environ['XDG_CACHE_HOME'],
        cpus=os.environ.get('SLURM_CPUS_PER_TASK'),threads={k:os.environ.get(k) for k in
        ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']})


def plant(spec):
    n=spec['n'];rank=spec['r'];seed=spec['system'];spectrum=spec['spectrum']
    namespace=CFG['plant_seed_namespace']
    u=orth(rng_for(namespace,1,n,seed),n);v=orth(rng_for(namespace,2,n,seed),n)
    a=.5*(np.eye(n) if spec['A_family']=='scalar' else orth(rng_for(namespace,3,n,seed),n))
    if spectrum=='exact':singular=np.r_[np.ones(rank),np.zeros(n-rank)]
    elif spectrum in ['gapped','gapped001','gapped02']:
        tail={'gapped':.05,'gapped001':.01,'gapped02':.2}[spectrum]
        singular=np.r_[np.ones(2),np.full(n-2,tail)]
    elif spectrum=='smooth':singular=.7**np.arange(n)
    elif spectrum=='flat':singular=np.ones(n)
    else:raise ValueError(spectrum)
    b=(u*singular)@v.T
    kstar,pstar=dare(a,b,np.eye(n),np.eye(n));p0=solve_discrete_lyapunov(a.T,np.eye(n))
    s=dict(A=a,B=b,Q=np.eye(n),R=np.eye(n),W=np.eye(n),K0=np.zeros((n,n)),
        Kstar=kstar,Jstar=float(np.trace(pstar)),initial_gap=float(np.trace(p0-pstar)),P0=p0)
    cert=dict(n=n,m=n,true_rank=int(np.count_nonzero(singular)),A_op=op(a),B_op=op(b),
        p0=op(p0),J0=float(np.trace(p0)),Jstar=s['Jstar'],initial_gap=s['initial_gap'],
        singular_values=singular.tolist(),tau2=[float(singular[k:]@singular[k:]) for k in range(n+1)],
        beta=[float(singular[k]) if k<n else 0. for k in range(n+1)])
    return s,v[:,:rank] if spectrum=='exact' else None,cert


def assess(s,k,basis):
    row,p=evaluate(s,k)
    if row['stable']:
        # P0=(4/3)I for both independently constructed A families.
        ratio=float(np.linalg.eigvalsh((p+p.T)/2).max()/(4/3))
        row.update(P_relative_max=ratio,NPG_containment=ratio<=2+1e-9,CE_containment=ratio<=4+1e-9)
        if basis is not None:
            projected=basis@(basis.T@k);qp,_=evaluate(s,projected);assert qp['stable']
            cov=solve_discrete_lyapunov(s['A']-s['B']@k,s['W'])
            null=k-projected;redundant=float(np.trace(null@cov@null.T))
            residual=abs(row['cost']-qp['cost']-redundant)
            assert residual<1e-7*max(1.,row['cost'])
            row.update(redundant_cost=redundant,projected_cost=qp['cost'],
                projected_gap=qp['gap'],decomposition_residual=residual)
    return row


def collect(s,k,x,count,rng,counter):
    n=len(x);h=12;burn=12
    f=np.ascontiguousarray(s['A']-s['B']@k);cost=np.ascontiguousarray(s['Q']+k.T@k)
    x,_,_=pulse_chunk(f,s['B'],cost,x,rng.normal(size=(burn,n)),rng.normal(size=(burn,h,n)))
    counter['transitions']+=burn*h
    x,_,returns=pulse_chunk(f,s['B'],cost,x,rng.normal(size=(1,n)),rng.normal(size=(1,h,n)))
    counter['transitions']+=h
    previous=returns[-1];prepared=prepare(f,s['B'],h)
    gram=np.zeros((n,n));cross=np.zeros((n,n));done=0
    while done<count:
        size=min(256,count-done)
        pulses=rng.normal(size=(size,n));noises=rng.normal(size=(size,h,n))
        x,starts,returns=batched_chunk(f,s['B'],cost,x,pulses,noises,prepared)
        counter['transitions']+=size*h
        delta=np.diff(np.r_[previous,returns]);previous=returns[-1]
        labels=-pulses*delta[:,None]/2
        gram+=starts.T@starts;cross+=labels.T@starts;done+=size
    z=np.linalg.solve(gram,cross.T).T
    assert np.linalg.norm(z@gram-cross)<1e-8*max(1.,np.linalg.norm(cross))
    return x,z,float(np.linalg.cond(gram)),gram,cross


def seed_for(spec,stage=None):
    parts=[CFG['plant_seed_namespace'],10 if stage is None else 20]
    if stage is None:parts.append(spec['n'])
    parts += [0 if spec['A_family']=='scalar' else 1,SPECTRUM_KEYS[spec['spectrum']],spec['system'],spec['trial']]
    if stage is not None:parts.append(stage)
    return rng_for(*parts)


def atomic_npz(path,**arrays):
    path=Path(path);tmp=path.with_name(path.stem+'.tmp.npz')
    np.savez_compressed(tmp,**arrays);tmp.replace(path)


def ce_task(spec,dest):
    dest.mkdir(parents=True,exist_ok=True);path=dest/(spec['id']+'.json')
    assert not path.exists(),'No learning replay'
    begin=time.monotonic();s,basis,cert=plant(spec);n=spec['n'];rng=seed_for(spec)
    x=np.zeros(n);x,_,_=ce_chunk(s['A'],s['B'],x,rng.normal(size=(144,n)),rng.normal(size=(144,n)))
    budgets=[2*n*f for f in CFG['exact']['CE_factors_N_over_n_plus_m']] if spec['spectrum']=='exact' else CFG['approximate_core']['CE_prefixes']
    stops=sorted(set(budgets)|{b//2 for b in budgets});gram=np.zeros((2*n,2*n));cross=np.zeros((n,2*n))
    saved={};done=0;rows=[];arrays={}
    for stop in stops:
        while done<stop:
            size=min(256,stop-done)
            x,z,y=ce_chunk(s['A'],s['B'],x,rng.normal(size=(size,n)),rng.normal(size=(size,n)))
            gram+=z.T@z;cross+=y.T@z;done+=size
        saved[done]=(gram.copy(),cross.copy())
        if done not in budgets:continue
        theta=fit_model(gram,cross);ah,bh=theta[:,:n],theta[:,n:]
        g1,c1=saved[done//2];h1=fit_model(g1,c1)[:,n:];h2=fit_model(gram-g1,cross-c1)[:,n:]
        proxy=op(h1-h2)/2;adaptive=int(np.count_nonzero(np.linalg.svd(bh,compute_uv=False)>proxy))
        modes=[('dense',n),('truncated',spec['r'])] if spec['spectrum']=='exact' else [('dense',n)]+[('k'+str(k),k) for k in CFG['approximate_core']['fixed_ranks'] if k<n]
        modes += [('adaptive',adaptive)];cache={}
        arrays['theta_'+str(done)]=theta;arrays['gram_'+str(done)]=gram.copy();arrays['cross_'+str(done)]=cross.copy()
        for mode,k in modes:
            row=dict(mode=mode,k=k,N=done,transitions=done+144,noise_proxy=proxy,
                threshold=proxy if mode=='adaptive' else None,tau2=cert['tau2'][k],beta=cert['beta'][k],
                B_error_op=op(bh-s['B']),A_error_op=op(ah-s['A']))
            try:
                if k not in cache:
                    candidate,_=dare(ah,bh if k==n else trunc(bh,k),s['Q'],s['R'])
                    cache[k]=(candidate,assess(s,candidate,basis))
                candidate,q=cache[k];row.update(q);arrays[f'K_{done}_{mode}']=candidate
            except ERRORS as err:
                row.update(stable=False,gap=None,cost=None,failure=type(err).__name__+': '+str(err))
            rows.append(row)
    arrays.update(A=s['A'],B=s['B'],x=x)
    atomic_npz(path.with_suffix('.npz'),**arrays)
    result=dict(spec=spec,identity=identity(),provenance=provenance(),certificates=cert,rows=rows,status='complete',
        actual_transitions=144+done,assigned_transitions=144+max(budgets),seconds=time.monotonic()-begin,
        peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,arrays_sha256=sha(path.with_suffix('.npz')))
    atomic_json(path,result);print(json.dumps(dict(id=spec['id'],seconds=result['seconds'])),flush=True)
    return result


def actor_task(spec,dest):
    dest.mkdir(parents=True,exist_ok=True);path=dest/(spec['id']+'.json')
    checkpoint=dest/(spec['id']+'.checkpoint.json')
    assert not path.exists() and not checkpoint.exists(),'No automatic learning replay, inspect checkpoint first'
    begin=time.monotonic();s,basis,cert=plant(spec);n=spec['n'];k=s['K0'].copy();x=np.zeros(n)
    total=0;policies=[k.copy()];rows=[dict(stage=0,transitions=0,**assess(s,k,basis))];diagnostics=[];arrays={}
    status='complete'
    for stage,count in enumerate(schedule()):
        counter={'transitions':0};used=(12+1+count)*12
        rng=seed_for(spec,stage);k_before=k.copy();x_before=x.copy()
        atomic_json(checkpoint,dict(spec=spec,identity=identity(),next_stage=stage+1,
            stage_inflight=True,committed_transitions=total,rows=rows,diagnostics=diagnostics,
            provenance=provenance(),automatic_replay_allowed=False))
        try:
            x,z,condition,gram,cross=collect(s,k,x,count,rng,counter)
            assert used==counter['transitions'];total+=counter['transitions'];counter['transitions']=0
            if stage+1 in DIAGNOSTIC_STAGES:
                truth=targets(s,k,12);sv=np.linalg.svd(truth['Z'],compute_uv=False)
                diagnostic_k=spec['r'] if spec['spectrum']=='exact' else (2 if spec['mode']=='dense' else spec['k'])
                for label,estimate in [('dense',z),('truncated',trunc(z,diagnostic_k))]:
                    diagnostics.append(dict(stage=stage+1,transitions=total,mode=label,k=diagnostic_k,
                        source_mode=spec['mode'],Z_error_op=op(estimate-truth['Z']),
                        Z_error_fro2=float(np.sum((estimate-truth['Z'])**2)),
                        Z_tail_fro2=float(sv[diagnostic_k:]@sv[diagnostic_k:]),
                        horizon_bias_op=op(truth['ZH']-truth['Z']),
                        **assess(s,k-(1/9)*(k+estimate),basis)))
                for label,value in [('K_before',k_before),('state_before',x_before),('Zhat',z),('gram',gram),('cross',cross)]:
                    arrays[f'{label}_{stage+1}']=value
                arrays[f'rng_after_{stage+1}']=np.asarray(json.dumps(rng.bit_generator.state))
            zz=z if spec['k']==n else trunc(z,spec['k'])
            candidate=k-(1/9)*(k+zz);q=assess(s,candidate,basis)
            rows.append(dict(stage=stage+1,N=count,transitions=total,retained_rank=spec['k'],
                gram_condition=condition,**q));k=candidate;policies.append(k.copy())
            atomic_npz(checkpoint.with_suffix('.npz'),policies=np.asarray(policies),k=k,x=x,**arrays)
            atomic_json(checkpoint,dict(spec=spec,identity=identity(),next_stage=stage+2,stage_inflight=False,
                committed_transitions=total,rows=rows,diagnostics=diagnostics,provenance=provenance(),automatic_replay_allowed=False))
            if not q['stable']:status='unstable';break
        except ERRORS as err:
            total+=counter['transitions'];status='numerical_failure'
            rows.append(dict(stage=stage+1,transitions=total,stable=False,gap=None,
                failure=type(err).__name__+': '+str(err)));break
    atomic_npz(path.with_suffix('.npz'),policies=np.asarray(policies),x=x,A=s['A'],B=s['B'],**arrays)
    result=dict(spec=spec,identity=identity(),provenance=provenance(),certificates=cert,status=status,rows=rows,
        same_blocks_diagnostic=diagnostics,assigned_transitions=sum((13+b)*12 for b in schedule()),
        actual_transitions=total,seconds=time.monotonic()-begin,
        peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,arrays_sha256=sha(path.with_suffix('.npz')))
    atomic_json(path,result)
    print(json.dumps(dict(id=spec['id'],status=status,seconds=result['seconds'],actual_transitions=total)),flush=True)
    return result


def verify_reuse():
    """Read old raw files without modifying or replaying them; verify both provenance and saved plants."""
    from manuscript_three_groups import identity as old_identity
    verified=[]
    for spec in all_specs():
        if spec['reuse_id'] is None:continue
        path=OLD/'raw'/(spec['reuse_id']+'.json');data=json.loads(path.read_text())
        assert data['identity']==old_identity(),('old frozen identity',path)
        assert sha(path.with_suffix('.npz'))==data['arrays_sha256'],('arrays hash',path)
        old=data['spec']
        for key in ['algorithm','n','A_family','spectrum','system','trial']:assert old[key]==spec[key],(key,path)
        if spec['algorithm']=='NPG':assert old['mode']==spec['mode'] and old['k']==2
        s,basis,cert=plant(spec)
        with np.load(path.with_suffix('.npz'),allow_pickle=False) as arr:
            assert np.array_equal(s['A'],arr['A']) and np.array_equal(s['B'],arr['B']),('plant mismatch',path)
            if spec['algorithm']=='NPG':assert len(arr['policies'])==len(data['rows'])
        expected=sum((13+b)*12 for b in schedule()) if spec['algorithm']=='NPG' else max(
            [2*spec['n']*f for f in CFG['exact']['CE_factors_N_over_n_plus_m']] if spec['spectrum']=='exact' else CFG['approximate_core']['CE_prefixes'])+144
        assert data['assigned_transitions']==expected,(expected,path)
        verified.append(dict(id=spec['id'],reuse_id=spec['reuse_id'],json_sha256=sha(path),
            arrays_sha256=data['arrays_sha256'],actual_transitions=data['actual_transitions']))
    assert len(verified)==336
    atomic_json(OUT/'reuse-audit.json',dict(status='PASS',verified=verified,count=len(verified),
        identity=identity(),provenance=provenance()))
    return len(verified)


def preflight():
    dest=OUT/'preflight';dest.mkdir(parents=True,exist_ok=True);checks=[];benchmarks=[]
    reused=verify_reuse()
    for n in [12,16,48]:
        spec=dict(n=n,r=2,A_family='dense',spectrum='exact',system=9001,trial=900)
        s,basis,_=plant(spec);old,_,_=old_plant(n,'dense','exact',9001)
        assert np.array_equal(s['A'],old['A']) and np.array_equal(s['B'],old['B'])
        k=np.zeros((n,n));x0=np.arange(n)/n
        a,b={'transitions':0},{'transitions':0}
        old_value=old_collect(s,k,x0.copy(),521,rng_for(889,n),a)
        new_value=collect(s,k,x0.copy(),521,rng_for(889,n),b)
        assert a==b and a['transitions']==(521+13)*12
        for label,x,y in [('endpoint',old_value[0],new_value[0]),('Zhat',old_value[1],new_value[1])]:
            assert np.array_equal(x,y),(n,label)
            checks.append(dict(n=n,test='old_new_'+label,exact_match=True))
        _,p=evaluate(s,k);assert np.allclose(p,s['P0'],rtol=1e-12,atol=1e-12)
        noise=rng_for(892,n).normal(size=(n,n))*.01
        q=assess(s,noise,basis);checks.append(dict(n=n,test='decomposition',residual=q['decomposition_residual']))
    candidates=[dict(algorithm='NPG',n=n,r=2,k=k,mode='dense' if k==n else 'truncated',
        A_family='dense',spectrum='exact',system=9002,trial=900) for n in [16,24,48] for k in [2,n]]
    candidates += [dict(algorithm='CE',n=n,r=rank,A_family='dense',spectrum=spectrum,system=9002,trial=900)
        for n,rank,spectrum in [(24,8,'exact'),(16,16,'flat')]]
    for i,spec in enumerate(candidates):
        spec.update(id='benchmark-'+str(i),reuse_id=None)
        value=(ce_task if spec['algorithm']=='CE' else actor_task)(spec,dest)
        benchmarks.append(dict(algorithm=spec['algorithm'],n=spec['n'],k=spec.get('k'),
            seconds=value['seconds'],peak_rss_KiB=value['peak_rss_KiB'],status=value['status'],
            actual_transitions=value['actual_transitions'],assigned_transitions=value['assigned_transitions']))
    # The full-rank system is the actual second major workload, not only an exact-rank proxy.
    spec=dict(id='benchmark-fullrank',algorithm='NPG',n=16,r=16,k=16,mode='dense',
        A_family='dense',spectrum='smooth',system=9002,trial=900,reuse_id=None)
    value=actor_task(spec,dest);benchmarks.append(dict(algorithm='NPG',n=16,k=16,spectrum='smooth',
        seconds=value['seconds'],peak_rss_KiB=value['peak_rss_KiB'],status=value['status'],
        actual_transitions=value['actual_transitions'],assigned_transitions=value['assigned_transitions']))
    atomic_json(OUT/'preflight.json',dict(status='PASS',checks=checks,benchmarks=benchmarks,reused=reused,
        expected_new=1728,identity=identity(),provenance=provenance()))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['preflight','formal','audit'])
    ap.add_argument('--bundle',type=int);args=ap.parse_args();require_compute()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.mode=='preflight':preflight();return
    if args.mode=='audit':print(verify_reuse());return
    pre=json.loads((OUT/'preflight.json').read_text());assert pre['status']=='PASS' and pre['identity']==identity()
    s,t=bundles()[args.bundle]
    for spec in specs(s,t):
        if spec['reuse_id'] is not None:continue
        (ce_task if spec['algorithm']=='CE' else actor_task)(spec,OUT/'raw')


if __name__=='__main__':main()
