"""Audit and report paired CE sample complexity with a matched initial gap."""
import csv
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import rank_sweep100 as e


def csv_write(path, rows):
    if not rows:return
    fields=list(dict.fromkeys(k for q in rows for k in q))
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def wilson(count,n):
    z=1.959963984540054;p=count/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return max(0.,mid-half),min(1.,mid+half)


def finite(value):return float(value) if np.isfinite(value) else None


def interval(values):
    # Nearest empirical quantiles preserve right censoring without inf interpolation.
    if np.isnan(values).any():return dict(low=None,high=None,undefined=True)
    bounds=np.quantile(values,[.025,.975],method='nearest')
    return dict(low=finite(bounds[0]),high=finite(bounds[1]),
                low_censored=bool(np.isinf(bounds[0])),high_censored=bool(np.isinf(bounds[1])),undefined=False)


def first_threshold(success, budgets, level=.9):
    rates=success.mean(axis=-2)
    hit=rates>=level-1e-12
    indices=hit.argmax(axis=-1)
    return np.where(hit.any(axis=-1),np.asarray(budgets)[indices],np.inf)


def figures(cfg, destination, requirements, rates, fixed):
    colors=plt.get_cmap('tab10').colors;dense='#bd4936';truncated='#1476a3'
    plt.rcParams.update({'axes.grid':True,'grid.alpha':.2,'font.size':10})
    def save(fig,name):
        fig.savefig(destination/(name+'.png'),dpi=180,facecolor='white')
        fig.savefig(destination/(name+'.svg'),facecolor='white');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.4),layout='constrained')
    for ax,target in zip(axes,cfg['relative_targets']):
        for method,color,offset in [('dense',dense,-.9),('truncated',truncated,.9)]:
            rows=[q for q in requirements if q['method']==method and q['relative_target']==target]
            for q in rows:
                x=q['rank']+offset;y=q['N_hat_90']
                if y is None:
                    ax.plot(x,q['max_budget'],'^',mfc='none',mec=color)
                    ax.annotate('',xy=(x,q['max_budget']*1.4),xytext=(x,q['max_budget']),arrowprops=dict(arrowstyle='->',color=color))
                else:
                    ax.plot(x,y,'o',color=color)
                    low,high=q['bootstrap95_low'],q['bootstrap95_high']
                    if low is not None and high is not None:ax.vlines(x,low,high,color=color,lw=1.5)
            ax.plot([],[],'o',color=color,label=method.capitalize())
        full=next(q for q in requirements if q['rank']==100 and q['method']=='dense' and q['relative_target']==target)
        if full['N_hat_90'] is not None:ax.axhline(full['N_hat_90'],ls=':',color='.4',label='Full-rank dense')
        ax.set(yscale='log',xlabel='Actuation rank',ylabel='Transitions for >=90% empirical success',
               title=f'Relative target {target:g} | absolute target {target*cfg["initial_gap"]:g}',xticks=cfg['ranks'])
        ax.legend(fontsize=8)
    fig.suptitle(f'CE | matched initial gap 1 | {requirements[0]["seeds"]} seeds per rank\nPointwise paired-bootstrap 95% intervals; open arrows: not reached',fontsize=12)
    save(fig,'sample_complexity_vs_rank')
    fig,axes=plt.subplots(1,5,figsize=(17,3.8),sharey=True,layout='constrained')
    for ax,rank in zip(axes,cfg['ranks']):
        for method,color,style in [('dense',dense,'--'),('truncated',truncated,'-')]:
            rows=[q for q in rates if q['rank']==rank and q['method']==method and q['relative_target']==cfg['relative_targets'][0]]
            x=[q['transitions'] for q in rows]
            ax.plot(x,[q['success_rate'] for q in rows],style,color=color,label=method.capitalize())
            ax.fill_between(x,[q['ci95_low'] for q in rows],[q['ci95_high'] for q in rows],color=color,alpha=.12)
        ax.axhline(.9,ls=':',color='.4');ax.set(xscale='log',ylim=(-.03,1.03),xlabel='Transitions',title=f'rank {rank}')
    axes[0].set_ylabel('Success probability');axes[-1].legend(fontsize=8)
    fig.suptitle('Matched-gap CE | relative target 0.1 | Wilson 95% intervals',fontsize=12)
    save(fig,'success_probability_vs_budget')
    fig,axes=plt.subplots(1,5,figsize=(17,3.8),sharey=True,layout='constrained')
    for ax,rank in zip(axes,cfg['ranks']):
        rows=[q for q in fixed if q['rank']==rank];x=[q['transitions'] for q in rows]
        for method,color,style in [('dense',dense,'--'),('truncated',truncated,'-')]:
            ax.plot(x,[q[method+'_gap_median']/cfg['initial_gap'] for q in rows],style,color=color,label=method.capitalize())
            ax.fill_between(x,[q[method+'_gap_q25']/cfg['initial_gap'] for q in rows],[q[method+'_gap_q75']/cfg['initial_gap'] for q in rows],color=color,alpha=.13)
        ax.axhline(.1,color='.4',ls=':');ax.set(xscale='log',yscale='log',xlabel='Transitions',title=f'rank {rank}')
    axes[0].set_ylabel('Relative optimality gap');axes[-1].legend(fontsize=8)
    fig.suptitle('CE gap convergence | identical initial gap 1 | medians and IQR\nAbsolute gap has identical numerical values because the common denominator is 1',fontsize=12)
    save(fig,'relative_and_absolute_gap_convergence')
    fig,axes=plt.subplots(1,2,figsize=(12,4.2),layout='constrained')
    for i,rank in enumerate(cfg['ranks']):
        rows=[q for q in fixed if q['rank']==rank];x=[q['transitions'] for q in rows]
        axes[0].plot(x,[q['full_dense_over_low_trunc_gap_ratio'] for q in rows],'-o',markersize=3,color=colors[i],label=f'rank {rank} + truncation')
        axes[0].fill_between(x,[q['cross_rank_gap_ci95_low'] for q in rows],[q['cross_rank_gap_ci95_high'] for q in rows],color=colors[i],alpha=.12)
    for ax in axes:ax.axhline(1,color='.4',ls=':')
    axes[0].set(xscale='log',yscale='log',xlabel='Common transition budget',ylabel='Full-rank dense gap / low-rank truncated gap',title='Same-budget comparison (>1 favors low rank)')
    axes[0].legend(fontsize=8)
    rows=[q for q in fixed if q['transitions']==max(z['transitions'] for z in fixed)]
    axes[1].plot([q['rank'] for q in rows],[q['full_dense_over_low_trunc_gap_ratio'] for q in rows],'-o',color=truncated)
    axes[1].set(yscale='log',xlabel='Actuation rank of truncated CE',ylabel='Full-rank dense gap / truncated gap',title=f'Common endpoint budget {rows[0]["transitions"]:,}',xticks=cfg['ranks'])
    fig.suptitle('Matched initial gap | direct low-rank + truncation versus full-rank + dense',fontsize=12)
    save(fig,'low_rank_truncated_vs_full_rank_dense')


