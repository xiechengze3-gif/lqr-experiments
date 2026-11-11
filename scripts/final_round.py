"""Bounded final round. New files only; historical sources/results stay intact."""
import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from dense_scaling import (atomic_json, rng_for, system as historical_system,
                           evaluate, targets, nominal_chunk, pulse_chunk)
from npg_batched_collector import prepare, batched_chunk
from direct_stein_final import sufficient, combine, fit, correct, update

METHODS=('dense','known_rank','adaptive')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_system(n,rank,seed,tau=0.):
    # Reuse validated isotropic, coupled unstable historical family unchanged.
    # Full-rank control is the nested generator from the authorized local engine.
    if rank==n:
        from final_npg_audit import nested_system
        return nested_system(n,rank,seed)
    return historical_system(dict(n=n,m=n,r=rank,system_seed=seed,
        family='coupled_unstable',stabilizer='isotropic',tail=tau,tail_shape='energy'))


def collect(s,k,x,count,rng,h=16,burn=512,sigma=1.):
    if count%2 or count//2 < k.shape[1]:raise ValueError('Even batch and identifiable halves required')
    n,m=k.shape[1],k.shape[0];f=np.ascontiguousarray(s['A']-s['B']@k)
    cost=np.ascontiguousarray(s['Q']+k.T@s['R']@k)
    x,_=nominal_chunk(f,x,rng.normal(size=(burn,n)))
    x,_,y=pulse_chunk(f,s['B'],cost,x,sigma*rng.normal(size=(1,m)),rng.normal(size=(1,h,n)))
    previous=y[-1];prepared=prepare(f,s['B'],h);parts=[]
    for half in range(2):
        accum=None
        for lo in range(0,count//2,256):
            size=min(256,count//2-lo)
            pulses=sigma*rng.normal(size=(size,m));noise=rng.normal(size=(size,h,n))
            x,starts,y=batched_chunk(f,s['B'],cost,x,pulses,noise,prepared)
            st=sufficient(starts,pulses,y,previous,sigma);previous=y[-1]
            accum=st if accum is None else combine(accum,st)
        parts.append(accum)
    full=fit(combine(*parts));halves=[fit(a)[:2] for a in parts]
    return x,full,halves,burn+(count+1)*h


def quality(s,k):
    gap0=s['initial_gap']
    if not np.isfinite(gap0) or gap0<=1e-10*max(1.,abs(s['Jstar'])):
        raise ValueError('Degenerate initial gap denominator')
    q,p=evaluate(s,k)
    q['normalized_gap']=q['gap']/gap0 if q['gap'] is not None else None
    return q,p


def estimator_rows(s,k,g,z,halves,used,meta,eta):
    q,p=quality(s,k);truth=targets(s,k,16,p);rows=[]
    methods=METHODS+('forced_rank4',) if meta['r']==g.shape[0] else METHODS
    for method in methods:
        gg,zz,info=correct(g,z,'known_rank' if method=='forced_rank4' else method,halves,
                          4 if method=='forced_rank4' else meta['r'] if method=='known_rank' else None)
        for ablation,g1,z1 in [('both_estimated',gg,zz),('exact_G_estimated_Z',truth['G'],zz),
                               ('estimated_G_exact_Z',gg,truth['Z']),('exact_GZ',truth['G'],truth['Z'])]:
            row=dict(meta,method=method,ablation=ablation,transitions=used,**info,
                G_error_fro2=float(np.sum((gg-truth['G'])**2)),
                Z_error_fro2=float(np.sum((zz-truth['Z'])**2)),
                G_error_H_fro2=float(np.sum((gg-truth['GH'])**2)),
                Z_error_H_fro2=float(np.sum((zz-truth['ZH'])**2)),
                G_bias_H_fro2=float(np.sum((truth['G']-truth['GH'])**2)),
                Z_bias_H_fro2=float(np.sum((truth['Z']-truth['ZH'])**2)),
                raw_G_error_fro2=float(np.sum((g-truth['G'])**2)),
                raw_Z_error_fro2=float(np.sum((z-truth['Z'])**2)))
            try:
                candidate,solve=update(k,s['R'],g1,z1,eta)
                after,_=quality(s,candidate);row.update(after,**solve)
            except (np.linalg.LinAlgError,ValueError,ArithmeticError) as e:
                row.update(stable=None,normalized_gap=None,gap=None,failure='numerical_failure',detail=str(e))
            rows.append(row)
    return rows


def fixed(out,cells,budgets,seeds,trials,eta,tag):
    directory=out/tag;directory.mkdir(parents=True,exist_ok=True)
    for n,r,tau in cells:
        for seed in seeds:
            s=make_system(n,r,seed,tau)
            for trial in trials:
                for count in budgets:
                    dest=directory/f'n{n}-r{r}-t{tau}-s{seed}-d{trial}-b{count}.json'
                    if dest.exists():continue
                    start=time.monotonic()
                    _,(g,z,diag),halves,used=collect(s,s['K0'],np.zeros(n),count,
                        rng_for(202610141,n,r,seed,trial),burn=512)
                    meta=dict(n=n,r=r,tau=tau,system_seed=seed,sampling_seed=trial,blocks=count,eta=eta)
                    rows=estimator_rows(s,s['K0'],g,z,halves,used,meta,eta)
                    np.savez(dest.with_suffix('.npz'),G=g,Z=z,G_half1=halves[0][0],Z_half1=halves[0][1],
                             G_half2=halves[1][0],Z_half2=halves[1][1])
                    atomic_json(dest,dict(meta=meta,rows=rows,critic=diag,seconds=time.monotonic()-start,
                        physical_transitions=used,initial_gap=s['initial_gap'],
                        rho0=quality(s,s['K0'])[0]['rho'],B_fro=float(np.linalg.norm(s['B']))))
                    print(json.dumps(dict(done=str(dest.name),seconds=time.monotonic()-start)),flush=True)


def actor(out,seeds,trials,budgets,eta,tag,updates=8,n=50,rank=4):
    directory=out/tag;directory.mkdir(parents=True,exist_ok=True)
    config_sha=sha(out/'frozen_config.json') if tag=='core' else None
    for seed in seeds:
        s=make_system(n,rank,seed)
        system_dir=directory/'systems';system_dir.mkdir(exist_ok=True)
        system_path=system_dir/f'n{n}-r{rank}-s{seed}.npz'
        if not system_path.exists():
            np.savez(system_path,**{k:v for k,v in s.items() if isinstance(v,np.ndarray)},
                     Jstar=s['Jstar'],initial_gap=s['initial_gap'])
        for trial in trials:
            for count in budgets:
                for method in METHODS:
                    dest=directory/f'n{n}-r{rank}-s{seed}-d{trial}-b{count}-{method}.json'
                    if dest.exists():
                        if json.loads(dest.read_text())['meta'].get('config_sha256')!=config_sha:
                            raise RuntimeError('Output config identity changed')
                        continue
                    k=s['K0'].copy();x=np.zeros(n);total=0;rows=[];status='completed'
                    q,_=quality(s,k);rows.append(dict(stage=0,transitions=0,**q))
                    checkpoint_dir=directory/'checkpoints';checkpoint_dir.mkdir(exist_ok=True)
                    checkpoint=checkpoint_dir/(dest.stem+'.npz');first=1
                    if checkpoint.exists():
                        with np.load(checkpoint,allow_pickle=False) as saved:
                            if str(saved['config_sha'])!=str(config_sha):raise RuntimeError('Checkpoint config changed')
                            k=saved['K'].copy();x=saved['x'].copy();total=int(saved['total'])
                            rows=json.loads(str(saved['rows']));first=int(saved['next_stage']);status=str(saved['status'])
                    for stage in range(first,updates+1):
                        if status!='completed':break
                        used=512+(count+1)*16
                        try:
                            x,(g,z,critic),halves,actual=collect(s,k,x,count,
                                rng_for(202610142,n,rank,seed,trial,stage))
                            total+=actual;assert used==actual
                            gg,zz,info=correct(g,z,method,halves,rank if method=='known_rank' else None)
                            candidate,solve=update(k,s['R'],gg,zz,eta)
                            q,_=quality(s,candidate)
                            row=dict(stage=stage,transitions=total,**q,**info,**critic,**solve)
                            if not q['stable']:status='controller_instability';row['failure']=status
                            rows.append(row);k=candidate
                        except (np.linalg.LinAlgError,ValueError,ArithmeticError) as e:
                            # Collector is fixed length; failed fit occurs after its full sampling.
                            if total < stage*used:total+=used
                            status='numerical_failure';rows.append(dict(stage=stage,transitions=total,
                                stable=None,gap=None,normalized_gap=None,failure=status,detail=str(e)))
                        atomic_json(directory/'progress.json',dict(seed=seed,trial=trial,count=count,method=method,stage=stage,status=status))
                        temporary=checkpoint.with_suffix('.tmp')
                        with temporary.open('wb') as stream:
                            np.savez(stream,K=k,x=x,total=total,rows=json.dumps(rows,allow_nan=False),
                                     next_stage=stage+1,status=status,config_sha=str(config_sha))
                        os.replace(temporary,checkpoint)
                        if status!='completed':break
                    meta=dict(n=n,r=rank,system_seed=seed,sampling_seed=trial,blocks=count,eta=eta,
                              updates=updates,method=method,status=status,
                              config_sha256=config_sha,
                              planned_transitions=updates*(512+(count+1)*16),actual_transitions=total)
                    atomic_json(dest,dict(meta=meta,rows=rows,initial_gap=s['initial_gap'],Jstar=s['Jstar']))
                    # Save final controllers independently of offline evaluation.
                    np.savez(dest.with_suffix('.npz'),K=k,x=x)
                    print(json.dumps(dict(actor=dest.name,status=status,final_gap=rows[-1]['normalized_gap'])),flush=True)


def core_seed(arguments):
    out,seed,cfg=arguments
    for name,digest in cfg['sources'].items():
        if sha(ROOT/name)!=digest:raise RuntimeError('Frozen source changed: '+name)
    actor(Path(out),[seed],cfg['sampling_seeds'],cfg['blocks_per_update'],cfg['eta'],'core')


def benchmark(out):
    s=make_system(50,4,801);start=time.monotonic()
    _,_,_,used=collect(s,s['K0'],np.zeros(50),32768,rng_for(123456))
    duration=time.monotonic()-start
    # Includes first-call compilation: conservative ceiling estimate.
    transitions=8*3*8*sum(512+(b+1)*16 for b in (32768,131072,524288))
    result=dict(seconds=duration,transitions=used,transitions_per_second=used/duration,
        proposed_core_transitions=transitions,proposed_core_hours=transitions/used*duration/3600,
        working_array_upper_bound_MB=64.,threads=1,output=str(out),
        temp=os.environ.get('TEMP'),numba_cache=os.environ.get('NUMBA_CACHE_DIR'))
    atomic_json(out/'resource_benchmark.json',result);print(json.dumps(result),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['benchmark','pilot-fixed','debug','debug-medium','core','scaling','rank8'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--eta',type=float,default=.25)
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    if args.mode=='benchmark':benchmark(out)
    elif args.mode=='pilot-fixed':
        fixed(out,[(50,4,0.)],[32768,131072],[801,802],[0,1],args.eta,'pilot-fixed')
    elif args.mode=='debug':actor(out,[901,902],[0,1],[32768],args.eta,'debug')
    elif args.mode=='debug-medium':actor(out,[801,802],[0],[131072],args.eta,'pilot-learning')
    elif args.mode=='core':
        cfg=json.loads((out/'frozen_config.json').read_text())
        with ProcessPoolExecutor(max_workers=cfg['workers']) as pool:
            list(pool.map(core_seed,[(str(out),seed,cfg) for seed in cfg['system_seeds']]))
    elif args.mode=='scaling':
        cells=[(50,r,0.) for r in (1,2,4,8,16,50)]+[(25,4,0.),(100,4,0.)]+[(50,4,t) for t in (.03,.1)]
        fixed(out,cells,[32768,131072],[1001,1002],[0],args.eta,'scaling')
    elif args.mode=='rank8':actor(out,[1101,1102],[0],[131072],args.eta,'rank8',rank=8)


if __name__=='__main__':main()
