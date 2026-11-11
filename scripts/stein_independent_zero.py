"""Stein PI/NPG on independent Gaussian A, Haar B and exact zero K0."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from threadpoolctl import threadpool_limits
import project2_overnight as core
from ce_matched_initial_gap import performance_gap

SOURCES=['dense_scaling.py','scripts/npg_batched_collector.py','scripts/direct_stein_final.py',
    'scripts/project2_overnight.py','scripts/ce_matched_initial_gap.py','scripts/rank_sweep100.py',
    'scripts/actuation_redundancy.py','scripts/stein_independent_zero.py']


def identity(cfg):
    return dict(config_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        sources={p:core.sha(ROOT/p) for p in SOURCES})


def tasks(cfg,phase):
    result=[]
    for n in cfg['dimensions']:
        for seed in cfg[phase+'_system_seeds']:
            for alg in ('NPG','PI'):
                profiles=[None] if alg=='NPG' else cfg['PI'][phase+'_N']
                for count in profiles:
                    for method in cfg['methods']:
                        result.append(dict(id=len(result),n=n,r=cfg['rank'],seed=seed,algorithm=alg,
                            method=method,N=count,phase=phase))
    return result


def schedule(cfg,spec):
    if spec['algorithm']=='PI':return [spec['N']]*cfg['PI']['updates']
    return [n for n,times in cfg['NPG']['schedule_segments'] for _ in range(times)]


def plant_path(out,n,seed):return out/'systems'/f'n{n:03d}-s{seed:04d}.npz'


def load(cfg,n,seed):
    p=plant_path(Path(cfg['output']),n,seed)
    proof=json.loads(p.with_suffix('.json').read_text())
    assert core.sha(p)==proof['sha256']
    with np.load(p,allow_pickle=False) as data:
        return {k:data[k].copy() if data[k].ndim else data[k].item() for k in data.files}


def prepare(cfg,ident):
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    if (out/'preflight.json').exists():assert json.loads((out/'preflight.json').read_text())['identity']==ident;return
    systems=[]
    for n in cfg['dimensions']:
        for seed in cfg['pilot_system_seeds']+cfg['confirm_system_seeds']:
            path=plant_path(out,n,seed)
            if path.exists():
                meta=json.loads(path.with_suffix('.json').read_text());assert meta['identity']==ident
                assert meta['sha256']==core.sha(path);systems.append(meta);continue
            # Initial policy has no plant, optimal-policy, rank or evaluator input.
            k0=np.zeros((n,n))
            raw=core.rng_for(cfg['A_rng_namespace'],n,seed).normal(size=(n,n))/math.sqrt(n)
            a=cfg['A_radius']/max(abs(np.linalg.eigvals(raw)))*raw
            brng=core.rng_for(cfg['B_rng_namespace'],n,seed)
            u,v=core.orth(brng,n),core.orth(brng,n)
            b=u[:,:cfg['rank']]@v[:,:cfg['rank']].T
            ks,ps=core.dare(a,b,np.eye(n),np.eye(n))
            p0=solve_discrete_lyapunov(a.T,np.eye(n))
            gap=float(np.trace(p0-ps));assert gap>0
            plant=dict(A=a,B=b,Q=np.eye(n),R=np.eye(n),W=np.eye(n),K0=k0,Kstar=ks,
                Jstar=float(np.trace(ps)),P0=p0,initial_gap=gap)
            q=core.quality(plant,k0);assert q['stable'] and abs(q['g']-1)<1e-10
            path.parent.mkdir(exist_ok=True)
            with path.open('wb') as f:np.savez(f,**plant)
            meta=dict(identity=ident,n=n,rank=cfg['rank'],seed=seed,sha256=core.sha(path),
                initial_gap=gap,rho_A=q['rho'],K0_rank=0,K0_fro2=0.,A_B_independent_by_construction=True,
                A_array_sha256=hashlib.sha256(a.tobytes()).hexdigest(),B_array_sha256=hashlib.sha256(b.tobytes()).hexdigest())
            core.atomic_json(path.with_suffix('.json'),meta);systems.append(meta)
    benchmarks=[]
    for n in cfg['dimensions']:
        s=load(cfg,n,cfg['pilot_system_seeds'][0]);start=time.monotonic()
        count=65536
        d=list(core.collect_prefixes(s,s['K0'],np.zeros(n),[count],core.rng_for(2026102287,n),cfg['H'],cfg['burn'],cfg['sigma']))[-1]
        elapsed=time.monotonic()-start;before=time.monotonic()
        for method in cfg['methods']:
            g,z,_,_=core.v4_correct(d['G'],d['Z'],method,cfg['rank'],d['halves'])
            core.quality(s,core.greedy(s['K0'],s['R'],g,z))
        benchmarks.append(dict(n=n,N=count,collector_seconds=elapsed,
            seconds_per_block=elapsed/count,postprocess_seconds_for_three=time.monotonic()-before))
    core.atomic_json(out/'preflight.json',dict(status='PASS',identity=ident,systems=systems,
        benchmarks=benchmarks,pilot_tasks=len(tasks(cfg,'pilot')),formal_tasks=len(tasks(cfg,'confirm')),
        peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        paths={key:os.environ.get(key) for key in ('TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR')}))
    core.atomic_json(out/'resolved_config.json',dict(cfg,identity=ident))
    print(json.dumps(dict(status='PASS',benchmarks=benchmarks,systems=len(systems))),flush=True)


def run(cfg,ident,phase,index):
    out=Path(cfg['output']);spec=tasks(cfg,phase)[index]
    dest=out/'raw'/f'{phase}-{index:04d}.json';cp=dest.with_suffix('.npz')
    if dest.exists():assert json.loads(dest.read_text())['identity']==ident;return
    s=load(cfg,spec['n'],spec['seed']);counts=schedule(cfg,spec)
    uses=[cfg['burn']+(n+1)*cfg['H'] for n in counts];cumulative=np.cumsum(uses).tolist()
    k=s['K0'].copy();x=np.zeros(spec['n']);actual=0;failed=False;start_stage=0
    rows=[dict(stage=0,transitions=0,actual_transitions=0,observed=True,**core.quality(s,k))];policies=[k.copy()]
    if cp.exists():
        with np.load(cp,allow_pickle=False) as saved:
            assert str(saved['identity'])==json.dumps(ident,sort_keys=True)
            k=saved['K'].copy();x=saved['x'].copy();actual=int(saved['actual']);failed=bool(saved['failed'])
            rows=json.loads(str(saved['rows']));policies=list(saved['policies']);start_stage=int(saved['next_stage'])
    began=time.monotonic();stage_times=[]
    for stage in range(start_stage,len(counts)):
        base=dict(stage=stage+1,N=counts[stage],transitions=cumulative[stage])
        if failed:
            rows.append(dict(base,actual_transitions=actual,observed=False,stable=False,gap=None,g=None,failure='prior_failure'))
            policies.append(k.copy());continue
        start=time.monotonic()
        try:
            d=list(core.collect_prefixes(s,k,x,[counts[stage]],
                core.rng_for(cfg['data_rng_namespace'],spec['n'],spec['seed'],stage),cfg['H'],cfg['burn'],cfg['sigma']))[-1]
            actual+=d['transitions'];x=d['x']
            rawsha=hashlib.sha256(d['G'].tobytes()+d['Z'].tobytes()).hexdigest()
            if spec['algorithm']=='PI':
                g,z,retained,threshold=core.v4_correct(d['G'],d['Z'],spec['method'],spec['r'],d['halves'])
                candidate=core.greedy(k,s['R'],g,z)
            else:
                z=d['Z'];threshold=None
                if spec['method']=='dense':retained=spec['n']
                elif spec['method']=='known_rank':retained=spec['r']
                else:
                    threshold=core.op(d['halves'][0][1]-d['halves'][1][1])/2
                    retained=int(np.count_nonzero(np.linalg.svd(z,compute_uv=False)>threshold))
                corrected=z if retained==spec['n'] else core.trunc(z,retained)
                candidate=k-cfg['NPG']['eta']*(s['R']@k+corrected)
            q=core.quality(s,candidate);k=candidate
            row=dict(base,actual_transitions=actual,observed=True,retained_rank=retained,
                threshold=threshold,raw_G_Z_sha256=rawsha,**q)
            failed=not q['stable'];row['failure']='controller_instability' if failed else None
        except (ArithmeticError,ValueError,np.linalg.LinAlgError) as err:
            if actual<cumulative[stage]:actual+=uses[stage]
            k=np.full_like(k,np.nan);failed=True
            row=dict(base,actual_transitions=actual,observed=True,stable=False,gap=None,g=None,
                failure='numerical_failure',detail=str(err))
        rows.append(row);policies.append(k.copy());stage_times.append(dict(stage=stage+1,N=counts[stage],seconds=time.monotonic()-start))
        cp.parent.mkdir(parents=True,exist_ok=True);temp=cp.with_suffix('.tmp')
        with temp.open('wb') as f:np.savez(f,identity=json.dumps(ident,sort_keys=True),K=k,x=x,
            actual=actual,failed=failed,rows=json.dumps(rows),policies=np.asarray(policies),next_stage=stage+1)
        temp.replace(cp)
    # Commit padded failed-path records and all stage policies as well.
    with cp.with_suffix('.tmp').open('wb') as f:np.savez(f,identity=json.dumps(ident,sort_keys=True),K=k,x=x,
        actual=actual,failed=failed,rows=json.dumps(rows),policies=np.asarray(policies),next_stage=len(counts))
    cp.with_suffix('.tmp').replace(cp)
    core.atomic_json(dest,dict(identity=ident,spec=spec,rows=rows,status='failed' if failed else 'completed',
        actual_transitions=actual,planned_transitions=sum(uses),seconds=time.monotonic()-began,
        stage_timings=stage_times,policy_sha256=core.sha(cp),job=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(spec=spec,status='failed' if failed else 'completed',seconds=time.monotonic()-began,final=rows[-1])),flush=True)


def report(cfg,ident,phase):
    out=Path(cfg['output']);dest=out/f'report-{phase}';dest.mkdir(exist_ok=True)
    data=[json.loads((out/'raw'/f'{phase}-{t["id"]:04d}.json').read_text()) for t in tasks(cfg,phase)]
    allrows=[];endpoints=[];checked=0;error=0.;first_raw={}
    for item in data:
        assert item['identity']==ident;spec=item['spec'];s=load(cfg,spec['n'],spec['seed'])
        path=out/'raw'/f'{phase}-{spec["id"]:04d}.npz';assert core.sha(path)==item['policy_sha256']
        with np.load(path,allow_pickle=False) as saved:
            assert len(saved['policies'])==len(item['rows'])
            for row,k in zip(item['rows'],saved['policies']):
                if not row['observed']:continue
                gap=performance_gap(s,k)[0] if np.isfinite(k).all() else math.inf
                assert bool(np.isfinite(gap))==row['stable']
                if row['stable']:
                    err=abs(gap-row['gap']);error=max(error,err);assert err<2e-8
                    assert abs(gap/s['initial_gap']-row['g'])<1e-8
                checked+=1
        key=(spec['n'],spec['seed'],spec['algorithm'],spec['N'])
        first=item['rows'][1].get('raw_G_Z_sha256')
        if first is not None:
            assert key not in first_raw or first_raw[key]==first
            first_raw[key]=first
        allrows += [dict(spec,**r) for r in item['rows']]
        last=item['rows'][-1]
        endpoints.append(dict(spec,planned_transitions=item['planned_transitions'],actual_transitions=item['actual_transitions'],
            stable=last['stable'],g=last.get('g'),gap=last.get('gap'),success=bool(last['stable'] and last['g']<=.1)))
    grouped={}
    for row in allrows:grouped.setdefault((row['n'],row['algorithm'],row['N'] if row['algorithm']=='PI' else None,row['method'],row['stage']),[]).append(row)
    curves=[]
    for (n,alg,profile,method,stage),rows in sorted(grouped.items(),key=str):
        values=[r['g'] if r['stable'] else math.inf for r in rows];med=float(np.median(values))
        curves.append(dict(n=n,algorithm=alg,N_profile=profile,method=method,stage=stage,
            transitions=rows[0]['transitions'],systems=len(rows),stable=sum(r['stable'] for r in rows),
            successes=sum(v<=.1 for v in values),g_median=med if math.isfinite(med) else None))
    for name,rr in [('all_stages',allrows),('endpoints',endpoints),('relative_error_curves',curves)]:core.write_csv(dest/(name+'.csv'),rr)
    core.atomic_json(dest/'summary.json',dict(status='complete',phase=phase,trajectories=len(data),
        endpoints=endpoints,metric=cfg['primary_metric'],policy_evaluations_checked=checked,maximum_gap_error=error,
        same_raw_first_stage_triplets=len(first_raw),physical_transitions=sum(d['actual_transitions'] for d in data)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,len(cfg['dimensions']),figsize=(11,7),layout='constrained')
    colors={'dense':'#ad493b','known_rank':'#1777a4','adaptive':'#25915a'}
    for row,alg in enumerate(('NPG','PI')):
        for ax,n in zip(axes[row],cfg['dimensions']):
            for method in cfg['methods']:
                if alg=='NPG':
                    rr=sorted([r for r in curves if r['n']==n and r['algorithm']==alg and r['method']==method],key=lambda r:r['stage'])
                else:
                    rr=sorted([r for r in curves if r['n']==n and r['algorithm']==alg and r['method']==method and r['stage']==cfg['PI']['updates']],key=lambda r:r['transitions'])
                ax.plot([r['transitions'] for r in rr if r['transitions']>0],[r['g_median'] if r['g_median'] is not None else np.nan for r in rr if r['transitions']>0],'-o',color=colors[method],label=method)
            ax.axhline(.1,color='.5',ls=':');ax.set(xscale='log',yscale='log',xlabel='Primitive transitions',ylabel='Relative gap g',title=f'{alg} | n={n}, r=4')
            ax.legend()
    fig.suptitle('Independent Gaussian A and Haar B | K0=0 | failures retained')
    for ext in ('png','svg'):fig.savefig(dest/('stein_relative_error.'+ext),dpi=170)
    plt.close(fig)
    print(json.dumps(dict(status='complete',phase=phase,trajectories=len(data),checked=checked)),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','task','report'])
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--phase',choices=['pilot','confirm'],default='pilot');p.add_argument('--task-id',type=int,default=0)
    a=p.parse_args();assert os.environ.get('SLURM_JOB_ID')
    cfg=json.loads(a.manifest.read_text());ident=identity(cfg)
    for key,wanted in [('TMPDIR',cfg['temp']),('XDG_CACHE_HOME',cfg['cache']),('NUMBA_CACHE_DIR',cfg['cache']+'/numba'),('MPLCONFIGDIR',cfg['cache']+'/matplotlib')]:
        assert os.environ.get(key)==wanted;Path(wanted).mkdir(parents=True,exist_ok=True)
    with threadpool_limits(1):
        if a.mode=='prepare':prepare(cfg,ident)
        elif a.mode=='task':run(cfg,ident,a.phase,a.task_id)
        else:report(cfg,ident,a.phase)


if __name__=='__main__':main()
