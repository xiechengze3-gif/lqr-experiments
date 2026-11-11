"""New unstable independent-A/B experiments. Simulation/evaluation are separate from learners."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, os, socket, sys, time
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov

try:
    from numba import njit
except ImportError:
    sys.path.append(os.environ.get('LQR_NUMBA_SITE','/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages'))
    from numba import njit

ROOT=Path(__file__).resolve().parent
BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/supplement-20261101'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
def rng(*parts):return np.random.default_rng(np.random.SeedSequence([2026110101]+list(map(int,parts))))
def haar(random,n):
    q,r=np.linalg.qr(random.normal(size=(n,n)))
    return q*np.where(np.diag(r)>=0,1.,-1.)
def trunc(matrix,k):
    if k>=min(matrix.shape):return matrix.copy()
    if k==0:return np.zeros_like(matrix)
    u,s,vh=np.linalg.svd(matrix,full_matrices=False);return (u[:,:k]*s[:k])@vh[:k]

def independent_dynamics(n,system):
    random=rng(1,n,system);q=haar(random,n)
    values=np.r_[1.05,random.uniform(.15,.60,n-1)]
    return (q*values)@q.T,q[:,0],values

def stability_only_gain(a,b,unstable_vector,target=.65):
    # One unstable Schur mode, all other eigenvalues are already stable.
    # No Q, R, P, objective, optimum or cost evaluator enters this function.
    c=unstable_vector@b
    if float(c@c)<1e-25:raise ArithmeticError('Uncontrollable unstable mode; no seed replacement')
    return ((1.05-target)*c/(c@c))[:,None]*unstable_vector[None,:]

def plant(n,m,rank,system,spectrum='exact',null_scale=0.):
    a,unstable,eigs=independent_dynamics(n,system)
    u=haar(rng(2,n,system),n);v=haar(rng(3,n,m,system),m)
    if spectrum=='exact':singular=np.r_[np.ones(rank),np.zeros(min(n,m)-rank)]
    elif spectrum=='smooth':singular=.7**np.arange(min(n,m))
    elif spectrum=='gapped':singular=np.r_[np.ones(2),np.full(min(n,m)-2,.05)]
    elif spectrum=='flat':singular=np.ones(min(n,m))
    else:raise ValueError(spectrum)
    b=(u[:,:len(singular)]*singular)@v[:,:len(singular)].T
    h=rng(4,n,system).normal(size=n);h/=np.linalg.norm(h)
    if spectrum=='exact':
        keff=stability_only_gain(a,u[:,:rank],unstable)
        k0=v[:,:rank]@keff
        if m>rank:k0=k0+null_scale*v[:,rank,None]*h[None,:]
        basis=v[:,:rank]
    else:
        k0=stability_only_gain(a,b,unstable);basis=None
    # Everything below is simulator/evaluation metadata, unavailable to learners.
    q=np.eye(n);r=np.eye(m);w=np.eye(n);f0=a-b@k0
    p0=solve_discrete_lyapunov(f0.T,q+k0.T@k0)
    ps=solve_discrete_are(a,b,q,r);ks=np.linalg.solve(r+b.T@ps@b,b.T@ps@a)
    projection=v[:,:rank]@v[:,:rank].T
    energy=float(np.sum((projection@k0)**2)/np.sum(k0**2))
    col,sv,_=np.linalg.svd(k0,full_matrices=False);kr=int(np.count_nonzero(sv>1e-10*max(1.,sv[0])))
    overlap=float(np.sum((v[:,:rank].T@col[:,:kr])**2)/max(1,kr))
    cert=dict(n=n,m=m,r=rank,system=system,spectrum=spectrum,null_scale=null_scale,
      rho_A=float(np.max(np.abs(np.linalg.eigvals(a)))),rho_F0=float(np.max(np.abs(np.linalg.eigvals(f0)))),
      P0_op=float(np.linalg.norm(p0,2)),J0=float(np.trace(p0)),Jstar=float(np.trace(ps)),
      initial_gap=float(np.trace(p0-ps)),K0_action_energy_overlap=energy,K0_action_column_subspace_overlap=overlap,
      initializer_uses_Q_R_Kstar_cost=False,A_B_independent_streams=True,A_eigenvalues=eigs.tolist(),
      optimal_sensitivity_fro2=float(np.sum((ps@(a-b@ks))**2)),
      tau2=[float(singular[k:]@singular[k:]) for k in range(len(singular)+1)],
      beta=[float(singular[k]) if k<len(singular) else 0. for k in range(len(singular)+1)])
    assert cert['rho_A']>1 and cert['rho_F0']<.9
    return dict(A=a,B=b,Q=q,R=r,W=w,K0=k0,P0=p0,Kstar=ks,Pstar=ps,basis=basis,certificate=cert)

def assess(s,k):
    f=s['A']-s['B']@k;radius=float(np.max(np.abs(np.linalg.eigvals(f))))
    result=dict(stable=bool(np.isfinite(radius) and radius<1-1e-10),rho=radius)
    if not result['stable']:return dict(result,gap=None,relative_gap=None,cost=None,redundant_cost=None)
    p=solve_discrete_lyapunov(f.T,s['Q']+k.T@s['R']@k)
    cov=solve_discrete_lyapunov(f,s['W']);delta=k-s['Kstar']
    gap=float(np.trace(cov@delta.T@(s['R']+s['B'].T@s['Pstar']@s['B'])@delta))
    result.update(cost=float(np.trace(p)),gap=gap,relative_gap=gap/s['certificate']['initial_gap'])
    if s['basis'] is not None:
        null=k-s['basis']@(s['basis'].T@k)
        result['redundant_cost']=float(np.trace(null@cov@null.T))
    return result

@njit(cache=True)
def ce_chunk(f,b,k,x,pulses,noises):
    count=len(noises);n=len(x);m=b.shape[1];zs=np.empty((count,n+m));ys=np.empty((count,n))
    for i in range(count):
        state=x.copy();action=-k@state+pulses[i]
        x=f@state+b@pulses[i]+noises[i]
        zs[i,:n]=state;zs[i,n:]=action;ys[i]=x
    return x,zs,ys

@njit(cache=True)
def block_starts(fh,x,increments):
    starts=np.empty_like(increments)
    for i in range(len(increments)):
        starts[i]=x;x=fh@x+increments[i]
    return starts

def prepare(f,b,h):
    powers=[np.eye(len(f))]
    for _ in range(h):powers.append(powers[-1]@f)
    return powers,powers[-2]@b

def pulse_batch(f,b,cost,x,pulses,noises,prepared):
    count,h,n=noises.shape;powers,impulse=prepared
    increments=pulses@impulse.T
    for t in range(h):increments+=noises[:,t]@powers[h-t-1].T
    starts=block_starts(np.ascontiguousarray(powers[-1]),x,increments)
    states=starts.copy();returns=np.zeros(count)
    for t in range(h):
        states=states@f.T+noises[:,t]
        if t==0:states+=pulses@b.T
        returns+=np.einsum('ij,ij->i',states,states@cost.T)
    return states[-1].copy(),starts,returns

def fit_model(gram,cross):
    theta=np.linalg.solve(gram,cross.T).T
    if not np.all(np.isfinite(theta)):raise ArithmeticError('Nonfinite OLS')
    return theta

def ce_learner(theta,n,q,r,rank):
    # Observation-only boundary: theta, known cost matrices and integer rank.
    ah,bh=theta[:,:n],theta[:,n:];bh=trunc(bh,rank)
    p=solve_discrete_are(ah,bh,q,r)
    return np.linalg.solve(r+bh.T@p@bh,bh.T@p@ah)

def ce_run(s,spec,config,destination):
    start=time.monotonic();n,m=s['B'].shape;random=rng(10,n,m,spec['system'],spec['trial'])
    k0=s['K0'];x=np.zeros(n);f=np.ascontiguousarray(s['A']-s['B']@k0);b=s['B'];sigma=config['nu']
    burn=config['ce_burn'];x,_,_=ce_chunk(f,b,k0,x,sigma*random.normal(size=(burn,m)),random.normal(size=(burn,n)))
    budgets=config['ce_prefixes'];stops=sorted(set(budgets)|{v//2 for v in budgets})
    gram=np.zeros((n+m,n+m));cross=np.zeros((n,n+m));snapshots={};done=0;records=[];policies={}
    for stop in stops:
        while done<stop:
            count=min(512,stop-done)
            x,z,y=ce_chunk(f,b,k0,x,sigma*random.normal(size=(count,m)),random.normal(size=(count,n)))
            gram+=z.T@z;cross+=y.T@z;done+=count
        snapshots[done]=(gram.copy(),cross.copy())
        if done not in budgets:continue
        theta=fit_model(gram,cross);ah,bh=theta[:,:n],theta[:,n:]
        g1,c1=snapshots[done//2];h1=fit_model(g1,c1)[:,n:];h2=fit_model(gram-g1,cross-c1)[:,n:]
        proxy=float(np.linalg.norm(h1-h2,2)/2);singular=np.linalg.svd(bh,compute_uv=False)
        modes=[('dense',min(n,m)),('truncated',spec['r'])]
        if config.get('fixed_ranks') is not None:modes=[('dense',min(n,m))]+[('k'+str(k),k) for k in config['fixed_ranks'] if k<min(n,m)]
        if config.get('adaptive_C5') is not None:
            threshold=config['adaptive_C5']*math.sqrt((n+m+math.log(1/config['delta']))/done)
            modes += [('adaptive_paper',int(np.count_nonzero(singular>threshold))),('adaptive_split',int(np.count_nonzero(singular>proxy)))]
        cache={}
        for mode,k in modes:
            row=dict(spec,algorithm='CE',mode=mode,k=k,N=done,transitions=burn+done,noise_proxy=proxy)
            try:
                if k not in cache:
                    candidate=ce_learner(theta,n,s['Q'],s['R'],k);cache[k]=(candidate,assess(s,candidate))
                candidate,q=cache[k];row.update(q);policies[str(done)+'_'+mode]=candidate
            except (np.linalg.LinAlgError,ValueError,ArithmeticError) as exc:
                row.update(stable=False,gap=None,relative_gap=None,failure=repr(exc))
            if mode=='adaptive_paper':row['threshold']=threshold
            if mode=='adaptive_split':row['threshold']=proxy
            records.append(row)
        if s['basis'] is not None and config.get('oracle',False):
            # Explicit diagnostic only: same OLS fit, true-space B projection.
            try:
                oracle=theta.copy();oracle[:,n:]=bh@s['basis']@s['basis'].T
                candidate=ce_learner(oracle,n,s['Q'],s['R'],min(n,m))
                records.append(dict(spec,algorithm='CE',mode='oracle_true_space_diagnostic',N=done,transitions=burn+done,**assess(s,candidate)))
            except (np.linalg.LinAlgError,ValueError,ArithmeticError) as exc:
                records.append(dict(spec,algorithm='CE',mode='oracle_true_space_diagnostic',N=done,transitions=burn+done,stable=False,gap=None,relative_gap=None,failure=repr(exc)))
    destination.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(destination.with_suffix('.npz'),**policies,A=s['A'],B=s['B'],K0=k0)
    data=dict(spec=spec,certificate=s['certificate'],records=records,seconds=time.monotonic()-start,
      transitions=burn+done,source_sha256=sha(__file__),job=os.environ['SLURM_JOB_ID'])
    save(destination,data);return data

def collect(s,k,x,count,random,config):
    # Simulator produces observations; fitting below never reads true model targets.
    n,m=s['B'].shape;h=config['H'];nu=config['nu'];f=np.ascontiguousarray(s['A']-s['B']@k)
    cost=s['Q']+k.T@s['R']@k;prepared=prepare(f,s['B'],h)
    burn=config['burn_blocks']
    if burn:
        x,_,_=pulse_batch(f,s['B'],cost,x,nu*random.normal(size=(burn,m)),random.normal(size=(burn,h,n)),prepared)
    x,_,ys=pulse_batch(f,s['B'],cost,x,nu*random.normal(size=(1,m)),random.normal(size=(1,h,n)),prepared)
    previous=ys[-1];gram=np.zeros((n,n));cross=np.zeros((m,n));curvature=np.zeros((m,m));done=0
    while done<count:
        size=min(256,count-done);pulses=nu*random.normal(size=(size,m));noise=random.normal(size=(size,h,n))
        x,starts,ys=pulse_batch(f,s['B'],cost,x,pulses,noise,prepared)
        delta=np.diff(np.r_[previous,ys]);previous=ys[-1]
        labels=-pulses*delta[:,None]/(2*nu**2)
        gram+=starts.T@starts;cross+=labels.T@starts
        curvature+=((pulses*delta[:,None]).T@pulses-nu**2*delta.sum()*np.eye(m))/(2*nu**4)
        done+=size
    z=fit_model(gram,cross);g=curvature/count
    return x,(g+g.T)/2,z

def actor_learner(k,r,g,z,mode,rank,algorithm,eta):
    if algorithm=='NPG':return k-eta*(r@k+(z if mode=='dense' else trunc(z,rank)))
    values,u=np.linalg.eigh(g);gp=(u*np.maximum(values,0.))@u.T
    if mode!='dense' and rank<k.shape[0]:
        basis=np.linalg.svd(np.concatenate((gp,z),axis=1),full_matrices=False)[0][:,:rank]
        gg=basis@(basis.T@gp@basis)@basis.T;zz=basis@(basis.T@z)
    else:gg,zz=gp,z
    return np.linalg.solve(r+(gg+gg.T)/2,gg@k-zz)

def actor_run(s,spec,config,algorithm,destination):
    start=time.monotonic();n,m=s['B'].shape;records=[];states={v:np.zeros(n) for v in ('dense','truncated')}
    policies={v:s['K0'].copy() for v in states};dead={v:False for v in states};totals={v:0 for v in states};saved={}
    for mode,k in policies.items():records.append(dict(spec,algorithm=algorithm,mode=mode,stage=0,transitions=0,padding_transitions=0,**assess(s,k)))
    padding={v:0 for v in states}
    schedule=config['npg_batches'] if algorithm=='NPG' else config['pi_batches']
    for stage,count in enumerate(schedule,1):
        for mode in states:
            # After failure, K0 observations consume the fixed budget only; all
            # later learned outputs remain failed. No recovery or iterate selection.
            behavior=s['K0'] if dead[mode] else policies[mode]
            random=rng(20 if algorithm=='NPG' else 21,n,m,spec['system'],spec['trial'],stage)
            used=(config['burn_blocks']+1+count)*config['H']
            try:
                states[mode],g,z=collect(s,behavior,states[mode],count,random,config)
                totals[mode]+=used
                if dead[mode]:
                    padding[mode]+=used;q=dict(stable=False,gap=None,relative_gap=None,failure='absorbing_failure_budget_padding')
                else:
                    candidate=actor_learner(policies[mode],s['R'],g,z,mode,spec['r'],algorithm,config['eta'])
                    q=assess(s,candidate);policies[mode]=candidate
                    if not q['stable']:dead[mode]=True
                records.append(dict(spec,algorithm=algorithm,mode=mode,stage=stage,N=count,transitions=totals[mode],padding_transitions=padding[mode],**q))
                if not dead[mode]:saved[mode+'_'+str(stage)]=policies[mode].copy()
            except (np.linalg.LinAlgError,ValueError,ArithmeticError) as exc:
                # No silent restart or replay. A partial sampling failure is a
                # whole task failure, recorded with a bounded receipt.
                save(destination.with_suffix('.failure.json'),dict(spec=spec,stage=stage,mode=mode,actual_transitions=totals[mode],error=repr(exc),source_sha256=sha(__file__)))
                raise
        assert totals['dense']==totals['truncated']
    destination.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(destination.with_suffix('.npz'),**saved,A=s['A'],B=s['B'],K0=s['K0'])
    data=dict(spec=spec,algorithm=algorithm,certificate=s['certificate'],records=records,seconds=time.monotonic()-start,
      actual_transitions=totals,source_sha256=sha(__file__),job=os.environ['SLURM_JOB_ID'])
    save(destination,data);return data

def require_compute():
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().startswith('login'):
        raise RuntimeError('Scientific simulation and diagnostics require a Slurm compute node')

def invariants(config,dest):
    records=[]
    for system in config['pilot_systems']:
        for null in (0.,.25):
            plants=[plant(12,m,2,system,null_scale=null) for m in config['ms']]
            reference=plants[0] if null==0 else plants[1]
            for s in plants:
                c=s['certificate'];p=reference['P0'];base=reference['certificate']
                item=dict(system=system,m=c['m'],null_scale=null,P0_difference=float(np.linalg.norm(s['P0']-p)),
                  J0_difference=abs(c['J0']-base['J0']),Jstar_difference=abs(c['Jstar']-base['Jstar']),
                  optimal_sensitivity_difference=abs(c['optimal_sensitivity_fro2']-base['optimal_sensitivity_fro2']))
                if null==0 or c['m']>2:
                    assert item['P0_difference']<1e-8*max(1.,np.linalg.norm(p))
                    assert item['Jstar_difference']<1e-8*max(1.,base['Jstar'])
                records.append(item)
    save(dest,dict(status='PASS_WITH_DECLARED_M_EQUALS_R_EXCEPTION',records=records,source_sha256=sha(__file__),job=os.environ['SLURM_JOB_ID']))

def main():
    require_compute();p=argparse.ArgumentParser();p.add_argument('mode',choices=['invariants','pilot_ce','pilot_actor'])
    p.add_argument('--config',type=Path,required=True);p.add_argument('--calibration',type=int,default=0);a=p.parse_args()
    config=json.loads(a.config.read_text());out=OUT/config['experiment'];out.mkdir(parents=True,exist_ok=True)
    if a.mode=='invariants':invariants(config,out/'pilot/invariants.json');return
    if a.mode=='pilot_ce':
        for system in config['pilot_systems']:
            for trial in config['pilot_trials']:
                for m in config['pilot_ms']:
                    spec=dict(experiment='X1',n=12,m=m,r=2,system=system,trial=trial,null_scale=.25)
                    path=out/'pilot/ce'/f's{system}-t{trial}-m{m}.json';assert not path.exists()
                    result=ce_run(plant(12,m,2,system,null_scale=.25),spec,config,path)
                    print(json.dumps({'id':path.stem,'seconds':result['seconds'],'records':len(result['records'])}),flush=True)
        return
    calibration=config['actor_calibration'][a.calibration];resolved=dict(config,**calibration)
    for system in config['pilot_systems']:
        for trial in config['actor_pilot_trials']:
            for m in config['pilot_ms']:
                for algorithm in ('NPG','PI'):
                    spec=dict(experiment='X1',n=12,m=m,r=2,system=system,trial=trial,null_scale=.25,calibration=a.calibration)
                    path=out/'pilot'/f'calibration-{a.calibration}'/algorithm/f's{system}-t{trial}-m{m}.json';assert not path.exists()
                    result=actor_run(plant(12,m,2,system,null_scale=.25),spec,resolved,algorithm,path)
                    dense=[r for r in result['records'] if r['mode']=='dense']
                    print(json.dumps({'id':path.stem,'algorithm':algorithm,'seconds':result['seconds'],'dense_all_stable':all(r['stable'] for r in dense)}),flush=True)

if __name__=='__main__':main()
