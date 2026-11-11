"""Frozen final-story experiments. Numerical execution requires real Slurm."""
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
from dense_scaling import (atomic_json, ce_chunk, dare, evaluate, nominal_chunk, njit,
                           op, orth, psd, require_compute, rng_for, targets, trunc)
from project2_overnight import collect_prefixes, greedy, v4_correct

NAME = 'final-story-20261024'
BASE = Path('/scratch/user/changze/lqr_experiments')
OUT = BASE/'results'/NAME
KS = [0, 1, 2, 3, 4, 5, 6, 8, 10, 12]
BUDGETS = [2048, 8192, 32768, 131072]
CFG = dict(n=12, rank=2, ms=[3,6,9,12], eta=1/9, H=12, burn=132,
           stages=64, budgets=BUDGETS, ranks=KS, e1_final=32768,
           systems=[101,102,103], trials=list(range(100,108)),
           calibration_systems=[9001,9002], calibration_trials=[900,901],
           multipliers=[.5,1.,2.], ce_budgets=[512,2048,8192,32768,131072],
           c_eff_operational=1., epsilons=[.5,.1,.02,.005,.001], SU_cap=12.)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def identity():
    files = ['scripts/final_story.py','scripts/project2_overnight.py',
             'scripts/direct_stein_final.py','scripts/npg_batched_collector.py',
             'dense_scaling.py','docs/FINAL_STORY_PROTOCOL_20261024.md']
    return dict(config=CFG, sources={p:sha(ROOT/p) for p in files})


