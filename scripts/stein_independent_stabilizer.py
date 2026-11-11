"""Stein on independent unstable Gaussian A/B and a stability-only initializer."""
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
    'scripts/actuation_redundancy.py','scripts/stein_independent_stabilizer.py','scripts/independent_ab_study_support.py','scripts/independent_ab_stabilizer.py']


def identity(cfg):
    return dict(config_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        sources={p:core.sha(ROOT/p) for p in SOURCES})


def tasks(cfg,phase):
    result=[]
    for n in cfg['dimensions']:
        for seed in cfg[phase+'_system_seeds']:
            for alg in cfg['algorithms']:
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
    from independent_ab_study_support import stein_prepare
    return stein_prepare(cfg,ident,core,plant_path)


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
        except (ArithmeticError,ValueError,np.linalg.LinAlgError,AssertionError) as err:
            if actual<cumulative[stage]:actual+=uses[stage]
            # Collection failure count is an upper bound, not an exact observed count.
            k=np.full_like(k,np.nan);failed=True
            row=dict(base,actual_transitions=actual,observed=True,stable=False,gap=None,g=None,
                failure='numerical_failure',detail=str(err),count_accuracy='upper_bound_on_failure')
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
                    err=abs(gap-row['gap']);error=max(error,err);assert err<2e-7*max(1.,abs(gap))
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
    fig,axes=plt.subplots(len(cfg['algorithms']),len(cfg['dimensions']),figsize=(11,4),layout='constrained',squeeze=False)
    colors={'dense':'#ad493b','known_rank':'#1777a4','adaptive':'#25915a'}
    for row,alg in enumerate(cfg['algorithms']):
        for ax,n in zip(axes[row],cfg['dimensions']):
            for method in cfg['methods']:
                if alg=='NPG':
                    rr=sorted([r for r in curves if r['n']==n and r['algorithm']==alg and r['method']==method],key=lambda r:r['stage'])
                else:
                    rr=sorted([r for r in curves if r['n']==n and r['algorithm']==alg and r['method']==method and r['stage']==cfg['PI']['updates']],key=lambda r:r['transitions'])
                ax.plot([r['transitions'] for r in rr if r['transitions']>0],[r['g_median'] if r['g_median'] is not None else np.nan for r in rr if r['transitions']>0],'-o',color=colors[method],label=method)
            ax.axhline(.1,color='.5',ls=':');ax.set(xscale='log',yscale='log',xlabel='Primitive transitions',ylabel='Relative gap g',title=f'{alg} | n={n}, r=4')
            ax.legend()
    fig.suptitle('Independent unstable Gaussian A and Haar B | stability-only K0')
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