def report(cfg, ident, phase):
    from ce_matched_initial_gap import load_matched, performance_gap
    out=Path(cfg['output']);dest=out/f'report-{phase}';dest.mkdir(parents=True,exist_ok=True)
    seeds=cfg[phase+'_seeds'];budget_data=cfg[phase+'_budgets'];budgets=[n+cfg['burn'] for n in budget_data]
    data={};sources={};max_error=0.;checked=0;full_pairs=0;physical=0;allrows=[]
    verification=e.read(out/'verification.json');assert verification['identity']==ident
    for rank in cfg['ranks']:
        s,_=load_matched(cfg,rank)
        for seed in seeds:
            path=out/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json';raw=e.read(path)
            assert raw['identity']==ident and raw['physical_transitions']==max(budgets)
            sources[str(path)]=e.sha(path);physical+=raw['physical_transitions']
            policies=out/'policies'/path.with_suffix('.npz').name
            assert e.sha(policies)==raw['policy_sha256']
            with np.load(policies,allow_pickle=False) as arrays:ks=arrays['policies'].copy()
            assert len(ks)==len(raw['records'])==2*len(budgets)
            for row,k in zip(raw['records'],ks):
                q,_=e.evaluate(s,k) if np.isfinite(k).all() else (dict(stable=False,gap=None),None)
                assert q['stable']==row['stable']
                if q['stable']:
                    err=abs(q['gap']-row['gap']);max_error=max(max_error,err);assert err<1e-9
                    alternative,_,_=performance_gap(s,k)
                    assert abs(alternative-row['gap'])<1e-9
                else:assert row['gap'] is None
                checked+=1;allrows.append(row)
            if rank==cfg['n']:
                for j in range(0,len(ks),2):np.testing.assert_array_equal(ks[j],ks[j+1]);full_pairs+=1
            for method in ('dense','truncated'):
                data[rank,method,seed]=[next(q for q in raw['records'] if q['method']==method and q['transitions']==budget) for budget in budgets]
    count=len(seeds);indices=np.random.default_rng(cfg['bootstrap_seed']).integers(0,count,size=(cfg['bootstrap_replicates'],count))
    rates=[];requirements=[];boot_requirements={};gap_arrays={}
    for rank in cfg['ranks']:
        for method in ('dense','truncated'):
            rr=[data[rank,method,seed] for seed in seeds]
            gap=np.array([[q['gap'] if q['stable'] and q['gap'] is not None else np.inf for q in curve] for curve in rr])
            # Retain failures as infinity; no conditional removal from success rates.
            gap_arrays[rank,method]=gap
            for relative in cfg['relative_targets']:
                eps=relative*cfg['initial_gap'];success=gap<=eps
                point=float(first_threshold(success,budgets));bootstrap=first_threshold(success[indices],budgets)
                boot_requirements[rank,method,relative]=bootstrap
                ci=interval(bootstrap);stabilities=np.array([[q['stable'] for q in curve] for curve in rr])
                instabilities=np.array([[q.get('failure')=='controller_instability' for q in curve] for curve in rr])
                numerical=np.array([[q.get('failure')=='riccati_failure' for q in curve] for curve in rr])
                for j,budget in enumerate(budgets):
                    successes=int(success[:,j].sum());low,high=wilson(successes,count)
                    rates.append(dict(rank=rank,method=method,relative_target=relative,absolute_target=eps,
                        transitions=budget,seeds=count,successes=successes,success_rate=successes/count,
                        ci95_low=low,ci95_high=high,instabilities=int(instabilities[:,j].sum()),numerical_failures=int(numerical[:,j].sum())))
                requirements.append(dict(rank=rank,method=method,relative_target=relative,absolute_target=eps,
                    initial_gap=cfg['initial_gap'],seeds=count,N_hat_90=finite(point),status='reached' if np.isfinite(point) else 'not reached',
                    bootstrap95_low=ci['low'],bootstrap95_high=ci['high'],bootstrap95_low_censored=ci.get('low_censored',False),bootstrap95_high_censored=ci.get('high_censored',False),
                    max_budget=max(budgets),max_successes=int(success[:,-1].sum()),max_instabilities=int(instabilities[:,-1].sum()),max_numerical_failures=int(numerical[:,-1].sum()),
                    endpoint_gap_median=finite(np.median(gap[:,-1])),bootstrap_unreached_fraction=float(np.isinf(bootstrap).mean())))
    cross=[];fixed=[]
    full=gap_arrays[cfg['n'],'dense']
    for rank in cfg['ranks']:
        d,t=gap_arrays[rank,'dense'],gap_arrays[rank,'truncated']
        for j,budget in enumerate(budgets):
            md,mt=np.median(d[:,j]),np.median(t[:,j]);reference=np.median(full[:,j])
            with np.errstate(invalid='ignore',divide='ignore'):
                br=np.median(full[indices,j],axis=1)/np.median(t[indices,j],axis=1)
            ci=interval(br)
            fixed.append(dict(rank=rank,transitions=budget,dense_gap_median=finite(md),truncated_gap_median=finite(mt),
                dense_gap_q25=finite(np.quantile(d[:,j],.25)),dense_gap_q75=finite(np.quantile(d[:,j],.75)),
                truncated_gap_q25=finite(np.quantile(t[:,j],.25)),truncated_gap_q75=finite(np.quantile(t[:,j],.75)),
                within_rank_dense_over_trunc_gap_ratio=finite(md/mt),full_dense_over_low_trunc_gap_ratio=finite(reference/mt),
                cross_rank_gap_ci95_low=ci['low'],cross_rank_gap_ci95_high=ci['high']))
        for relative in cfg['relative_targets']:
            a=next(q for q in requirements if q['rank']==cfg['n'] and q['method']=='dense' and q['relative_target']==relative)
            b=next(q for q in requirements if q['rank']==rank and q['method']=='truncated' and q['relative_target']==relative)
            numerator=boot_requirements[cfg['n'],'dense',relative];denominator=boot_requirements[rank,'truncated',relative]
            with np.errstate(invalid='ignore',divide='ignore'):ratios=numerator/denominator
            ci=interval(ratios)
            ratio=a['N_hat_90']/b['N_hat_90'] if a['N_hat_90'] is not None and b['N_hat_90'] is not None else None
            cross.append(dict(rank=rank,relative_target=relative,full_rank_dense_N_hat=a['N_hat_90'],low_rank_truncated_N_hat=b['N_hat_90'],
                sample_saving_factor_full_over_low=ratio,bootstrap95_low=ci['low'],bootstrap95_high=ci['high'],
                undefined_bootstrap_fraction=float(np.isnan(ratios).mean()),
                interpretation='Factor >1 favors low rank plus truncation; no forced finite value for censored outcomes'))
    csv_write(dest/'sample_complexity.csv',requirements);csv_write(dest/'success_by_budget.csv',rates)
    csv_write(dest/'fixed_budget_gaps.csv',fixed);csv_write(dest/'low_rank_vs_full_rank.csv',cross)
    csv_write(dest/'all_checkpoints.csv',allrows);csv_write(dest/'initial_systems.csv',verification['systems'])
    figures(cfg,dest,requirements,rates,fixed)
    audit=dict(status='PASS',phase=phase,paired_tasks=len(seeds)*len(cfg['ranks']),policies_checked=checked,
        full_rank_paired_budget_checks=full_pairs,maximum_gap_recompute_error=max_error,
        physical_transitions=physical,algorithm_charged_transitions=2*physical,sources_sha256=sources)
    e.atomic_json(dest/'audit.json',audit)
    summary=dict(status='complete',phase=phase,seeds=seeds,initial_gap=cfg['initial_gap'],relative_targets=cfg['relative_targets'],
        requirements=requirements,low_rank_vs_full_rank=cross,audit=audit,
        limitations=['One common physical system instance. Matching initial gap changes behavior policies.',
                    'Exploration state distributions and control capabilities still vary with rank.',
                    'Oracle gains are used only for private initial-policy construction; unchanged CE learner uses OLS data.',
                    'Bootstrap confidence is conditional on this system; Nhat is a discrete-grid empirical threshold.'])
    e.atomic_json(dest/'summary.json',summary)
    print(json.dumps(dict(status='complete',phase=phase,contrast=cross,checked_policies=checked)),flush=True)