def provenance():
    return dict(job=os.environ['SLURM_JOB_ID'], array_task=os.environ.get('SLURM_ARRAY_TASK_ID'),
                host=socket.gethostname(), threads={k:os.environ.get(k) for k in
                ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']},
                temp=os.environ['TMPDIR'], cache=os.environ['XDG_CACHE_HOME'])


def schedule(final):
    return [final//8]*16+[final//4]*16+[final//2]*16+[final]*16


def assigned(final):
    return sum(CFG['burn']+(count+1)*CFG['H'] for count in schedule(final))


def plant(family, seed, m=12):
    n = CFG['n']; r = CFG['rank']
    u = orth(rng_for(246100,seed),n)
    v = orth(rng_for(246101,seed,m),m)
    if family == 'E1':
        singular = np.r_[np.ones(r),np.zeros(min(n,m)-r)]
        a = .5*np.eye(n)
        b = u[:,:r]@v[:,:r].T
        h = rng_for(246102,seed).normal(size=n); h /= np.linalg.norm(h)
        k0 = .25*np.outer(v[:,r],h)
    else:
        assert family == 'E2' and m == n
        singular = .6**np.arange(n)
        a = .7*np.eye(n)
        b = (u*singular)@v.T
        k0 = np.zeros((m,n))
    ks,pstar = dare(a,b,np.eye(n),np.eye(m))
    p0 = solve_discrete_lyapunov((a-b@k0).T,np.eye(n)+k0.T@k0)
    s = dict(A=a,B=b,Q=np.eye(n),R=np.eye(m),W=np.eye(n),K0=k0,
             Kstar=ks,Jstar=float(np.trace(pstar)),initial_gap=float(np.trace(p0-pstar)))
    sensitivity = pstar@(a-b@ks)
    spec = np.linalg.svd(sensitivity,compute_uv=False)
    cert = dict(family=family,system=seed,n=n,m=m,rank=int(np.count_nonzero(singular)),
                p0=op(p0),q=1.,mu_minus=1.,mu_plus=1.,w_minus=1.,w_plus=1.,
                b_B=float(singular[0]),J0=float(np.trace(p0)),Jstar=s['Jstar'],
                initial_gap=s['initial_gap'],Pstar_Fstar_fro2=float(np.sum(spec**2)),
                sensitivity_stable_rank=float(np.sum(spec**2)/spec[0]**2),
                K0_null_fro=op(k0) if family=='E1' else 0.,spectrum=singular.tolist(),
                tails=[dict(k=k,beta_k=float(singular[k]) if k<len(singular) else 0.,
                            tau_k2=float(np.sum(singular[k:]**2))) for k in range(len(singular)+1)],
                effective_ranks=[dict(epsilon=e,c_eff=CFG['c_eff_operational'],
                    k_epsilon=next(k for k in range(1,len(singular)+1)
                        if np.sum(singular[k:]**2)<=CFG['c_eff_operational']*e)) for e in CFG['epsilons']])
    return s, v[:,:r], cert


def assess(s,k,basis=None):
    q,_ = evaluate(s,k)
    if not q['stable']:
        return q
    if basis is not None:
        kn = k-basis@(basis.T@k)
        f = s['A']-s['B']@k
        cov = solve_discrete_lyapunov(f,s['W'])
        q['redundant_cost'] = float(np.trace(kn@cov@kn.T))
        ke = k-kn
        qe,_ = evaluate(s,ke)
        assert qe['stable']
        q['decomposition_residual'] = abs(q['cost']-qe['cost']-q['redundant_cost'])
        assert q['decomposition_residual'] < 1e-7*max(1.,q['cost'])
    return q


def npg_projection(z,mode,k,mult,halves):
    singular = np.linalg.svd(z,compute_uv=False)
    threshold = None
    proxy = op(halves[0][1]-halves[1][1])/2
    if mode == 'adaptive':
        threshold = mult*proxy
        retained = int(np.count_nonzero(singular>threshold))
    else:
        retained = min(k,len(singular))
    return (z.copy() if retained==len(singular) else trunc(z,retained)), retained, threshold, proxy


@njit(cache=True)
def rectangular_ce_chunk(f,b,k,x,pulses,noises):
    count,n=noises.shape
    m=pulses.shape[1]
    design=np.empty((count,n+m));outputs=np.empty((count,n))
    for j in range(count):
        design[j,:n]=x
        design[j,n:]=-k@x+pulses[j]
        x=f@x+b@pulses[j]+noises[j]
        outputs[j]=x
    return x,design,outputs


def actor(spec,dest):
    path = dest/(spec['id']+'.json')
    if path.exists():
        assert json.loads(path.read_text())['identity']==identity()
        return
    begin = time.monotonic()
    s,basis,cert = plant(spec['family'],spec['system'],spec.get('m',12))
    k,x,total = s['K0'].copy(),np.zeros(CFG['n']),0
    ispi = spec['algorithm']=='PI'
    ns = [122964]*8 if ispi else schedule(spec['final'])
    assert not ispi or sum(CFG['burn']+(n+1)*CFG['H'] for n in ns)==assigned(CFG['e1_final'])
    rows = [dict(stage=0,actual_transitions=0,**assess(s,k,basis if spec['family']=='E1' else None))]
    status = 'complete'; checkpoints = []; policies = [k.copy()]
    for stage,count in enumerate(ns):
        try:
            data = next(collect_prefixes(s,k,x,[count],
                rng_for(246200,spec['system'],spec['trial'],stage,spec.get('m',12)),
                h=CFG['H'],burn=CFG['burn']))
            x = data['x']; total += data['transitions']
            true = targets(s,k,CFG['H'])
            if ispi:
                gg,zz,rank,threshold = v4_correct(data['G'],data['Z'],
                    'dense' if spec['mode']=='dense' else 'known_rank',CFG['rank'])
                candidate = greedy(k,s['R'],gg,zz)
                proxy = None; spectral_error = op(np.concatenate((data['G']-true['G'],data['Z']-true['Z']),axis=1))
            else:
                zz,rank,threshold,proxy = npg_projection(data['Z'],spec['mode'],spec.get('k',12),
                    spec.get('multiplier',1.),data['halves'])
                candidate = k-CFG['eta']*(k+zz)
                spectral_error = op(data['Z']-true['Z'])
            q = assess(s,candidate,basis if spec['family']=='E1' else None)
            row = dict(stage=stage+1,N=count,actual_transitions=total,retained_rank=rank,
                threshold=threshold,noise_proxy=proxy,raw_spectral_error=spectral_error,
                gram_condition=float(data['gram_condition']),
                horizon_bias_op=op(true['ZH']-true['Z']),**q)
            # Matched same-data counterfactual is diagnostic; does not continue training.
            if stage==len(ns)-1:
                for cmode,crank in [('dense',12),('truncated',CFG['rank'])]:
                    if ispi:
                        cg,cz,_,_ = v4_correct(data['G'],data['Z'],
                            'dense' if cmode=='dense' else 'known_rank',CFG['rank'])
                        ck = greedy(k,s['R'],cg,cz)
                    else:
                        cz = data['Z'] if cmode=='dense' else trunc(data['Z'],crank)
                        ck = k-CFG['eta']*(k+cz)
                    checkpoints.append(dict(mode=cmode,**assess(s,ck,basis if spec['family']=='E1' else None)))
            k = candidate; policies.append(k.copy()); rows.append(row)
            if not q['stable']:
                status = 'unstable'; break
        except (np.linalg.LinAlgError,ValueError,FloatingPointError,ArithmeticError) as error:
            status = 'numerical_failure'
            rows.append(dict(stage=stage+1,actual_transitions=total,stable=False,gap=None,failure=str(error)))
            break
    planned = sum(CFG['burn']+(n+1)*CFG['H'] for n in ns)
    dest.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path.with_suffix('.npz'),policies=np.asarray(policies),x=x)
    atomic_json(path,dict(spec=spec,identity=identity(),provenance=provenance(),status=status,
        certificates=cert,rows=rows,assigned_transitions=planned,actual_transitions=total,
        seconds=time.monotonic()-begin,peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        matched_terminal_updates=checkpoints,policy_sha256=sha(path.with_suffix('.npz'))))
    print(json.dumps(dict(id=spec['id'],status=status,gap=rows[-1].get('gap'),seconds=time.monotonic()-begin)),flush=True)


def ce_run(spec,dest,calibration=False):
    path = dest/(spec['id']+'.json')
    if path.exists():
        assert json.loads(path.read_text())['identity']==identity(); return
    begin = time.monotonic(); s,basis,cert = plant(spec['family'],spec['system'],spec.get('m',12))
    n,m = CFG['n'],s['B'].shape[1]
    rng = rng_for(246300,spec['system'],spec['trial'],m)
    f = s['A']-s['B']@s['K0']; x=np.zeros(n)
    x,_ = nominal_chunk(f,x,rng.normal(size=(CFG['burn'],n)))
    gram,cross = np.zeros((n+m,n+m)),np.zeros((n,n+m))
    budgets = CFG['ce_budgets'] if spec['family']=='E2' else CFG['ce_budgets'][:-1]
    stops = sorted(set(budgets)|{b//2 for b in budgets}); saved={}; done=0; rows=[]; policies={}
    for stop in stops:
        while done<stop:
            size=min(256,stop-done)
            x,z,y=rectangular_ce_chunk(f,s['B'],s['K0'],x,rng.normal(size=(size,m)),rng.normal(size=(size,n)))
            gram+=z.T@z;cross+=y.T@z;done+=size
        saved[done]=(gram.copy(),cross.copy())
        if done not in budgets:continue
        theta=np.linalg.solve(gram,cross.T).T; ah,bh=theta[:,:n],theta[:,n:]
        ga,ca=saved[done//2]
        half1=np.linalg.solve(ga,ca.T).T[:,n:]
        half2=np.linalg.solve(gram-ga,(cross-ca).T).T[:,n:]
        proxy=op(half1-half2)/2; error=op(bh-s['B'])
        modes=[('dense',min(n,m),None)]
        if spec['family']=='E1':modes+=[('truncated',CFG['rank'],None)]
        else:
            modes += [('k'+str(k),k,None) for k in KS if k!=12]
            multipliers=CFG['multipliers'] if calibration else [spec['multiplier']]
            modes += [('adaptive'+str(c),None,c) for c in multipliers]
        for mode,rank,mult in modes:
            threshold=None
            if mult is not None:
                threshold=mult*proxy;rank=int(np.count_nonzero(np.linalg.svd(bh,compute_uv=False)>threshold))
            estimate=bh if rank==min(n,m) else trunc(bh,rank)
            row=dict(mode=mode,k=rank,N=done,transitions=done+CFG['burn'],threshold=threshold,
                     noise_proxy=proxy,raw_spectral_error=error)
            try:
                ck,_=dare(ah,estimate,s['Q'],s['R'])
                row.update(assess(s,ck,basis if spec['family']=='E1' else None))
                policies[f'N{done}_{mode}']=ck
                if spec['family']=='E1' and row['stable']:
                    oracle=basis@(basis.T@ck)
                    row['oracle_projected_redundant_cost']=assess(s,oracle,basis)['redundant_cost']
            except (np.linalg.LinAlgError,ValueError) as error_msg:
                row.update(stable=False,gap=None,failure=str(error_msg))
            rows.append(row)
    dest.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path.with_suffix('.npz'),**policies)
    atomic_json(path,dict(spec=spec,identity=identity(),provenance=provenance(),certificates=cert,
        rows=rows,actual_transitions=done+CFG['burn'],seconds=time.monotonic()-begin,
        policy_sha256=sha(path.with_suffix('.npz'))))
    print(json.dumps(dict(id=spec['id'],seconds=time.monotonic()-begin)),flush=True)


def tasks(phase,selection=None):
    ts=[]
    seeds=CFG['calibration_systems'] if phase=='calibration' else CFG['systems']
    trials=CFG['calibration_trials'] if phase=='calibration' else CFG['trials']
    for seed in seeds:
        for trial in trials:
            if phase=='formal':
                for m in CFG['ms']:
                    for alg in ['NPG','PI']:
                        for mode in ['dense','truncated']:
                            ts.append(dict(family='E1',system=seed,trial=trial,m=m,algorithm=alg,mode=mode,
                                k=12 if mode=='dense' else 2,final=CFG['e1_final']))
                    ts.append(dict(family='E1',system=seed,trial=trial,m=m,algorithm='CE'))
            for final in BUDGETS:
                arms=([dict(mode='adaptive',multiplier=c) for c in CFG['multipliers']] if phase=='calibration'
                    else [dict(mode='dense' if k==12 else 'fixed',k=k) for k in KS]
                         +[dict(mode='adaptive',multiplier=selection['NPG'])])
                for arm in arms:
                    ts.append(dict(family='E2',system=seed,trial=trial,algorithm='NPG',final=final,**arm))
            ts.append(dict(family='E2',system=seed,trial=trial,algorithm='CE',
                           multiplier=None if phase=='calibration' else selection['CE']))
    for i,t in enumerate(ts):t['id']=phase+f'-{i:05d}'
    return ts


def run_bundle(phase,index,bundles):
    selection=None if phase=='calibration' else json.loads((OUT/'threshold_frozen.json').read_text())['selection']
    ts=tasks(phase,selection)
    for t in ts[index::bundles]:
        if t['algorithm']=='CE':ce_run(t,OUT/phase,phase=='calibration')
        else:actor(t,OUT/phase)


def freeze():
    expected=tasks('calibration'); losses={a:{str(c):[] for c in CFG['multipliers']} for a in ['NPG','CE']}
    hashes={}
    for t in expected:
        p=OUT/'calibration'/(t['id']+'.json');d=json.loads(p.read_text());assert d['identity']==identity()
        hashes[p.name]=sha(p)
        if t['algorithm']=='NPG':
            row=d['rows'][-1];value=np.log1p(row['gap']) if d['status']=='complete' and row['stable'] else 20.
            losses['NPG'][str(t['multiplier'])].append(float(value))
        else:
            for row in d['rows']:
                if row['mode'].startswith('adaptive'):
                    value=np.log1p(row['gap']) if row['stable'] else 20.
                    losses['CE'][row['mode'].removeprefix('adaptive')].append(float(value))
    means={alg:{c:float(np.mean(v)) for c,v in vals.items()} for alg,vals in losses.items()}
    selected={alg:float(min(vals,key=lambda c:(vals[c],-float(c)))) for alg,vals in means.items()}
    frozen=dict(selection=selected,calibration_losses=means,calibration_sha256=hashes,
                identity=identity(),provenance=provenance(),selection_rule='mean log1p gap; failures20; ties larger c')
    p=OUT/'threshold_frozen.json'
    assert not p.exists(),'Never refreeze using test results'
    atomic_json(p,frozen);print(json.dumps(frozen['selection']),flush=True)


def prepare():
    begin=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    checks=[]
    for seed in CFG['systems']+CFG['calibration_systems']:
        previous=None
        for m in CFG['ms']:
            s,basis,c=plant('E1',seed,m)
            _,p0=evaluate(s,s['K0']);_,ps=dare(s['A'],s['B'],s['Q'],s['R'])
            now=(p0,ps,s['B']@s['B'].T)
            if previous:
                for a,b in zip(previous,now):np.testing.assert_allclose(a,b,atol=2e-11)
            previous=now
            assert np.linalg.norm(s['B']@s['K0'])<1e-12 and c['Pstar_Fstar_fro2']>1
            checks.append(c)
        s,basis,c=plant('E2',seed);assert np.linalg.matrix_rank(s['B'])==12
        checks.append(c)
    # Independent quadrature for Z and G: exact Gaussian Stein identities.
    from numpy.polynomial.hermite_e import hermegauss
    from dense_scaling import pulse_chunk
    nodes,weights=hermegauss(7);weights/=np.sqrt(2*np.pi)
    f=np.array([[.4,.1],[0.,.3]]);b=np.array([[.8,.2],[.1,.7]])
    cost=np.array([[1.2,.1],[.1,1.4]]);x=np.array([.3,-.4]);h=4
    z=np.zeros(2);g=np.zeros((2,2))
    for i in range(7):
        for j in range(7):
            pulse=np.array([nodes[i],nodes[j]]);w=weights[i]*weights[j]
            _,_,ret=pulse_chunk(f,b,cost,x,pulse[None,:],np.zeros((1,h,2)))
            delta=ret[0]-17.
            z+=w*(-pulse*delta/2)
            g+=w*(np.outer(pulse,pulse)-np.eye(2))*delta/2
    ph=sum(np.linalg.matrix_power(f,t).T@cost@np.linalg.matrix_power(f,t) for t in range(h))
    np.testing.assert_allclose(z,-b.T@ph@f@x,atol=1e-11)
    np.testing.assert_allclose(g,b.T@ph@b,atol=1e-11)
    # Rectangular identification collector checked against independent recursion.
    for m in [3,12]:
        s,_,_=plant('E1',8998,m);rr=rng_for(246099,m)
        pulse=rr.normal(size=(128,m));noise=rr.normal(size=(128,12));x0=rr.normal(size=12)
        f=s['A']-s['B']@s['K0']
        xe,design,yy=rectangular_ce_chunk(f,s['B'],s['K0'],x0.copy(),pulse,noise)
        xx=x0.copy();manual=[];outputs=[]
        for j in range(128):
            action=-s['K0']@xx+pulse[j];manual.append(np.r_[xx,action])
            xx=s['A']@xx+s['B']@action+noise[j];outputs.append(xx.copy())
        np.testing.assert_allclose(xe,xx,atol=1e-12)
        np.testing.assert_allclose(design,manual,atol=1e-12)
        np.testing.assert_allclose(yy,outputs,atol=1e-12)
    # Actual full maximum-budget path, not a synthetic solver-only timing.
    benchmarks=[dict(id='benchmark-npg',family='E2',system=8999,trial=899,m=12,
                     algorithm='NPG',mode='dense',k=12,final=max(BUDGETS)),
                dict(id='benchmark-pi',family='E1',system=8999,trial=899,m=12,
                     algorithm='PI',mode='truncated',k=2,final=CFG['e1_final']),
                dict(id='benchmark-ce',family='E2',system=8999,trial=899,m=12,algorithm='CE',multiplier=1.)]
    timings=[]
    for spec in benchmarks:
        if spec['algorithm']=='CE':ce_run(spec,OUT/'preflight')
        else:actor(spec,OUT/'preflight')
        d=json.loads((OUT/'preflight'/(spec['id']+'.json')).read_text())
        timings.append(dict(algorithm=spec['algorithm'],seconds=d['seconds'],
                            peak_rss_KiB=d.get('peak_rss_KiB'),status=d.get('status','complete')))
    atomic_json(OUT/'preflight.json',dict(status='PASS',certificates=checks,benchmarks=timings,
        assigned_E1=assigned(CFG['e1_final']),identity=identity(),provenance=provenance(),
        seconds=time.monotonic()-begin))


def robustness():
    rows=[]
    for p in sorted((OUT/'formal').glob('*.json')):
        d=json.loads(p.read_text());t=d['spec']
        if t['family']!='E1' or t.get('m')!=12 or t['algorithm']=='CE':continue
        s,basis,_=plant('E1',t['system'],12)
        k=np.load(p.with_suffix('.npz'))['policies'][-1]
        nominal=assess(s,k);denom=nominal.get('cost')
        for direction in range(10):
            perturb=rng_for(246400,t['system'],direction).normal(size=(12,12))
            perturb-=perturb@basis@basis.T;perturb/=op(perturb)
            assert np.linalg.norm(perturb@basis)<1e-11
            for delta in [0.,1.,2.,4.,8.,16.]:
                q=assess(dict(s,B=s['B']+delta*perturb),k) if d['status']=='complete' else dict(stable=False,cost=None)
                change=(q['cost']-denom)/denom if q['stable'] and nominal['stable'] else None
                rows.append(dict(id=t['id'],system=t['system'],trial=t['trial'],algorithm=t['algorithm'],
                    mode=t['mode'],direction=direction,delta=delta,nominal_complete=d['status']=='complete',
                    stable=q['stable'],relative_change=change,
                    absolute_relative_change=abs(change) if change is not None else None))
    atomic_json(OUT/'robustness.json',dict(rows=rows,identity=identity(),provenance=provenance(),
                additional_training_transitions=0,deployment_transitions=0))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','calibration','formal','freeze','robustness'])
    p.add_argument('--bundle',type=int,default=0);p.add_argument('--bundles',type=int,default=1)
    a=p.parse_args();require_compute()
    if a.mode=='prepare':prepare()
    elif a.mode=='freeze':freeze()
    elif a.mode=='robustness':robustness()
    else:run_bundle(a.mode,a.bundle,a.bundles)


if __name__=='__main__':main()
