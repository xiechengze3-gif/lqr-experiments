"""Pilot-only original ce_run with explicit local provenance."""
import time, math
import numpy as np
from frozen_engine import rng, ce_chunk, fit_model, ce_learner, assess, sha, save

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
      transitions=burn+done,source_sha256=sha(__file__),job=None,execution_context='LOCAL_AUTHOR_APPROVED_X10')
    save(destination,data);return data
