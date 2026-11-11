"""100d CE, absolute gap .1, ranks16/32/64/100. Compute nodes only."""
import argparse
import csv
import hashlib
import json
import math
import os
import resource
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import atomic_json,ce,dare,evaluate,op,orth,require_compute,rng_for,system,tails,trunc


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extended_system(task):
    """Same formulas/RNG as historical system; permit rank=n and empty tails.

    Historical rank<n behavior is tested array-by-array before production.
    Do not replace the full-rank cell with the different nested generator.
    """
    n,rank=task['n'],task['r']
    if task['m']!=n or not 1<=rank<=n:raise ValueError('m=n, 1<=rank<=n required')
    rng=rng_for(981113,n,task['system_seed'])
    state_basis,input_basis=orth(rng,n),orth(rng,n)
    q_basis,r_basis=orth(rng,n),orth(rng,n)
    q=(q_basis*np.linspace(1.,3.,n))@q_basis.T
    r=(r_basis*np.linspace(1.,2.5,n))@r_basis.T
    diagonal=rng.uniform(-.60,.65,n);diagonal[:rank]=.78
    latent=np.diag(diagonal)+.10*np.diag(np.ones(n-1),1)
    latent+=.025/math.sqrt(n)*rng.normal(size=(n,n))
    latent*=.9/op(latent)
    f0=state_basis@latent@state_basis.T
    left=state_basis if task['family']=='coupled_unstable' else orth(rng,n)
    singular=np.zeros(n);singular[:rank]=np.linspace(1.2,.9,rank)
    b0=(left*singular)@input_basis.T
    initial=np.full(n,.03);initial[:rank]=.4/singular[:rank]
    if task.get('stabilizer')=='isotropic':initial[:]=.35
    k0=(input_basis*initial)@state_basis.T
    a=f0+b0@k0
    level,shape=task['tail'],task['tail_shape']
    if rank==n:
        if level!=0.:raise ValueError('Full rank has no trailing singular values')
    elif shape=='flat':singular[rank:]=level
    elif shape=='energy':singular[rank:]=level/math.sqrt(n-rank)
    elif shape=='decay':singular[rank:]=level*np.arange(1,n-rank+1,dtype=float)**-1.5
    else:raise ValueError(shape)
    b=(left*singular)@input_basis.T
    f_bound=.9+.03*.3;k_bound=.4/.9
    if task.get('stabilizer')=='isotropic':f_bound=.925;k_bound=.35
    p0=(3+2.5*k_bound**2)/(1-f_bound**2)
    ks,ps=dare(a,b,q,r)
    s=dict(A=a,B=b,Q=q,R=r,W=np.eye(n),K0=k0,Kstar=ks,Jstar=float(np.trace(ps)),
           p0=p0,input_basis=input_basis[:,:rank])
    f=a-b@k0;p=solve_discrete_lyapunov(f.T,q+k0.T@r@k0)
    s['initial_gap']=float(np.trace(p)-s['Jstar'])
    if s['initial_gap']<=0 or op(f)>f_bound+1e-10:raise ArithmeticError('Initial certificate failed')
    if task['family']=='coupled_unstable' and np.max(np.abs(np.linalg.eigvals(a)))<=1:
        raise ArithmeticError('Main family must be open-loop unstable')
    s['diagnostics']=dict(initial_gap=s['initial_gap'],Jstar=s['Jstar'],F0_op=op(f),
                           A_rho=float(np.max(np.abs(np.linalg.eigvals(a)))),B_fro2=float(np.sum(b*b)),
                           B=tails(b,rank),matrix_sha256={k:hashlib.sha256(s[k].tobytes()).hexdigest()
                               for k in ('A','B','Q','R','W','K0')})
    return s


def config():
    cfg=read(ROOT/'manifest.json')
    for name,digest in cfg['sources'].items():
        assert sha(ROOT/name)==digest, name
    return cfg


