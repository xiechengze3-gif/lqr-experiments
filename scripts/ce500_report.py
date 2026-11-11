"""Saved-artifact audit and statistical report for CE500; no new learning."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from threadpoolctl import threadpool_limits
import rank_sweep100 as e
import ce500_matched_gap as run
from ce_matched_initial_gap import performance_gap


def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        w.writeheader();w.writerows(rows)


def wilson(k,n):
    z=1.959963984540054;p=k/n;d=1+z*z/n
    mid=(p+z*z/(2*n))/d;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return max(0.,mid-half),min(1.,mid+half)


def finite(v):return float(v) if np.isfinite(v) else None


def threshold(success,budgets):
    hits=success.mean(axis=-2)>=.9-1e-12
    return np.where(hits.any(axis=-1),np.asarray(budgets)[hits.argmax(axis=-1)],np.inf)


def boot_interval(values):
    q=np.quantile(values,[.025,.975],method='nearest')
    return dict(low=finite(q[0]),high=finite(q[1]),low_censored=bool(np.isinf(q[0])),high_censored=bool(np.isinf(q[1])))


def report(cfg,phase,plan,full_audit):
    ident=run.identity(cfg);out=Path(cfg['output']);dest=out/f'report-{phase}'
    dest.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    budgets=[v+cfg['burn'] for v in (plan['budgets'] if plan else cfg['pilot_budgets'])]
    seeds=cfg[phase+'_seeds'];count=len(seeds);data={};allrows=[];hashes={};physical=0
    checked=0;full_pairs=0;max_gap_error=0.;maximum_ols_residual=0.;ols_fits=0
    for rank in cfg['ranks']:
        s=run.load_system(cfg,rank)
        for seed in seeds:
            stem=f'ce-r{rank:03d}-s{seed:04d}';path=out/'raw'/(stem+'.json');raw=e.read(path)
            assert raw['identity']==ident and raw['physical_transitions']==max(budgets)
            assert len(raw['records'])==2*len(budgets)
            hashes[str(path.relative_to(out))]=e.sha(path);physical+=raw['physical_transitions']
            for budget in budgets:
                pair=[q for q in raw['records'] if q['transitions']==budget]
                assert [q['method'] for q in pair]==['dense','truncated']
                pp=out/pair[0]['policy_file'];assert e.sha(pp)==pair[0]['policy_sha256']==pair[1]['policy_sha256']
                hashes[str(pp.relative_to(out))]=pair[0]['policy_sha256']
                with np.load(pp,allow_pickle=False) as a:
                    ks=[a['shared'].copy()]*2 if rank==cfg['n'] else [a[k].copy() for k in ('dense','truncated')]
                if rank==cfg['n']:
                    np.testing.assert_array_equal(*ks)
                    assert {k:v for k,v in pair[0].items() if k!='method'}=={k:v for k,v in pair[1].items() if k!='method'}
                    full_pairs+=1
                # Full formal audit reevaluates every unique policy independently.
                if full_audit or seed==seeds[0] or budget==budgets[-1]:
                    for j,(row,k) in enumerate(zip(pair,ks)):
                        if rank==cfg['n'] and j:continue
                        if np.isfinite(k).all():
                            gap,rho,_=performance_gap(s,k);stable=np.isfinite(gap)
                        else:gap=np.inf;stable=False
                        assert stable==row['stable']
                        if stable:
                            error=abs(gap-row['gap']);max_gap_error=max(max_gap_error,error)
                            assert error<1e-8,(rank,seed,budget,error)
                        checked+=1
                for row in pair:maximum_ols_residual=max(maximum_ols_residual,row['ols_residual'])
                allrows+=pair
            # Recompute each final joint OLS from its original sufficient statistics.
            with np.load(out/'checkpoints'/(stem+'.npz'),allow_pickle=False) as a:
                gram=a['gram'];cross=a['cross']
                theta=run.cho_solve(run.cho_factor((gram+gram.T)/2),cross.T).T
            with np.load(out/'estimates'/(stem+'.npz'),allow_pickle=False) as a:
                np.testing.assert_array_equal(theta,np.concatenate((a['Ahat'],a['Bhat']),axis=1))
            assert np.linalg.norm(theta@gram-cross)/np.linalg.norm(cross)<1e-10;ols_fits+=1
            for method in ('dense','truncated'):
                data[rank,method,seed]=[next(q for q in raw['records'] if q['transitions']==b and q['method']==method) for b in budgets]
            print(json.dumps(dict(audited_rank=rank,seed=seed,seconds=time.monotonic()-start)),flush=True)
    indices=np.random.default_rng(cfg['bootstrap_seed']).integers(0,count,size=(cfg['bootstrap_replicates'],count))
    rates=[];requirements=[];gap_arrays={};bootN={}
    for rank in cfg['ranks']:
        for method in ('dense','truncated'):
            records=[data[rank,method,s] for s in seeds]
            gap=np.array([[q['gap'] if q['stable'] else np.inf for q in rr] for rr in records])
            gap_arrays[rank,method]=gap
            for target in cfg['relative_targets']:
                success=gap<=target*cfg['initial_gap'];n90=float(threshold(success,budgets))
                boot=threshold(success[indices],budgets);bootN[rank,method,target]=boot
                ci=boot_interval(boot);hit=None if not np.isfinite(n90) else budgets.index(n90)
                for j,budget in enumerate(budgets):
                    wins=int(success[:,j].sum());low,high=wilson(wins,count)
                    unstable=sum(rr[j].get('failure')=='controller_instability' for rr in records)
                    numerical=sum(rr[j].get('failure')=='riccati_failure' for rr in records)
                    il,ih=wilson(unstable,count);fl,fh=wilson(numerical,count)
                    rates.append(dict(rank=rank,method=method,relative_target=target,absolute_target=target*cfg['initial_gap'],
                        transitions=budget,seeds=count,successes=wins,success_rate=wins/count,ci95_low=low,ci95_high=high,
                        instabilities=unstable,instability_ci95_low=il,instability_ci95_high=ih,
                        numerical_failures=numerical,numerical_failure_ci95_low=fl,numerical_failure_ci95_high=fh))
                selected=rates[-len(budgets)+hit] if hit is not None else rates[-1]
                requirements.append(dict(rank=rank,method=method,initial_gap=cfg['initial_gap'],relative_target=target,
                    seeds=count,N_hat_90=finite(n90),status='reached' if hit is not None else 'not reached',
                    previous_tested_budget=budgets[hit-1] if hit is not None and hit>0 else None,
                    bootstrap95_low=ci['low'],bootstrap95_high=ci['high'],bootstrap95_low_censored=ci['low_censored'],
                    bootstrap95_high_censored=ci['high_censored'],bootstrap_unreached_fraction=float(np.isinf(boot).mean()),
                    threshold_or_endpoint_successes=selected['successes'],success_ci95_low=selected['ci95_low'],success_ci95_high=selected['ci95_high'],
                    threshold_or_endpoint_instabilities=selected['instabilities'],instability_ci95_low=selected['instability_ci95_low'],instability_ci95_high=selected['instability_ci95_high'],
                    max_budget=max(budgets),endpoint_successes=int(success[:,-1].sum()),endpoint_gap_median=finite(np.median(gap[:,-1]))))
    fixed=[];contrasts=[];full=gap_arrays[cfg['n'],'dense']
    for rank in cfg['ranks']:
        d,t=gap_arrays[rank,'dense'],gap_arrays[rank,'truncated']
        for j,budget in enumerate(budgets):
            md,mt,mf=np.median(d[:,j]),np.median(t[:,j]),np.median(full[:,j])
            row=dict(rank=rank,transitions=budget,dense_gap_median=finite(md),truncated_gap_median=finite(mt),
                dense_gap_q25=finite(np.quantile(d[:,j],.25)),dense_gap_q75=finite(np.quantile(d[:,j],.75)),
                truncated_gap_q25=finite(np.quantile(t[:,j],.25)),truncated_gap_q75=finite(np.quantile(t[:,j],.75)),
                dense_over_trunc=finite(md/mt) if np.isfinite(md) and np.isfinite(mt) and mt>0 else None,
                full_dense_over_low_trunc=finite(mf/mt) if np.isfinite(mf) and np.isfinite(mt) and mt>0 else None)
            fixed.append(row)
        for target in cfg['relative_targets']:
            a=next(q for q in requirements if q['rank']==cfg['n'] and q['method']=='dense' and q['relative_target']==target)
            b=next(q for q in requirements if q['rank']==rank and q['method']=='truncated' and q['relative_target']==target)
            aa,bb=bootN[cfg['n'],'dense',target],bootN[rank,'truncated',target]
            uncensored=np.isfinite(aa).all() and np.isfinite(bb).all()
            ratio=a['N_hat_90']/b['N_hat_90'] if a['N_hat_90'] is not None and b['N_hat_90'] is not None else None
            ci=boot_interval(aa/bb) if uncensored else dict(low=None,high=None)
            contrasts.append(dict(rank=rank,relative_target=target,full_rank_dense_N=a['N_hat_90'],low_rank_truncated_N=b['N_hat_90'],
                sample_saving_factor_full_over_low=ratio,bootstrap95_low=ci['low'],bootstrap95_high=ci['high'],
                ratio_interval_censored=not uncensored))
    for name,rows in [('sample_complexity',requirements),('success_by_budget',rates),('fixed_budget_gaps',fixed),
                      ('low_rank_vs_full_rank',contrasts),('all_checkpoints',allrows),('initial_systems',e.read(out/'verification.json')['systems'])]:
        write_csv(dest/(name+'.csv'),rows)
    audit=dict(status='PASS',phase=phase,paired_tasks=count*len(cfg['ranks']),unique_policies_reevaluated=checked,
        full_rank_paired_budget_checks=full_pairs,final_joint_OLS_recomputed=ols_fits,
        maximum_performance_identity_gap_error=max_gap_error,maximum_OLS_normal_residual=maximum_ols_residual,
        physical_transitions=physical,algorithm_charged_transitions=2*physical,
        all_policy_hashes_checked=True,sources_sha256=hashes)
    e.atomic_json(dest/'audit.json',audit)
    e.atomic_json(dest/'summary.json',dict(status='complete',phase=phase,dimension=cfg['n'],seeds=seeds,budgets=budgets,
        initial_gap=cfg['initial_gap'],relative_targets=cfg['relative_targets'],requirements=requirements,
        low_rank_vs_full_rank=contrasts,audit=audit))
    plots(cfg,dest,requirements,rates,fixed)
    print(json.dumps(dict(status='complete',contrasts=contrasts,audit={k:v for k,v in audit.items() if k!='sources_sha256'})),flush=True)


def plots(cfg,dest,requirements,rates,fixed):
    colors={'dense':'#ba4737','truncated':'#1476a3'};ranks=cfg['ranks']
    plt.rcParams.update({'axes.grid':True,'grid.alpha':.2,'font.size':10})
    def save(fig,name):
        for ext in ('png','svg'):fig.savefig(dest/(name+'.'+ext),dpi=180,facecolor='white')
        plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.2),layout='constrained')
    for ax,target in zip(axes,cfg['relative_targets']):
        for method,color in colors.items():
            rows=[q for q in requirements if q['relative_target']==target and q['method']==method]
            ax.plot(ranks,[q['N_hat_90'] or np.nan for q in rows],'-o' if method=='truncated' else '--s',color=color,label=method)
            for q in rows:
                if q['N_hat_90'] is None:ax.plot(q['rank'],q['max_budget'],'^',mec=color,mfc='none')
                elif q['bootstrap95_low'] and q['bootstrap95_high']:ax.vlines(q['rank'],q['bootstrap95_low'],q['bootstrap95_high'],color=color,alpha=.6)
        ax.set(xscale='log',yscale='log',xlabel='Actuation rank',ylabel='Transitions for >=90% empirical success',
               title=f'Relative = absolute gap target {target:g}',xticks=ranks)
        ax.set_xticklabels(ranks);ax.legend()
    fig.suptitle(f'CE | n=m={cfg["n"]} | initial gap=1 | {requirements[0]["seeds"]} seeds')
    save(fig,'sample_complexity_vs_rank')
    fig,axes=plt.subplots(2,len(ranks),figsize=(17,6),sharey=True,layout='constrained')
    for i,target in enumerate(cfg['relative_targets']):
        for ax,rank in zip(axes[i],ranks):
            for method,color in colors.items():
                rows=[q for q in rates if q['rank']==rank and q['method']==method and q['relative_target']==target]
                x=[q['transitions'] for q in rows]
                ax.plot(x,[q['success_rate'] for q in rows],'-' if method=='truncated' else '--',color=color,label=method)
                ax.fill_between(x,[q['ci95_low'] for q in rows],[q['ci95_high'] for q in rows],color=color,alpha=.12)
            ax.axhline(.9,color='.4',ls=':');ax.set(xscale='log',ylim=(-.03,1.03),title=f'rank {rank} | target {target:g}',xlabel='Transitions')
        axes[i,0].set_ylabel('Success probability')
    axes[0,-1].legend();fig.suptitle('Success probability | Wilson 95% confidence intervals')
    save(fig,'success_probability_vs_budget')
    fig,axes=plt.subplots(1,len(ranks),figsize=(17,3.8),sharey=True,layout='constrained')
    for ax,rank in zip(axes,ranks):
        rows=[q for q in fixed if q['rank']==rank];x=[q['transitions'] for q in rows]
        for method,color in colors.items():
            ax.plot(x,[q[method+'_gap_median'] for q in rows],'-' if method=='truncated' else '--',color=color,label=method)
            ax.fill_between(x,[q[method+'_gap_q25'] if q[method+'_gap_q25'] is not None else np.nan for q in rows],
                              [q[method+'_gap_q75'] if q[method+'_gap_q75'] is not None else np.nan for q in rows],color=color,alpha=.12)
        for target in cfg['relative_targets']:ax.axhline(target,color='.5',ls=':')
        ax.set(xscale='log',yscale='log',xlabel='Transitions',title=f'rank {rank}')
    axes[0].set_ylabel('Absolute / relative optimality gap');axes[-1].legend()
    fig.suptitle('Absolute = relative gap (initial gap=1) | medians and IQR; failures retained')
    save(fig,'absolute_relative_gap_convergence')
    fig,ax=plt.subplots(figsize=(8,4.2),layout='constrained')
    for rank in ranks:
        rows=[q for q in fixed if q['rank']==rank]
        ax.plot([q['transitions'] for q in rows],[q['full_dense_over_low_trunc'] for q in rows],'-o',ms=3,label=f'rank {rank} + truncation')
    ax.axhline(1,color='.4',ls=':');ax.set(xscale='log',yscale='log',xlabel='Same transition budget',
        ylabel='Full-rank dense median gap / truncated median gap',title='Same-budget gap improvement (>1 favors low rank + truncation)')
    ax.legend();save(fig,'same_budget_gap_improvement')


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--phase',choices=['pilot','confirm'],required=True);p.add_argument('--plan',type=Path)
    p.add_argument('--full-audit',action='store_true');args=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    cfg=e.read(args.manifest)
    with threadpool_limits(1):report(cfg,args.phase,e.read(args.plan) if args.plan else None,args.full_audit)


if __name__=='__main__':main()
