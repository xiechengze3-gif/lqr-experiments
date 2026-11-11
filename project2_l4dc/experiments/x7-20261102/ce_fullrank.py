"""X7 full-rank S models and saved-fit CE; frozen observation-only learner."""
from __future__ import annotations
import json
import math
import os
import resource
import shutil
import time
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov
import frozen_engine as e

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/x7-20261102'


def require_compute():
    e.require_compute()


def save_new(path,data):
    path=Path(path);assert not path.exists(),str(path)
    e.save(path,data)


def npz_new(path,**arrays):
    path=Path(path);assert not path.exists(),str(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,**arrays)
    return e.sha(path)


def verify_sources(config):
    for name,digest in config['scientific_sources'].items():
        assert e.sha(Path(__file__).parent/name)==digest,name


def make_model(n,spectrum,system):
    require_compute()
    random=e.rng(1,n,system)
    rotation=e.haar(random,n);eigenvalues=random.uniform(.15,.60,n)
    a=(rotation*eigenvalues)@rotation.T
    u=e.haar(e.rng(2,n,system),n);v=e.haar(e.rng(3,n,n,system),n)
    if spectrum=='geometric':singular=.7**np.arange(n)
    elif spectrum=='polynomial':singular=1./np.arange(1,n+1)
    else:raise ValueError(spectrum)
    b=(u*singular)@v.T;eye=np.eye(n);k0=np.zeros((n,n))
    p0=solve_discrete_lyapunov(a.T,eye)
    ps=solve_discrete_are(a,b,eye,eye)
    ks=np.linalg.solve(eye+b.T@ps@b,b.T@ps@a)
    cert=dict(family='S',n=n,m=n,r=n,system=system,spectrum=spectrum,
        full_rank=True,rho_A=float(max(eigenvalues)),rho_F0=float(max(eigenvalues)),
        P0_op=float(np.linalg.norm(p0,2)),P0_class_bound=1.5625,
        J0=float(np.trace(p0)),Jstar=float(np.trace(ps)),
        initial_gap=float(np.trace(p0-ps)),B_op=1.,
        A_B_independent_streams=True,stream_root=2026110101,
        initializer_uses_Q_R_Kstar_cost=False,A_eigenvalues=eigenvalues.tolist(),
        singular_values=singular.tolist(),
        tau2=[float(singular[k:]@singular[k:]) for k in range(n+1)],
        beta=[float(singular[k]) if k<n else 0. for k in range(n+1)],
        optimal_sensitivity_fro2=float(np.sum((ps@(a-b@ks))**2)),
        K0_action_energy_overlap=None,
        K0_overlap_note='Zero gain: normalized overlaps undefined.')
    assert cert['P0_op']<=1.5625+1e-10
    assert cert['initial_gap']>0 and cert['rho_A']<=.60+1e-12
    assert np.allclose(np.linalg.svd(b,compute_uv=False),singular,rtol=1e-8,atol=1e-12)
    return dict(A=a,B=b,Q=eye,R=eye,W=eye,K0=k0,P0=p0,Pstar=ps,Kstar=ks,
                basis=None,certificate=cert)


def save_model(model,directory):
    require_compute();directory=Path(directory)
    assert not directory.exists();directory.mkdir(parents=True)
    path=directory/'model.npz'
    digest=npz_new(path,**{k:model[k] for k in
        ['A','B','Q','R','W','K0','P0','Pstar','Kstar']},
        certificate_json=np.array(json.dumps(model['certificate'],sort_keys=True)))
    save_new(directory/'model.json',dict(status='MODEL_FROZEN_NO_TRAINING',
        model_sha256=digest,source_sha256=e.sha(__file__),
        engine_sha256=e.sha(e.__file__),certificate=model['certificate']))
    return dict(path=str(path),sha256=digest,certificate=model['certificate'])


def load_model(path,digest):
    require_compute();path=Path(path);assert e.sha(path)==digest
    with np.load(path,allow_pickle=False) as data:
        model={name:data[name].copy() for name in
            ['A','B','Q','R','W','K0','P0','Pstar','Kstar']}
        model['certificate']=json.loads(str(data['certificate_json']))
    model['basis']=None
    return model


def prefixes(config,n):
    return [4*(2*n)*v for v in config['multiplier_grid']]


