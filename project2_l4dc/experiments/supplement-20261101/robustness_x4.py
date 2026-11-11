"""X4 fixed-policy perturbation diagnostic; no sampling, retraining or output selection."""
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_are,solve_discrete_lyapunov
import engine as e

def sources(cfg,phase):
    result=[]
    if phase=='pilot':
        for system in cfg['pilot_systems']:
            for alg in ['NPG','PI']:
                p=e.OUT/'X1/pilot/revised-base2048'/alg/f's{system}-t7001-m12-null25.json'
                result.append((alg,p,False))
    else:
        for system in cfg['formal_systems']:
            for trial in cfg['formal_trials']:
                for alg in ['CE','NPG','PI']:
                    p=e.OUT/'X1/formal'/alg/f's{system}-t{trial}-m12-null25.json'
                    result.append((alg,p,True))
    return result

def evaluate(a,b,k,ps,ks,reference_gap):
    if k is None:return dict(stable=False,gap=None,relative_gap=None,failure='source_absorbing_failure')
    f=a-b@k;rho=float(max(abs(np.linalg.eigvals(f))))
    if not np.isfinite(rho) or rho>=1-1e-10:return dict(stable=False,rho=rho,gap=None,relative_gap=None)
    cov=solve_discrete_lyapunov(f,np.eye(len(a)));delta=k-ks
    gap=float(np.trace(cov@delta.T@(np.eye(len(k))+b.T@ps@b)@delta))
    pc=solve_discrete_lyapunov(f.T,np.eye(len(a))+k.T@k);direct=float(np.trace(pc-ps))
    err=abs(direct-gap)/max(1.,abs(float(np.trace(pc))));assert err<1e-8
    return dict(stable=True,rho=rho,gap=gap,relative_gap=gap/reference_gap if reference_gap is not None else None,
       relative_defined=reference_gap is not None,independent_gap_error=err)

def main():
    e.require_compute();p=argparse.ArgumentParser();p.add_argument('--phase',choices=['pilot','formal'],required=True);a=p.parse_args()
    root=Path(__file__).parent;cfgpath=root/'configs/X4_v1.json';cfg=json.loads(cfgpath.read_text())
    if a.phase=='formal':
        approval=json.loads((root/'X4/ACCEPTED.json').read_text());assert approval['decision']=='ACCEPTED'
        assert approval['config_sha256']==e.sha(cfgpath) and approval['source_sha256']==e.sha(__file__)
    dest=e.OUT/'X4'/a.phase;assert not dest.exists();dest.mkdir(parents=True)
    records=[];source_manifest=[];perturbations={};model_cache={};max_orth=0.;max_norm_error=0.
    for alg,path,audited in sources(cfg,a.phase):
        data=json.loads(path.read_text());spec=data['spec'];archive=path.with_name(path.stem+'.audit.npz') if audited else path.with_suffix('.npz')
        with np.load(archive) as z:
            aa,bb,k0=z['A'],z['B'],z['K0'];n,m=bb.shape;policies={}
            for mode in ['dense','truncated']:
                candidates=[r for r in data['records'] if r['mode']==mode and (alg!='CE' or r['N']==8192)]
                endpoint=candidates[-1];gain=None;gain_key=None
                if endpoint['stable']:
                    gain_key='K_'+endpoint['assessment_id'] if audited else mode+'_'+str(endpoint['stage'])
                    gain=z[gain_key].copy()
                policies[mode]=(gain,gain_key,endpoint['stable'])
        source_manifest.append(dict(algorithm=alg,path=str(path),json_sha256=e.sha(path),archive=str(archive),archive_sha256=e.sha(archive)))
        _,_,vh=np.linalg.svd(bb,full_matrices=False);v=vh[:2].T;null=np.eye(m)-v@v.T;bnorm=float(np.linalg.norm(bb,2))
        signature=hashlib.sha256(aa.tobytes()+bb.tobytes()+k0.tobytes()).hexdigest()
        for direction in range(10):
            random=np.random.default_rng(np.random.SeedSequence([cfg['direction_seed'],spec['system'],direction]))
            delta=random.normal(size=(n,m))@null;delta/=np.linalg.norm(delta,2)
            for scale in cfg['scales']:
                perturb=scale*bnorm*delta;orth=float(np.linalg.norm(perturb@v,2));norm_error=abs(float(np.linalg.norm(perturb,2))-scale*bnorm)
                assert orth<1e-12 and norm_error<1e-12;max_orth=max(max_orth,orth);max_norm_error=max(max_norm_error,norm_error)
                cache_key=(signature,direction,scale)
                if cache_key not in model_cache:
                    b=bb+perturb;ps=solve_discrete_are(aa,b,np.eye(n),np.eye(m));ks=np.linalg.solve(np.eye(m)+b.T@ps@b,b.T@ps@aa)
                    f0=aa-b@k0;rho0=float(max(abs(np.linalg.eigvals(f0))))
                    ref=float(np.trace(solve_discrete_lyapunov(f0.T,np.eye(n)+k0.T@k0)-ps)) if rho0<1-1e-10 else None
                    if ref is not None:assert ref>0
                    model_id=str(len(model_cache));model_cache[cache_key]=(b,ps,ks,ref,rho0,model_id)
                    perturbations['DeltaB_'+model_id]=perturb
                b,ps,ks,reference_gap,rho0,model_id=model_cache[cache_key]
                for mode,(gain,gain_key,source_stable) in policies.items():
                    q=evaluate(aa,b,gain,ps,ks,reference_gap)
                    row=dict(algorithm=alg,mode=mode,system=spec['system'],trial=spec['trial'],scale=scale,direction=direction,
                      model_id=model_id,source_json=str(path),source_archive=str(archive),source_gain_key=gain_key,
                      source_endpoint_stable=source_stable,reference_K0_rho=rho0,reference_K0_gap=reference_gap,
                      source_initial_gap=data['certificate']['initial_gap'],**q)
                    row['relative_gap_source_normalization']=row['gap']/data['certificate']['initial_gap'] if row['stable'] else None
                    records.append(row)
    assert len(records)==(240 if a.phase=='pilot' else 5760)
    np.savez_compressed(dest/'perturbations.npz',**perturbations)
    e.save(dest/'outputs.json',dict(status='COMPLETE',phase=a.phase,records=records,source_manifest=source_manifest,
      config_sha256=e.sha(cfgpath),source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),
      perturbations_sha256=e.sha(dest/'perturbations.npz'),max_orthogonality_error=max_orth,max_operator_norm_error=max_norm_error,
      new_training_transitions=0,retraining=False,frozen_final_output_only=True,job=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='COMPLETE',phase=a.phase,outputs=len(records),unstable=sum(not r['stable'] for r in records),
       new_training_transitions=0,max_orthogonality_error=max_orth)),flush=True)

if __name__=='__main__':main()
