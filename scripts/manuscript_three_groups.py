"""User-requested CE/effective-rank/single-trajectory NPG; real Slurm only."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import (atomic_json, dare, evaluate, njit, op, orth,
                           pulse_chunk, require_compute, rng_for, targets, trunc)
from npg_batched_collector import batched_chunk, prepare

NAME = 'manuscript-three-groups-20261027'
BASE = Path('/scratch/user/changze/lqr_experiments')
OUT = BASE/'results'/NAME
CFG = dict(exact_dims=[12,24,48,96], rank=2, approximate_n=16,
    factors=[4,8,16,32,64,128,256], ce_budgets=[256,512,1024,2048,4096,16384,65536],
    ranks=[0,1,2,3,4,6,8,12,16], A_families=['scalar','dense'],
    spectra=['exact','gapped','smooth'], systems=[101,102,103], trials=list(range(100,108)),
    threshold_multiplier=1., H=12, burn_blocks=12, ce_burn=144,
    actor_n=12, eta=1/9, actor_blocks=[2048,8192,32768,131072], stages_per_budget=12,
    SU_cap=12., seed_namespace=27102026)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def identity():
    files=['scripts/manuscript_three_groups.py','scripts/npg_batched_collector.py',
           'dense_scaling.py','docs/MANUSCRIPT_THREE_GROUPS_PROTOCOL_20261027.md']
    return dict(config=CFG,sources={f:sha(ROOT/f) for f in files})


def provenance():
    return dict(job=os.environ['SLURM_JOB_ID'],array=os.environ.get('SLURM_ARRAY_TASK_ID'),
        host=socket.gethostname(),temp=os.environ['TMPDIR'],cache=os.environ['XDG_CACHE_HOME'],
        threads={k:os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']})


def plant(n,family,spectrum,seed):
    u=orth(rng_for(CFG['seed_namespace'],1,n,seed),n)
    v=orth(rng_for(CFG['seed_namespace'],2,n,seed),n)
    a=.5*(np.eye(n) if family=='scalar' else orth(rng_for(CFG['seed_namespace'],3,n,seed),n))
    if spectrum=='exact': singular=np.r_[np.ones(2),np.zeros(n-2)]
    elif spectrum=='gapped': singular=np.r_[np.ones(2),np.full(n-2,.05)]
    else:
        assert spectrum=='smooth'
        singular=.7**np.arange(n)
    b=(u*singular)@v.T
    kstar,pstar=dare(a,b,np.eye(n),np.eye(n))
    p0=solve_discrete_lyapunov(a.T,np.eye(n))
    s=dict(A=a,B=b,Q=np.eye(n),R=np.eye(n),W=np.eye(n),K0=np.zeros((n,n)),
        Kstar=kstar,Jstar=float(np.trace(pstar)),initial_gap=float(np.trace(p0-pstar)))
    cert=dict(n=n,m=n,A_family=family,spectrum=spectrum,system=seed,rank=int(np.count_nonzero(singular)),
        A_op=op(a),B_op=op(b),p0=op(p0),Jstar=s['Jstar'],J0=float(np.trace(p0)),
        initial_gap=s['initial_gap'],singular_values=singular.tolist(),
        tau2=[float(singular[k:]@singular[k:]) for k in range(n+1)])
    return s,v[:,:2] if spectrum=='exact' else None,cert


def assess(s,k,basis):
    q,_=evaluate(s,k)
    if q['stable'] and basis is not None:
        projected=basis@(basis.T@k)
        qp,_=evaluate(s,projected)
        assert qp['stable']
        null=k-projected
        cov=solve_discrete_lyapunov(s['A']-s['B']@k,s['W'])
        redundant=float(np.trace(null@cov@null.T))
        residual=abs(q['cost']-qp['cost']-redundant)
        assert residual<1e-7*max(1.,q['cost'])
        q.update(redundant_cost=redundant,projected_cost=qp['cost'],decomposition_residual=residual)
    return q


@njit(cache=True)
def ce_chunk(a,b,x,pulses,noises):
    count,n=noises.shape
    design=np.empty((count,2*n));outputs=np.empty((count,n))
    for j in range(count):
        design[j,:n]=x;design[j,n:]=pulses[j]
        x=a@x+b@pulses[j]+noises[j]
        outputs[j]=x
    return x,design,outputs


def fit_model(gram,cross):
    theta=np.linalg.solve(gram,cross.T).T
    assert np.linalg.norm(theta@gram-cross)<1e-8*max(1.,np.linalg.norm(cross))
    return theta


def ce_task(spec,dest):
    path=dest/(spec['id']+'.json')
    assert not path.exists(),'No automatic learning replay'
    begin=time.monotonic(); n=spec['n']
    s,basis,cert=plant(n,spec['A_family'],spec['spectrum'],spec['system'])
    family_id=0 if spec['A_family']=='scalar' else 1
    spectrum_id=CFG['spectra'].index(spec['spectrum'])
    rng=rng_for(CFG['seed_namespace'],10,n,family_id,spectrum_id,spec['system'],spec['trial'])
    x=np.zeros(n)
    x,_,_=ce_chunk(s['A'],s['B'],x,rng.normal(size=(CFG['ce_burn'],n)),rng.normal(size=(CFG['ce_burn'],n)))
    budgets=[int(2*n*f) for f in CFG['factors']] if spec['spectrum']=='exact' else CFG['ce_budgets']
    stops=sorted(set(budgets)|{b//2 for b in budgets});saved={};done=0
    gram=np.zeros((2*n,2*n));cross=np.zeros((n,2*n));rows=[];arrays={}
    for stop in stops:
        while done<stop:
            size=min(256,stop-done)
            x,z,y=ce_chunk(s['A'],s['B'],x,rng.normal(size=(size,n)),rng.normal(size=(size,n)))
            gram+=z.T@z;cross+=y.T@z;done+=size
        saved[done]=(gram.copy(),cross.copy())
        if done not in budgets:continue
        theta=fit_model(gram,cross);ah,bh=theta[:,:n],theta[:,n:]
        ga,ca=saved[done//2]
        h1=fit_model(ga,ca)[:,n:];h2=fit_model(gram-ga,cross-ca)[:,n:]
        proxy=op(h1-h2)/2
        sv=np.linalg.svd(bh,compute_uv=False);adaptive=int(np.count_nonzero(sv>CFG['threshold_multiplier']*proxy))
        modes=[('dense',n),('oracle_rank',2)] if spec['spectrum']=='exact' else [('dense',n)]+[('k'+str(k),k) for k in CFG['ranks'] if k<n]
        modes += [('adaptive',adaptive)]
        arrays['theta_'+str(done)]=theta
        arrays['gram_'+str(done)]=gram.copy();arrays['cross_'+str(done)]=cross.copy()
        cache={}
        for mode,k in modes:
            row=dict(mode=mode,k=k,N=done,transitions=done+CFG['ce_burn'],budget_factor=done/(2*n),
                noise_proxy=proxy,threshold=CFG['threshold_multiplier']*proxy if mode=='adaptive' else None,
                B_error_op=op(bh-s['B']),A_error_op=op(ah-s['A']),
                tau2=cert['tau2'][k],bound_shape=k*2*n/done+cert['tau2'][k])
            try:
                if k not in cache:
                    candidate,_=dare(ah,bh if k==n else trunc(bh,k),s['Q'],s['R'])
                    cache[k]=(candidate,assess(s,candidate,basis))
                candidate,q=cache[k]
                row.update(q);arrays[f'K_{done}_{mode}']=candidate
            except (np.linalg.LinAlgError,ValueError,ArithmeticError) as err:
                row.update(stable=False,gap=None,cost=None,failure=type(err).__name__+': '+str(err))
            rows.append(row)
    arrays.update(A=s['A'],B=s['B'],x=x)
    dest.mkdir(parents=True,exist_ok=True);np.savez_compressed(path.with_suffix('.npz'),**arrays)
    result=dict(spec=spec,identity=identity(),provenance=provenance(),certificates=cert,rows=rows,
        actual_transitions=CFG['ce_burn']+done,assigned_transitions=CFG['ce_burn']+max(budgets),
        seconds=time.monotonic()-begin,peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        arrays_sha256=sha(path.with_suffix('.npz')))
    atomic_json(path,result)
    print(json.dumps(dict(id=spec['id'],seconds=result['seconds'],failures=sum(not r['stable'] for r in rows))),flush=True)
    return result


def collect(s,k,x,count,rng,counter):
    n=len(x);h=CFG['H'];burn=CFG['burn_blocks']
    f=np.ascontiguousarray(s['A']-s['B']@k);cost=np.ascontiguousarray(s['Q']+k.T@k)
    # Burn-in follows the same pulse process as the baseline and regression.
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
    return x,z,(burn+1+count)*h,float(np.linalg.cond(gram))


def schedule():
    return [b for b in CFG['actor_blocks'] for _ in range(CFG['stages_per_budget'])]


def actor_task(spec,dest):
    path=dest/(spec['id']+'.json');assert not path.exists(),'No automatic learning replay'
    begin=time.monotonic();n=spec['n'];s,basis,cert=plant(n,spec['A_family'],spec['spectrum'],spec['system'])
    k=s['K0'].copy();x=np.zeros(n);total=0;status='complete';policies=[k.copy()]
    rows=[dict(stage=0,transitions=0,**assess(s,k,basis))];diagnostic=[]
    for stage,count in enumerate(schedule()):
        used=(CFG['burn_blocks']+1+count)*CFG['H']
        counter={'transitions':0}
        try:
            # Method absent from RNG key: paired innovations, separate evolving states.
            rng=rng_for(CFG['seed_namespace'],20,0 if spec['A_family']=='scalar' else 1,
                CFG['spectra'].index(spec['spectrum']),spec['system'],spec['trial'],stage)
            x,z,observed,condition=collect(s,k,x,count,rng,counter);assert used==observed
            total+=counter['transitions'];counter['transitions']=0
            rank=spec['k'] if spec['mode']=='truncated' else n
            zz=z if rank==n else trunc(z,rank)
            if stage==0:
                truth=targets(s,k,CFG['H'])
                for label,estimate in [('dense',z),('truncated',trunc(z,spec['k']))]:
                    diagnostic.append(dict(mode=label,Z_error_op=op(estimate-truth['Z']),
                        Z_error_fro2=float(np.sum((estimate-truth['Z'])**2)),
                        horizon_bias_op=op(truth['ZH']-truth['Z']),
                        **assess(s,k-CFG['eta']*(k+estimate),basis)))
            candidate=k-CFG['eta']*(k+zz)
            q=assess(s,candidate,basis)
            rows.append(dict(stage=stage+1,N=count,transitions=total,retained_rank=rank,gram_condition=condition,**q))
            k=candidate;policies.append(k.copy())
            if not q['stable']:status='unstable';break
        except (np.linalg.LinAlgError,ValueError,ArithmeticError,FloatingPointError) as err:
            total+=counter['transitions']
            status='numerical_failure';rows.append(dict(stage=stage+1,transitions=total,stable=False,gap=None,
                failure=type(err).__name__+': '+str(err)));break
    assigned=sum((CFG['burn_blocks']+1+b)*CFG['H'] for b in schedule())
    dest.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path.with_suffix('.npz'),policies=np.asarray(policies),x=x,A=s['A'],B=s['B'])
    result=dict(spec=spec,identity=identity(),provenance=provenance(),certificates=cert,status=status,rows=rows,
        same_first_blocks_diagnostic=diagnostic,assigned_transitions=assigned,actual_transitions=total,
        seconds=time.monotonic()-begin,peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        arrays_sha256=sha(path.with_suffix('.npz')))
    atomic_json(path,result)
    print(json.dumps(dict(id=spec['id'],status=status,gap=rows[-1].get('gap'),seconds=result['seconds'])),flush=True)
    return result


def specs(system,trial):
    result=[]
    for family in CFG['A_families']:
        for n in CFG['exact_dims']:
            result.append(dict(algorithm='CE',n=n,A_family=family,spectrum='exact'))
        for spectrum in ['gapped','smooth']:
            result.append(dict(algorithm='CE',n=CFG['approximate_n'],A_family=family,spectrum=spectrum))
        for spectrum in CFG['spectra']:
            for mode in ['dense','truncated']:
                result.append(dict(algorithm='NPG',n=CFG['actor_n'],A_family=family,
                    spectrum=spectrum,mode=mode,k=4 if spectrum=='smooth' else 2))
    for i,spec in enumerate(result):
        spec.update(system=system,trial=trial,id=f's{system}-t{trial}-{i:02d}')
    return result


def preflight():
    dest=OUT/'preflight';dest.mkdir(parents=True,exist_ok=True);checks=[];benchmarks=[]
    for family in CFG['A_families']:
        s,basis,cert=plant(12,family,'exact',9001)
        k=rng_for(45,0 if family=='scalar' else 1).normal(size=(12,12))*.01
        q=assess(s,k,basis);assert q['stable']
        checks.append(dict(test='redundant_decomposition',family=family,residual=q['decomposition_residual']))
        rng=rng_for(46);f=s['A']-s['B']@k;cost=s['Q']+k.T@k
        xi=rng.normal(size=(19,12));w=rng.normal(size=(19,12,12));x=rng.normal(size=12)
        serial=pulse_chunk(f,s['B'],cost,x,xi,w)
        batch=batched_chunk(f,s['B'],cost,x,xi,w,prepare(f,s['B'],12))
        for label,a,b in zip(['endpoint','starts','returns'],serial,batch):
            assert np.allclose(a,b,rtol=2e-11,atol=2e-10)
            checks.append(dict(test='sequential_batched_'+label,family=family,error=float(np.max(np.abs(a-b)))))
        assert abs(cert['A_op']-.5)<1e-12 and cert['rank']==2
    for algorithm,n,family,spectrum,mode in [('CE',96,'dense','exact',None),
            ('CE',16,'dense','smooth',None),('NPG',12,'dense','exact','dense')]:
        spec=dict(id='benchmark-'+algorithm+'-'+str(n),algorithm=algorithm,n=n,A_family=family,
            spectrum=spectrum,system=9002,trial=900,mode=mode,k=2)
        value=ce_task(spec,dest) if algorithm=='CE' else actor_task(spec,dest)
        benchmarks.append(dict(algorithm=algorithm,n=n,seconds=value['seconds'],
            peak_rss_KiB=value['peak_rss_KiB'],status=value.get('status','complete')))
    atomic_json(OUT/'preflight.json',dict(status='PASS',checks=checks,benchmarks=benchmarks,
        identity=identity(),provenance=provenance(),planned_tasks=len(specs(101,100))*24))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['preflight','formal']);ap.add_argument('--bundle',type=int)
    args=ap.parse_args();require_compute()
    if args.mode=='preflight':preflight();return
    pre=json.loads((OUT/'preflight.json').read_text());assert pre['status']=='PASS' and pre['identity']==identity()
    pairs=[(s,t) for s in CFG['systems'] for t in CFG['trials']]
    system,trial=pairs[args.bundle]
    for spec in specs(system,trial):
        (ce_task if spec['algorithm']=='CE' else actor_task)(spec,OUT/'raw')


if __name__=='__main__':main()