def fit_prefixes(model,config,trial,resume=None):
    """Same random stream,512 chunks,half-prefix stops and solves as ce_run."""
    require_compute()
    n,m=model['B'].shape;system=model['certificate']['system']
    random=e.rng(10,n,m,system,trial)
    budgets=prefixes(config,n);sigma=config['nu']
    f=np.ascontiguousarray(model['A']-model['B']@model['K0'])
    if resume is None:
        done=0;x=np.zeros(n)
        x,_,_=e.ce_chunk(f,model['B'],model['K0'],x,
            sigma*random.normal(size=(config['ce_burn'],m)),
            random.normal(size=(config['ce_burn'],n)))
        gram=np.zeros((n+m,n+m));cross=np.zeros((n,n+m))
    else:
        done=int(resume['N']);assert done in budgets
        x=resume['x'].copy();gram=resume['gram'].copy();cross=resume['cross'].copy()
        random.bit_generator.state=json.loads(str(resume['rng_state']))
    snapshots={}
    for stop in sorted(set(budgets)|{N//2 for N in budgets}):
        if stop<=done:continue
        while done<stop:
            count=min(512,stop-done)
            x,z,y=e.ce_chunk(f,model['B'],model['K0'],x,
                sigma*random.normal(size=(count,m)),random.normal(size=(count,n)))
            gram+=z.T@z;cross+=y.T@z;done+=count
        snapshots[done]=(gram.copy(),cross.copy())
        if done not in budgets:continue
        theta=e.fit_model(gram,cross)
        g1,c1=snapshots[done//2]
        theta1=e.fit_model(g1,c1);theta2=e.fit_model(gram-g1,cross-c1)
        yield dict(N=done,x=x.copy(),gram=gram.copy(),cross=cross.copy(),
            half_gram=g1.copy(),half_cross=c1.copy(),theta=theta,
            theta1=theta1,theta2=theta2,
            rng_state=np.array(json.dumps(random.bit_generator.state,sort_keys=True)))


def arm_specs(theta,theta1,theta2,config):
    """Inputs contain only observations,known dimensions and frozen constants."""
    n=theta.shape[0];m=theta.shape[1]-n
    singular=np.linalg.svd(theta[:,n:],compute_uv=False)
    proxy=float(np.linalg.norm(theta1[:,n:]-theta2[:,n:],2)/2)
    arms=[dict(mode='dense',k=min(n,m),threshold=None,constant=None,
               kind='fixed',label='dense fixed order')]
    arms += [dict(mode='k'+str(k),k=k,threshold=None,constant=None,
                  kind='fixed',label='fixed order')
             for k in config['fixed_rank_pool'] if k<min(n,m)]
    return arms,singular,proxy


def resolved_arms(fit,config):
    arms,singular,proxy=arm_specs(fit['theta'],fit['theta1'],fit['theta2'],config)
    n=fit['theta'].shape[0];d=fit['theta'].shape[1]
    scale=math.sqrt((d+math.log(1/config['delta']))/fit['N'])
    for mode,constant,label in [
        ('adaptive_paper',config['adaptive_C5'],'paper-form fixed constant'),
        ('sensitivity_C0p5',config['sensitivity_constants'][0],'sensitivity, not selection'),
        ('sensitivity_C1p0',config['sensitivity_constants'][1],'sensitivity, not selection')]:
        threshold=constant*scale
        arms.append(dict(mode=mode,k=int(np.count_nonzero(singular>threshold)),
            threshold=threshold,constant=constant,kind='data_adaptive',label=label))
    # Keep the frozen common-arm order:dense,fixed,paper,split,then sensitivities.
    split=dict(mode='adaptive_split',k=int(np.count_nonzero(singular>proxy)),
        threshold=proxy,constant=None,kind='data_adaptive',label='half-sample proxy multiplier1')
    arms.insert(len(arms)-2,split)
    return arms,singular,proxy


def evaluate_fit(model,fit,spec,config):
    require_compute();n=model['B'].shape[0]
    arms,singular,proxy=resolved_arms(fit,config)
    cache={};policies={};records=[]
    for arm in arms:
        k=arm['k']
        if k not in cache:
            try:
                gain=e.ce_learner(fit['theta'],n,model['Q'],model['R'],k)
                outcome=e.assess(model,gain)
                if outcome['stable']:
                    error=abs(outcome['cost']-model['certificate']['Jstar']-outcome['gap'])/max(1.,abs(outcome['gap']))
                    assert error<1e-7
                    outcome['cost_identity_error']=error
                else:outcome['cost_identity_error']=None
                policies['K_'+str(k)]=gain
                cache[k]=outcome
            except (np.linalg.LinAlgError,ValueError,ArithmeticError) as exc:
                cache[k]=dict(stable=False,gap=None,relative_gap=None,
                    cost=None,rho=None,cost_identity_error=None,failure=repr(exc))
        row=dict(spec,algorithm='CE',N=fit['N'],transitions=fit['N']+config['ce_burn'],
            **arm,noise_proxy=proxy,policy_key='K_'+str(k),**cache[k])
        records.append(row)
    return records,policies,singular


def run_path(model,spec,config,destination,config_sha256,model_sha256,resume_from=None):
    """Checkpoint reuse goes to a NEW directory;never changes prior artifacts."""
    require_compute();verify_sources(config)
    destination=Path(destination)
    assert destination.resolve().is_relative_to(OUT) and not destination.exists()
    destination.mkdir(parents=True)
    started=time.monotonic();all_records=[];artifacts=[];state=None;copied=0
    if resume_from is not None:
        previous=Path(resume_from)
        for N in prefixes(config,spec['n']):
            receipt=previous/f'prefix-{N:09d}.json'
            if not receipt.exists():break
            checkpoint=json.loads(receipt.read_text())
            assert checkpoint['config_sha256']==config_sha256
            assert checkpoint['source_sha256']==e.sha(__file__)
            assert checkpoint['model_sha256']==model_sha256 and checkpoint['spec']==spec
            artifact=previous/checkpoint['artifact']['path']
            assert e.sha(artifact)==checkpoint['artifact']['sha256']
            shutil.copy2(artifact,destination/artifact.name)
            shutil.copy2(receipt,destination/receipt.name)
            with np.load(artifact,allow_pickle=False) as data:
                state={name:data[name].copy() for name in
                    ['x','gram','cross','rng_state']}
            state['N']=N
            all_records.extend(checkpoint['records'])
            artifacts.append(dict(N=N,path=artifact.name,sha256=e.sha(artifact)))
            copied+=1
    for fit in fit_prefixes(model,config,spec['trial'],state):
        records,policies,singular=evaluate_fit(model,fit,spec,config)
        N=fit['N'];path=destination/f'prefix-{N:09d}.npz'
        payload={k:v for k,v in fit.items() if k!='N'}
        digest=npz_new(path,**payload,estimated_B_singular_values=singular,**policies)
        artifact=dict(N=N,path=path.name,sha256=digest)
        checkpoint=dict(status='COMPLETE_PREFIX',spec=spec,N=N,
            config_sha256=config_sha256,source_sha256=e.sha(__file__),
            engine_sha256=e.sha(e.__file__),model_sha256=model_sha256,
            transitions=N+config['ce_burn'],records=records,artifact=artifact)
        save_new(destination/f'prefix-{N:09d}.json',checkpoint)
        all_records.extend(records);artifacts.append(artifact)
    expected=len(prefixes(config,spec['n']))*(len([k for k in config['fixed_rank_pool'] if k<spec['n']])+5)
    assert len(all_records)==expected and len(artifacts)==6
    result=dict(status='COMPLETE',spec=spec,config_sha256=config_sha256,
        source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),
        model_sha256=model_sha256,records=all_records,artifacts=artifacts,
        primitive_transitions=max(prefixes(config,spec['n']))+config['ce_burn'],
        newly_collected_transitions=(max(prefixes(config,spec['n']))-state['N']
            if state is not None else max(prefixes(config,spec['n']))+config['ce_burn']),
        copied_prefixes=copied,resume_from=str(resume_from) if resume_from else None,
        seconds=time.monotonic()-started,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        job=os.environ['SLURM_JOB_ID'])
    save_new(destination/'DONE.json',result)
    return result


def reference_equivalence(model,spec,config,actual,reference_path):
    """Pass-through capture around UNCHANGED ce_run;no performance readout."""
    require_compute();captured=[];last_x=None;randoms=[]
    original_fit=e.fit_model;original_chunk=e.ce_chunk;original_rng=e.rng
    def fit(*args):
        value=original_fit(*args);captured.append(value.copy());return value
    def chunk(*args):
        nonlocal last_x
        value=original_chunk(*args);last_x=value[0].copy();return value
    def rng(*parts):
        value=original_rng(*parts)
        if parts==(10,spec['n'],spec['m'],spec['system'],spec['trial']):randoms.append(value)
        return value
    resolved=dict(config,ce_prefixes=prefixes(config,spec['n']),
        fixed_ranks=config['fixed_rank_pool'])
    try:
        e.fit_model=fit;e.ce_chunk=chunk;e.rng=rng
        reference=e.ce_run(model,spec,resolved,Path(reference_path))
    finally:
        e.fit_model=original_fit;e.ce_chunk=original_chunk;e.rng=original_rng
    assert len(captured)==18 and len(randoms)==1
    observed={(r['N'],r['mode']):r for r in actual['records']}
    checks=0;maximum=0.
    for index,artifact in enumerate(actual['artifacts']):
        path=Path(actual['_directory'])/artifact['path']
        with np.load(path,allow_pickle=False) as data:
            for j,name in enumerate(['theta','theta1','theta2']):
                assert np.array_equal(data[name],captured[3*index+j])
                checks+=1
            if index==len(actual['artifacts'])-1:
                assert np.array_equal(data['x'],last_x)
                assert str(data['rng_state'])==json.dumps(randoms[0].bit_generator.state,sort_keys=True)
            with np.load(Path(reference_path).with_suffix('.npz'),allow_pickle=False) as policies:
                for row in reference['records']:
                    if row['N']!=artifact['N']:continue
                    own=observed[row['N'],row['mode']]
                    assert own['k']==row['k'] and own['stable']==row['stable']
                    for name in ['gap','relative_gap','rho','cost']:
                        assert own.get(name)==row.get(name)
                    key=str(row['N'])+'_'+row['mode']
                    if key in policies:
                        left=data[own['policy_key']];right=policies[key]
                        error=float(np.linalg.norm(left-right)/max(1.,np.linalg.norm(right)))
                        maximum=max(maximum,error);assert error<1e-11;checks+=1
    assert e.sha(e.__file__)==config['scientific_sources']['frozen_engine.py']
    return dict(status='PASS',full_and_half_fits_bitwise=True,
        final_state_and_rng_bitwise=True,common_record_fields_bitwise=True,
        policy_max_relative_error=maximum,checks=checks,
        no_performance_selection_or_readout=True)
