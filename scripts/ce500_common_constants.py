"""Common system constants across rank; unchanged paired OLS CE collector."""
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
from threadpoolctl import threadpool_limits,threadpool_info
import rank_sweep100 as e
import ce500_matched_gap as engine
from ce_matched_initial_gap import performance_gap

SOURCES=list(dict.fromkeys(engine.SOURCES+['scripts/ce500_common_constants.py','scripts/ce500_common_constant_prepare.py','scripts/ce500_common_constant_report.py','scripts/common_constant_spectrum_preflight.py']))


def identity(cfg):
    return dict(config_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        sources={name:e.sha(ROOT/name) for name in SOURCES},initialization='shared_fixed_pole_K0_and_common_P0')


def write_csv(path,rows):
    if not rows:return
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        w.writeheader();w.writerows(rows)


def prepare(cfg,ident):
    from ce500_common_constant_prepare import prepare as prepare_shared
    return prepare_shared(cfg,ident,e,engine)


def task(cfg,ident,phase,index):
    out=Path(cfg['output']);assert e.read(out/'preflight.json')['status']=='PASS'
    seeds=cfg[phase+'_seeds'];rank=cfg['ranks'][index//len(seeds)];seed=seeds[index%len(seeds)]
    result=engine.task(cfg,ident,rank,seed,cfg['budgets'])
    e.atomic_json(out/'task_receipts'/f'{phase}-{index:03d}.json',dict(result,phase=phase,
        rank=rank,seed=seed,identity=ident,slurm_job_id=os.environ['SLURM_JOB_ID']))


def audit(cfg,ident,phase,shard):
    out=Path(cfg['output']);seeds=cfg[phase+'_seeds']
    selected=seeds if phase=='pilot' else seeds[5*shard:5*(shard+1)]
    assert selected
    hashes={};checked=ols=full=0;worst=0.;began=time.monotonic()
    for rank in cfg['ranks']:
        s=engine.load_system(cfg,rank);assert max(abs(np.linalg.eigvals(s['A']-s['B']@s['K0'])))<1
        for seed in selected:
            stem=f'ce-r{rank:03d}-s{seed:04d}';path=out/'raw'/(stem+'.json');raw=e.read(path)
            assert raw['identity']==ident and raw['budgets']==cfg['budgets']
            hashes[str(path.relative_to(out))]=e.sha(path)
            for count in cfg['budgets']:
                pair=[r for r in raw['records'] if r['ols_samples']==count]
                assert [r['method'] for r in pair]==['dense','truncated']
                assert all(r['transitions']==count+cfg['burn'] for r in pair)
                p=out/pair[0]['policy_file'];assert e.sha(p)==pair[0]['policy_sha256']==pair[1]['policy_sha256']
                hashes[str(p.relative_to(out))]=e.sha(p)
                with np.load(p,allow_pickle=False) as data:
                    ks=[data['shared']]*2 if rank==cfg['n'] else [data['dense'],data['truncated']]
                    if rank==cfg['n']:
                        assert {k:v for k,v in pair[0].items() if k!='method'}=={k:v for k,v in pair[1].items() if k!='method'};full+=1
                    for j,(row,k) in enumerate(zip(pair,ks)):
                        if rank==cfg['n'] and j:continue
                        gap=performance_gap(s,k)[0] if np.isfinite(k).all() else math.inf
                        assert bool(np.isfinite(gap))==row['stable']
                        if row['stable']:
                            err=abs(gap-row['gap']);worst=max(worst,err);assert err<2e-7*max(1.,abs(gap))
                        checked+=1
            with np.load(out/'checkpoints'/(stem+'.npz'),allow_pickle=False) as data:
                theta=engine.cho_solve(engine.cho_factor((data['gram']+data['gram'].T)/2),data['cross'].T).T
            with np.load(out/'estimates'/(stem+'.npz'),allow_pickle=False) as data:
                np.testing.assert_allclose(theta,np.concatenate((data['Ahat'],data['Bhat']),axis=1),atol=1e-12,rtol=0)
            ols+=1
    dest=out/'audit-shards'/f'{phase}-{shard:02d}.json'
    e.atomic_json(dest,dict(status='PASS',identity=ident,seeds=selected,unique_policies=checked,
        OLS_fits=ols,full_rank_identity_checks=full,maximum_gap_error=worst,
        seconds=time.monotonic()-began,sources_sha256=hashes,slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS',phase=phase,shard=shard,policies=checked,seconds=time.monotonic()-began)),flush=True)


def report_base(cfg,ident,phase):
    out=Path(cfg['output']);dest=out/f'report-{phase}';dest.mkdir(exist_ok=True)
    if phase=='pilot':audit(cfg,ident,phase,0)
    audits=[e.read(out/'audit-shards'/f'{phase}-{i:02d}.json') for i in range(1 if phase=='pilot' else 6)]
    assert all(a['status']=='PASS' and a['identity']==ident for a in audits)
    seeds=cfg[phase+'_seeds'];count=len(seeds);allrows=[];rates=[];requirements=[];fixed=[]
    physical=0
    for rank in cfg['ranks']:
        data={seed:e.read(out/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json') for seed in seeds}
        for raw in data.values():allrows+=raw['records'];physical+=raw['physical_transitions']
        arrays={}
        for method in ('dense','truncated'):
            gaps=np.asarray([[next(r['gap'] if r['stable'] else math.inf for r in data[seed]['records'] if r['method']==method and r['ols_samples']==n) for n in cfg['budgets']] for seed in seeds])
            arrays[method]=gaps
            for target in cfg['absolute_targets']:
                successes=np.sum(gaps<=target,axis=0);hits=np.flatnonzero(successes/count>=.9)
                sustained=[j for j in hits if np.all(successes[j:]/count>=.9)]
                first=int(hits[0]) if len(hits) else None
                requirements.append(dict(rank=rank,method=method,absolute_target=target,seeds=count,
                    N_hat_90=cfg['budgets'][first]+cfg['burn'] if first is not None else None,
                    sustained_N90=cfg['budgets'][sustained[0]]+cfg['burn'] if sustained else None,
                    successes_at_first=int(successes[first]) if first is not None else None,
                    max_budget=max(cfg['budgets'])+cfg['burn'],endpoint_successes=int(successes[-1]),
                    endpoint_gap_median=float(np.median(gaps[:,-1])) if np.isfinite(np.median(gaps[:,-1])) else None))
                for j,n in enumerate(cfg['budgets']):
                    rates.append(dict(rank=rank,method=method,absolute_target=target,transitions=n+cfg['burn'],
                        successes=int(successes[j]),seeds=count,stable=int(np.isfinite(gaps[:,j]).sum())))
        for j,n in enumerate(cfg['budgets']):
            d,t=[float(np.median(arrays[m][:,j])) for m in ('dense','truncated')]
            paired=arrays['dense'][:,j]/arrays['truncated'][:,j]
            fixed.append(dict(rank=rank,transitions=n+cfg['burn'],seeds=count,
                dense_gap_median=d if math.isfinite(d) else None,truncated_gap_median=t if math.isfinite(t) else None,
                ratio_of_medians=d/t if math.isfinite(d/t) else None,
                paired_ratio_median=float(np.median(paired)) if np.isfinite(paired).all() else None))
    for name,rr in [('all_checkpoints',allrows),('sample_complexity',requirements),('success_by_budget',rates),('fixed_budget_gaps',fixed),('initial_systems',e.read(out/'verification.json')['systems'])]:write_csv(dest/(name+'.csv'),rr)
    summary=dict(status='complete',phase=phase,seeds=seeds,ranks=cfg['ranks'],K0='shared fixed-pole stabilizer; identical F0/P0 across ranks',
        target_definition='absolute J-Jstar; no matching of initial gaps',requirements=requirements,
        physical_transitions=physical,unique_policies_audited=sum(a['unique_policies'] for a in audits),
        OLS_fits_audited=sum(a['OLS_fits'] for a in audits),fixed_budget=fixed)
    e.atomic_json(dest/'summary.json',summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,len(cfg['ranks']),figsize=(17,3.7),sharey=True,layout='constrained')
    for ax,rank in zip(axes,cfg['ranks']):
        rr=[r for r in fixed if r['rank']==rank]
        for m,color in [('dense','#aa4538'),('truncated','#1974a3')]:
            ax.plot([r['transitions'] for r in rr],[r[m+'_gap_median'] or np.nan for r in rr],'-o',color=color,label=m)
        for target in cfg['absolute_targets']:ax.axhline(target,color='.5',ls=':')
        ax.set(xscale='log',yscale='log',xlabel='Primitive transitions',title=f'rank {rank}')
    axes[0].set_ylabel('Absolute gap J-Jstar');axes[-1].legend()
    fig.suptitle(f'Independent A/B | n=500 | shared K0/F0/P0, p0=47 | {count} seeds')
    for ext in ('png','svg'):fig.savefig(dest/('common_constant_gap_curves.'+ext),dpi=170)
    plt.close(fig)
    print(json.dumps(dict(status='complete',phase=phase,requirements=requirements)),flush=True)


def report(cfg,ident,phase):
    report_base(cfg,ident,phase)
    from ce500_common_constant_report import report_scaling
    report_scaling(cfg,ident,e,write_csv,phase)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','task','audit','report'])
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--phase',choices=['pilot','confirm'],default='pilot')
    p.add_argument('--task-id',type=int,default=0);p.add_argument('--shard',type=int,default=0)
    args=p.parse_args();assert os.environ.get('SLURM_JOB_ID'),'Use a real Grace compute allocation'
    cfg=e.read(args.manifest);ident=identity(cfg)
    for key,wanted in [('TMPDIR',cfg['temp']),('XDG_CACHE_HOME',cfg['cache']),('NUMBA_CACHE_DIR',cfg['cache']+'/numba'),('MPLCONFIGDIR',cfg['cache']+'/matplotlib')]:
        assert os.environ.get(key)==wanted;Path(wanted).mkdir(parents=True,exist_ok=True)
    with threadpool_limits(1):
        if args.mode=='prepare':prepare(cfg,ident)
        elif args.mode=='task':task(cfg,ident,args.phase,args.task_id)
        elif args.mode=='audit':audit(cfg,ident,args.phase,args.shard)
        else:report(cfg,ident,args.phase)


if __name__=='__main__':main()