def verify(cfg,out):
    out.mkdir(parents=True,exist_ok=True);checks=[]
    start=time.monotonic()
    for rank in (16,32,64):
        for seed in (0,1):
            task=dict(n=100,m=100,r=rank,system_seed=seed,trial_seed=0,
                      family='coupled_unstable',stabilizer='isotropic',tail=0.,tail_shape='energy')
            a,b=system(task),extended_system(task)
            for key in ('A','B','Q','R','W','K0','Kstar','input_basis'):
                np.testing.assert_array_equal(a[key],b[key])
            assert a['Jstar']==b['Jstar'] and a['initial_gap']==b['initial_gap']
            checks.append(dict(rank=rank,seed=seed,old_generator_bitwise_equal=True))
    for item in cfg['reused']:
        p=ROOT/item['bundle_path'];assert sha(p)==item['sha256']
        old=read(p);task=item['task'];s=extended_system(task)
        old_rows=old['records'];den=next(r['gap']/r['relative_gap'] for r in old_rows if r.get('relative_gap',0)>0 and r.get('gap') is not None)
        np.testing.assert_allclose(s['initial_gap'],den,rtol=1e-8,atol=1e-7)
        current,_=ce(dict(task,budgets=[512],sigma=1.),s)
        expected=[r for r in old_rows if r['N']==512]
        assert len(current)==len(expected)==2
        for a,b in zip(current,expected):
            assert a['method']==b['method'] and a['stable']==b['stable']
            for key in ('gap','cost','rho'):
                if a.get(key) is not None:np.testing.assert_allclose(a[key],b[key],rtol=1e-8,atol=1e-7)
        checks.append(dict(rank=task['r'],seed=task['system_seed'],historical_first_prefix_replayed=True))
    for seed in (0,1):
        task=dict(n=100,m=100,r=100,system_seed=seed,trial_seed=0,family='coupled_unstable',stabilizer='isotropic',tail=0.,tail_shape='energy')
        s=extended_system(task);assert np.linalg.matrix_rank(s['B'])==100
        np.testing.assert_allclose(trunc(s['B'],100),s['B'],rtol=1e-12,atol=1e-12)
        records,_=ce(dict(task,budgets=[512],sigma=1.),s)
        a,b=records;assert a['stable']==b['stable']
        for key in ('gap','cost','rho','B_error_fro2'):
            if a.get(key) is not None:np.testing.assert_allclose(a[key],b[key],rtol=1e-8,atol=1e-7)
        checks.append(dict(rank=100,seed=seed,full_rank_dense_truncated_numerically_equal=True))
    atomic_json(out/'verification.json',dict(status='PASS',identity=sha(ROOT/'manifest.json'),checks=checks,
                seconds=time.monotonic()-start,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(verification='PASS',checks=len(checks))),flush=True)


def run(cfg,out,index):
    proof=read(out/'verification.json');assert proof['status']=='PASS' and proof['identity']==sha(ROOT/'manifest.json')
    task=cfg['new_tasks'][index];dest=out/'raw'/f'task-{index:03d}.json'
    if dest.exists():assert read(dest)['identity']==proof['identity'];return
    start=time.monotonic();s=extended_system(task)
    rows,_=ce(dict(task,budgets=cfg['budgets'],sigma=1.),s)
    atomic_json(dest,dict(task=task,records=rows,identity=proof['identity'],diagnostics=s['diagnostics'],
                actual_physical_transitions=max(cfg['budgets'])+512,seconds=time.monotonic()-start,
                slurm_job_id=os.environ['SLURM_JOB_ID'],execution_location='Grace Slurm compute node'))
    np.savez(dest.with_suffix('.npz'),**{k:v for k,v in s.items() if isinstance(v,np.ndarray)})
    print(json.dumps(dict(task=task,seconds=time.monotonic()-start)),flush=True)


