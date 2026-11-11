"""PI-only and joined NPG/CE/PI reports; never recompute historical learning."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import rank_sweep100 as e
from rank_sweep100_report import csv_write, wilson, threshold, success, savefig


def summarize(cfg,out,phase):
    seeds=cfg[phase+'_seeds'];wanted=set(seeds);rows=[];raw=[];sources=[]
    ident=e.read(out/'resolved_config.json')['identity']
    for path in sorted((out/'raw').glob('*.json')):
        data=e.read(path)
        if data['seed'] not in wanted:continue
        assert data['identity']==ident
        raw.append(data);rows+=data['records'];sources.append(dict(path=str(path),sha256=e.sha(path)))
    planned={(rank,seed) for rank in cfg['ranks'] for seed in seeds}
    assert {(d['rank'],d['seed']) for d in raw}==planned and len(raw)==len(planned)
    rates=[];requirements=[];pairs=[];epsilon=cfg['epsilon']
    for rank in cfg['ranks']:
        for method in ('dense','truncated'):
            group=[r for r in rows if r['rank']==rank and r['method']==method]
            grid=sorted({r['transitions'] for r in group});n=len(seeds)
            for eps in (epsilon,epsilon/2):
                curve=[]
                for budget in grid:
                    current=[r for r in group if r['transitions']==budget];assert len(current)==n
                    hits=sum(success(r,eps) for r in current)
                    def ever(seed,kind):return any(r['seed']==seed and r['failure']==kind for r in group if r['transitions']<=budget)
                    unstable=sum(ever(seed,'controller_instability') for seed in seeds)
                    numeric=sum(ever(seed,'numerical_failure') for seed in seeds)
                    gaps=[r['gap'] for r in current if r['stable'] and r['observed'] and r['gap'] is not None]
                    ci=wilson(hits,n);ii=wilson(unstable,n)
                    row=dict(route='pi',rank=rank,method=method,epsilon=eps,transitions=budget,seeds=n,
                        successes=hits,success_rate=hits/n,success_ci95_low=ci[0],success_ci95_high=ci[1],
                        failures=n-hits,failure_rate=1-hits/n,failure_ci95_low=1-ci[1],failure_ci95_high=1-ci[0],
                        instabilities=unstable,instability_rate=unstable/n,instability_ci95_low=ii[0],instability_ci95_high=ii[1],
                        numerical_failures=numeric,stable_observed=len(gaps),gap_median=float(np.median(gaps)) if gaps else None,
                        gap_q25=float(np.quantile(gaps,.25)) if gaps else None,gap_q75=float(np.quantile(gaps,.75)) if gaps else None)
                    rates.append(row);curve.append(row)
                first,sustained,previous=threshold(curve,.9)
                hits=np.asarray([[success(next(r for r in group if r['seed']==seed and r['transitions']==budget),eps)
                                 for budget in grid] for seed in seeds],dtype=float)
                weights=np.random.default_rng(81132).multinomial(n,np.full(n,1/n),size=2000)
                good=weights@hits/n>=.9-1e-12
                boot=np.array([grid[np.flatnonzero(v)[0]] if v.any() else np.inf for v in good]);order=np.sort(boot)
                lo,hi=float(order[50]),float(order[1950]);endpoint=curve[-1]
                requirements.append(dict(route='pi',rank=rank,method=method,epsilon=eps,seeds=n,
                    N_hat_epsilon_90=first,status='reached' if first is not None else 'not reached',
                    sustained_N_hat=sustained,previous_tested_budget=previous,max_budget=grid[-1],
                    bootstrap95_low=None if np.isinf(lo) else int(lo),bootstrap95_high=None if np.isinf(hi) else int(hi),
                    bootstrap95_low_censored=bool(np.isinf(lo)),bootstrap95_high_censored=bool(np.isinf(hi)),
                    bootstrap_censoring_fraction=float(np.mean(np.isinf(boot))),
                    success_at_N_hat=next((r['success_rate'] for r in curve if r['transitions']==first),None),
                    success_ci95_at_N_hat=next(([r['success_ci95_low'],r['success_ci95_high']] for r in curve if r['transitions']==first),None),
                    max_budget_successes=endpoint['successes'],max_budget_success_rate=endpoint['success_rate'],
                    max_budget_success_ci95=[endpoint['success_ci95_low'],endpoint['success_ci95_high']],
                    max_budget_failure_rate=endpoint['failure_rate'],max_budget_failure_ci95=[endpoint['failure_ci95_low'],endpoint['failure_ci95_high']],
                    max_budget_instabilities=endpoint['instabilities'],max_budget_instability_rate=endpoint['instability_rate'],
                    max_budget_instability_ci95=[endpoint['instability_ci95_low'],endpoint['instability_ci95_high']],
                    max_budget_numerical_failures=endpoint['numerical_failures'],max_budget_gap_median=endpoint['gap_median']))
        budget=max(r['transitions'] for r in rows if r['rank']==rank);differences=[];success_delta=0
        for seed in seeds:
            d=next(r for r in rows if r['rank']==rank and r['seed']==seed and r['method']=='dense' and r['transitions']==budget)
            t=next(r for r in rows if r['rank']==rank and r['seed']==seed and r['method']=='truncated' and r['transitions']==budget)
            success_delta+=int(success(t,epsilon))-int(success(d,epsilon))
            if d['stable'] and t['stable'] and d['observed'] and t['observed']:differences.append(t['gap']-d['gap'])
        interval=[None,None]
        if differences:
            v=np.asarray(differences);rng=np.random.default_rng(60017)
            interval=np.quantile(v[rng.integers(len(v),size=(2000,len(v)))].mean(axis=1),[.025,.975]).tolist()
        pairs.append(dict(rank=rank,paired_seeds=len(seeds),jointly_stable_pairs=len(differences),
            truncated_minus_dense_success_fraction=success_delta/len(seeds),
            conditional_gap_difference_mean=float(np.mean(differences)) if differences else None,
            conditional_gap_difference_ci95=interval))
    return dict(status='complete',phase=phase,epsilon=epsilon,sensitivity_epsilon=epsilon/2,
        confidence_scope='Conditional on the fixed shared system instance; data-seed variation only',
        threshold_definition='First measured cumulative budget with >=90% point success and a stable whole PI path',
        sampling_budget_and_update_count_vary_together=True,
        formal_statistics_exclude_pilot_seeds=phase=='confirm',
        completed_tasks=len(raw),expected_tasks=len(planned),identity=ident,requirements=requirements,
        paired_comparisons=pairs,physical_transitions=sum(d['physical_transitions'] for d in raw),
        algorithm_charged_transitions=sum(sum(d['algorithm_actual_transitions'].values()) for d in raw)),rates,rows,sources


def report(cfg,out,baseline,phase):
    summary,rates,rows,sources=summarize(cfg,out,phase)
    dest=out/('report-'+phase);dest.mkdir(exist_ok=True)
    e.atomic_json(dest/'summary.json',summary)
    csv_write(dest/'sample_complexity.csv',summary['requirements']);csv_write(dest/'success_by_budget.csv',rates)
    csv_write(dest/'all_checkpoints.csv',rows);csv_write(dest/'paired_comparisons.csv',summary['paired_comparisons'])
    csv_write(dest/'sources.csv',sources)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
        'axes.grid':True,'grid.alpha':.2,'figure.dpi':120,'savefig.dpi':180})
    colors={'dense':'#b94835','truncated':'#176da0'};styles={'dense':'-','truncated':'--'};eps=cfg['epsilon']
    fig,axes=plt.subplots(1,5,figsize=(17,3.7),sharey=True,constrained_layout=True)
    for ax,rank in zip(axes,cfg['ranks']):
        for method in ('dense','truncated'):
            group=[r for r in rates if r['rank']==rank and r['method']==method and r['epsilon']==eps and r['transitions']>0]
            xx=[r['transitions'] for r in group]
            ax.plot(xx,[r['success_rate'] for r in group],color=colors[method],ls=styles[method],marker='o',label=method)
            ax.fill_between(xx,[r['success_ci95_low'] for r in group],[r['success_ci95_high'] for r in group],color=colors[method],alpha=.12)
        ax.axhline(.9,color='#444',ls='--',lw=.8);ax.set(title=f'r={rank}',xscale='log',xlabel='Transitions',ylim=(-.03,1.03))
    axes[0].set_ylabel('Success probability (Wilson 95% CI)');axes[0].legend()
    fig.suptitle(f'Full LSTD PI | common absolute target {eps:.6f} | {phase}')
    savefig(fig,dest/'pi_success_probability')
    baseline_summary=e.read(baseline/('report-'+phase)/'summary.json')
    baseline_hashes=e.read(baseline/'derived_reports_sha256.json')
    baseline_key='report-'+phase+'/summary.json'
    assert e.sha(baseline/baseline_key)==baseline_hashes[baseline_key] and baseline_summary['epsilon']==eps
    for rank in cfg['ranks']:
        assert e.sha(baseline/'frozen/system_inputs'/f'r{rank:03d}.npz')==cfg['system_artifact_sha256'][str(rank)]
    requirements=baseline_summary['requirements']+summary['requirements']
    csv_write(dest/'all_algorithms_sample_complexity.csv',requirements)
    fig,axes=plt.subplots(1,3,figsize=(15,4.8),constrained_layout=True)
    for ax,route,title in zip(axes,('npg','ce','pi'),('Stein NPG','Certainty equivalence','Full LSTD PI')):
        for method,offset in [('dense',-.12),('truncated',.12)]:
            group=[r for r in requirements if r['route']==route and r['method']==method and r['epsilon']==eps]
            group.sort(key=lambda r:r['rank']);xx=np.arange(len(group))+offset
            yy=[r['N_hat_epsilon_90'] if r['N_hat_epsilon_90'] is not None else r['max_budget'] for r in group]
            ax.plot(xx,[y if r['N_hat_epsilon_90'] is not None else np.nan for y,r in zip(yy,group)],color=colors[method],alpha=.45,lw=1)
            for x,y,r in zip(xx,yy,group):
                hit=r['N_hat_epsilon_90'] is not None
                ax.scatter(x,y,marker='o' if hit else '^',s=48,color=colors[method],facecolors=colors[method] if hit else 'none',zorder=3)
                if hit and r['bootstrap95_low'] is not None and r['bootstrap95_high'] is not None:
                    ax.vlines(x,r['bootstrap95_low'],r['bootstrap95_high'],color=colors[method],lw=1.3)
                    ax.hlines([r['bootstrap95_low'],r['bootstrap95_high']],x-.035,x+.035,color=colors[method],lw=1.3)
                elif hit and r.get('bootstrap95_high_censored',False):
                    if r['bootstrap95_low'] is not None:ax.vlines(x,r['bootstrap95_low'],y,color=colors[method],lw=1.3)
                    ax.annotate('',xy=(x,y*1.6),xytext=(x,y),arrowprops=dict(arrowstyle='->',color=colors[method],linestyle='--'))
                if not hit:ax.annotate('',xy=(x,y*1.6),xytext=(x,y),arrowprops=dict(arrowstyle='->',color=colors[method]))
            ax.plot([],[],color=colors[method],marker='o',label=method.capitalize())
        ax.set(yscale='log',xticks=range(len(cfg['ranks'])),xticklabels=cfg['ranks'],xlabel='Actuation rank',title=title,
               ylabel='Transitions for >=90% point success');ax.legend(loc='lower right');ax.margins(y=.25)
    fig.suptitle(f"100d rank sweep | absolute target {eps:.6f} | {len(cfg[phase+'_seeds'])} {phase} seeds\nSeparate log scales | Bars: seed-bootstrap 95% CI | open arrows: not reached; dashed arrows: censored CI")
    savefig(fig,dest/'sample_complexity_vs_rank_all_algorithms')
    initial={r['rank']:r['initial_gap'] for r in baseline_summary['oracle_summary']}
    for relative in (False,True):
        fig,axes=plt.subplots(1,5,figsize=(17,3.8),constrained_layout=True)
        for ax,rank in zip(axes,cfg['ranks']):
            divisor=initial[rank] if relative else 1.
            for method in ('dense','truncated'):
                group=[r for r in rates if r['rank']==rank and r['method']==method and r['epsilon']==eps and r['transitions']>0]
                xx=[r['transitions'] for r in group]
                curve=lambda key:[r[key]/divisor if r[key] is not None else np.nan for r in group]
                ax.plot(xx,curve('gap_median'),color=colors[method],ls=styles[method],marker='o',label=method)
                ax.fill_between(xx,curve('gap_q25'),curve('gap_q75'),color=colors[method],alpha=.12)
            ax.axhline(eps/divisor,color='#444',ls='--',lw=.8)
            ax.set(xscale='log',yscale='log',title=f'PI, r={rank}',xlabel='Transitions')
        axes[0].set_ylabel('Gap / initial gap' if relative else 'Absolute gap');axes[0].legend()
        fig.suptitle('Stable observed seeds: median and IQR; all failures retained in success plots')
        savefig(fig,dest/('pi_relative_gap_convergence' if relative else 'pi_absolute_gap_convergence'))
    baseline_rates=baseline/('report-'+phase)/'success_by_budget.csv'
    assert e.sha(baseline_rates)==baseline_hashes['report-'+phase+'/success_by_budget.csv']
    with baseline_rates.open(encoding='utf-8-sig',newline='') as stream:old_rates=list(csv.DictReader(stream))
    for row in old_rates:
        for key in ('rank','transitions'):row[key]=int(row[key])
        for key in ('epsilon','gap_median','gap_q25','gap_q75'):
            row[key]=float(row[key]) if row[key] else None
    all_rates=old_rates+rates
    csv_write(dest/'all_algorithms_success_by_budget.csv',all_rates)
    fig,axes=plt.subplots(3,5,figsize=(17,9),sharey=True,constrained_layout=True)
    for i,route in enumerate(('npg','ce','pi')):
        for j,rank in enumerate(cfg['ranks']):
            ax=axes[i,j]
            for method in ('dense','truncated'):
                group=[r for r in all_rates if r['route']==route and r['rank']==rank
                       and r['method']==method and r['epsilon']==eps and r['transitions']>0]
                xx=[r['transitions'] for r in group]
                ax.plot(xx,[float(r['success_rate']) for r in group],color=colors[method],ls=styles[method],label=method)
                ax.fill_between(xx,[float(r['success_ci95_low']) for r in group],
                                [float(r['success_ci95_high']) for r in group],color=colors[method],alpha=.12)
            ax.axhline(.9,color='#444',ls='--',lw=.8)
            ax.set(xscale='log',title=f'{route.upper()}, r={rank}',xlabel='Transitions',ylim=(-.03,1.03))
        axes[i,0].set_ylabel('Success probability')
    axes[0,0].legend()
    fig.suptitle(f'Common absolute gap target {eps:.6f} | Wilson 95% CI | {phase}')
    savefig(fig,dest/'all_algorithms_success_probability')
    for relative in (False,True):
        fig,axes=plt.subplots(3,5,figsize=(17,10),constrained_layout=True)
        for i,route in enumerate(('npg','ce','pi')):
            for j,rank in enumerate(cfg['ranks']):
                ax=axes[i,j];divisor=initial[rank] if relative else 1.
                for method in ('dense','truncated'):
                    group=[r for r in all_rates if r['route']==route and r['rank']==rank and r['method']==method and r['epsilon']==eps and r['transitions']>0]
                    xx=[r['transitions'] for r in group]
                    curve=lambda key:[r[key]/divisor if r[key] is not None else np.nan for r in group]
                    ax.plot(xx,curve('gap_median'),color=colors[method],ls=styles[method],label=method)
                    ax.fill_between(xx,curve('gap_q25'),curve('gap_q75'),color=colors[method],alpha=.12)
                ax.axhline(eps/divisor,color='#444',ls='--',lw=.8)
                ax.set(xscale='log',yscale='log',title=f'{route.upper()}, r={rank}',xlabel='Transitions')
            axes[i,0].set_ylabel('Gap / initial gap' if relative else 'Absolute gap')
        axes[0,0].legend();fig.suptitle('Median and IQR of stable observed seeds | each route uses its own frozen sampling schedule')
        savefig(fig,dest/('all_algorithms_relative_gap_convergence' if relative else 'all_algorithms_absolute_gap_convergence'))
    oracle=e.read(out/'oracle.json')['references'];oracle_summary=[]
    fig,ax=plt.subplots(figsize=(8.5,4.6),constrained_layout=True)
    for rank,color in zip(cfg['ranks'],['#334e80','#05827b','#72a02d','#bc7435','#92559b']):
        group=[r for r in oracle if r['rank']==rank]
        oracle_summary.append(dict(rank=rank,initial_gap=initial[rank],
            exact_PI_iterations=next((r['stage'] for r in group if r['gap']<=eps),None),
            exact_PI_sensitivity_iterations=next((r['stage'] for r in group if r['gap']<=eps/2),None)))
        visible=[r for r in group if r['stage']<=len(cfg['batch_schedule'])]
        ax.plot([r['stage'] for r in visible],[max(r['gap'],1e-12) for r in visible],color=color,marker='o',label=f'r={rank}')
    ax.axhline(eps,color='#111',ls=':',label='Absolute target')
    ax.set(yscale='log',xticks=range(len(cfg['batch_schedule'])+1),xlabel='Exact PI updates',ylabel='Absolute gap',
           title='Exact PI from common K0 | first four updates; gaps floored at 1e-12 for display')
    ax.legend(ncol=3);savefig(fig,dest/'pi_oracle_convergence')
    csv_write(dest/'systems_and_oracle.csv',oracle_summary)
    joined=[]
    for o in oracle_summary:
        row=dict(o)
        row['sampling_seeds']=len(cfg[phase+'_seeds'])
        row['exact_NPG_iterations']=next(v['exact_iterations'] for v in baseline_summary['oracle_summary'] if v['rank']==o['rank'])
        for route in ('npg','ce','pi'):
            for method in ('dense','truncated'):
                cell=next(r for r in requirements if r['rank']==o['rank'] and r['route']==route and r['method']==method and r['epsilon']==eps)
                prefix=route+'_'+method+'_'
                for key in ('N_hat_epsilon_90','status','bootstrap95_low','bootstrap95_high',
                            'bootstrap95_low_censored','bootstrap95_high_censored',
                            'success_at_N_hat','success_ci95_at_N_hat','max_budget',
                            'max_budget_success_rate','max_budget_success_ci95',
                            'max_budget_failure_rate','max_budget_failure_ci95',
                            'max_budget_instability_rate','max_budget_instability_ci95',
                            'max_budget_numerical_failures','max_budget_gap_median'):
                    row[prefix+key]=cell[key]
        joined.append(row)
    csv_write(dest/'all_algorithms_summary_table.csv',joined)
    e.atomic_json(dest/'baseline_reuse.json',dict(path=str(baseline),summary_sha256=e.sha(baseline/baseline_key),
        original_derived_hashes_verified=True,same_exact_system_artifacts=True,no_historical_learning_repeated=True))
    e.atomic_json(dest/'joined_summary.json',dict(summary,requirements=requirements,oracle_summary=oracle_summary))
    print(json.dumps(dict(status='complete',phase=phase,paired_PI_tasks=len(sources),report=str(dest))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--phase',choices=['pilot','confirm'],default='confirm');a=p.parse_args()
    cfg=e.read(a.output/'resolved_config.json');report(cfg,a.output,a.baseline,a.phase)