def report(cfg,out):
    out.mkdir(parents=True,exist_ok=True);rows=[];inputs=[];missing=[];ident=sha(ROOT/'manifest.json')
    sources=[(ROOT/d['bundle_path'],d['task'],'historical',d['sha256']) for d in cfg['reused']]
    for i,task in enumerate(cfg['new_tasks']):
        p=out/'raw'/f'task-{i:03d}.json'
        if not p.exists():missing.append(i);continue
        assert read(p)['identity']==ident
        sources.append((p,task,'new_Grace',sha(p)))
    for path,task,origin,digest in sources:
        assert sha(path)==digest;data=read(path)
        inputs.append(dict(path=str(path),sha256=digest,origin=origin,r=task['r'],seed=task['system_seed']))
        for r in data['records']:
            rows.append(dict(rank=task['r'],seed=task['system_seed'],method=r['method'],budget=r['transitions'],
                             absolute_gap=r.get('gap'),g=r.get('relative_gap'),stable=r.get('stable'),
                             success=bool(r.get('stable') and r.get('gap') is not None and r['gap']<=cfg['absolute_epsilon']),
                             failure=r.get('failure'),origin=origin))
    groups=defaultdict(list)
    for r in rows:groups[r['rank'],r['method'],r['budget']].append(r)
    summary=[]
    for (rank,method,budget),values in sorted(groups.items()):
        gaps=[r['absolute_gap'] for r in values if r['stable'] and r['absolute_gap'] is not None]
        summary.append(dict(rank=rank,method=method,budget=budget,systems=len(values),
                            successes=sum(r['success'] for r in values),failures=sum(not r['stable'] for r in values),
                            median_absolute_gap=statistics.median(gaps) if gaps else None,
                            all_succeed=len(values)==2 and all(r['success'] for r in values)))
    attainment=[]
    for rank in cfg['ranks']:
        for method in ('raw','truncated'):
            vals=[r for r in summary if r['rank']==rank and r['method']==method]
            met=[r['budget'] for r in vals if r['all_succeed']]
            attainment.append(dict(rank=rank,method=method,epsilon=.1,minimum_tested_budget=min(met) if met else None,
                                    right_censored=not bool(met),maximum_tested_budget=max(cfg['budgets'])+512))
    full_equal=[]
    for seed in (0,1):
        for budget in cfg['budgets']:
            vals=[r for r in rows if r['rank']==100 and r['seed']==seed and r['budget']==budget+512]
            if len(vals)!=2:continue
            a,b=vals;assert a['stable']==b['stable']
            if a['absolute_gap'] is not None:
                np.testing.assert_allclose(a['absolute_gap'],b['absolute_gap'],rtol=1e-8,atol=1e-7)
            full_equal.append(dict(seed=seed,budget=budget+512,status='PASS'))
    dest=out/'report';dest.mkdir(exist_ok=True)
    for name,values in [('endpoints',rows),('success_by_budget',summary),('sample_to_accuracy',attainment),('sources',inputs)]:
        with (dest/f'{name}.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    for ax,method,title in zip(axes,('raw','truncated'),('Dense CE','Known-rank CE')):
        for rank in cfg['ranks']:
            vals=[r for r in summary if r['rank']==rank and r['method']==method]
            points=[r for r in vals if r['median_absolute_gap'] is not None]
            ax.plot([r['budget'] for r in points],[max(r['median_absolute_gap'],1e-10) for r in points],'-o',ms=3,label=f'r={rank}')
        ax.axhline(.1,color='#dc2626',ls='--');ax.set(xscale='log',yscale='log',xlabel='Total primitive transitions',ylabel='Median absolute J-Jstar',title=title);ax.grid(alpha=.2);ax.legend()
    fig.suptitle('100d CE | absolute gap target 0.1 | 2 systems per rank | fixed prefixes')
    fig.tight_layout()
    for ext in ('png','svg'):fig.savefig(dest/f'absolute_gap_curves.{ext}',dpi=170)
    plt.close(fig)
    status='COMPLETE' if not missing and len(inputs)==8 and len(full_equal)==14 else 'INCOMPLETE'
    atomic_json(dest/'summary.json',dict(status=status,absolute_epsilon=.1,ranks=cfg['ranks'],new_tasks=4,
                completed_new_tasks=4-len(missing),reused_datasets=4,fullrank_checks=full_equal,missing=missing,
                new_physical_transitions=sum(read(p)['actual_physical_transitions'] for p,_,origin,_ in sources if origin=='new_Grace'),
                slurm_job_id=os.environ['SLURM_JOB_ID']))
    lines=['# 100d CE high-rank comparison','',f'Status: {status}. Absolute J-Jstar <= 0.1; all 2 systems must attain.','',
           '| rank | method | minimum tested total transitions |','| --- | --- | ---: |']
    for r in attainment:lines.append(f"| {r['rank']} | {r['method']} | {r['minimum_tested_budget'] if not r['right_censored'] else '> '+str(r['maximum_tested_budget'])} |")
    lines+=['','![Absolute-gap curves](absolute_gap_curves.png)','',
             'Same historical generator extended to permit r=n; old-rank arrays verified bitwise. A and B still vary with rank, so this is not an isolated causal rank effect. Two systems and a coarse budget grid are descriptive, not an exact sample-complexity law. Full-rank truncated and dense outputs agree numerically; both postprocessors share one physical trajectory per dataset.']
    (dest/'findings.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(status=status,attainment=attainment)),flush=True)


if __name__=='__main__':
    require_compute();parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['verify','run','report'])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--task-id',type=int)
    args=parser.parse_args();cfg=config()
    if args.mode=='verify':verify(cfg,args.output)
    elif args.mode=='run':run(cfg,args.output,args.task_id)
    else:report(cfg,args.output)
