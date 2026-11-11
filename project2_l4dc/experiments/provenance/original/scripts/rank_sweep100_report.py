"""Conditional-on-system, paired-seed rank-sweep summaries and publication plots."""
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from rank_sweep100 import read, sha, atomic_json


def csv_write(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(rows)


def wilson(k,n):
    z=1.959963984540054; p=k/n; den=1+z*z/n
    mid=(p+z*z/(2*n))/den; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,mid-half),min(1.,mid+half)]


def success(row,eps):
    return bool(row['observed'] and row['stable'] and row.get('whole_path_stable',True)
                and row['gap'] is not None and row['gap']<=eps)


def threshold(curve,level=.9):
    okay=[row['success_rate']>=level-1e-12 for row in curve]
    first=next((row['transitions'] for row,hit in zip(curve,okay) if hit),None)
    sustained=next((row['transitions'] for i,row in enumerate(curve) if all(okay[i:])),None)
    prev=max((row['transitions'] for row in curve if first is not None and row['transitions']<first),default=None)
    return first,sustained,prev


def make_report(cfg,phase='confirm',partial=False):
    out=Path(cfg['output']); verification=read(out/'verification.json'); ident=verification['identity']
    seeds=cfg[phase+'_seeds']; wanted=set(seeds); rows=[]; sources=[]; raw=[]
    for path in sorted((out/'raw').glob('*.json')):
        data=read(path)
        if data['seed'] not in wanted:continue
        assert data['identity']==ident
        raw.append(data);rows+=data['records'];sources.append(dict(path=str(path),sha256=sha(path)))
    expected=len(seeds)*len(cfg['ranks'])*2
    if not partial:assert len(raw)==expected,(len(raw),expected)
    report=out/('report-'+phase);report.mkdir(exist_ok=True)
    epsilon=verification['epsilon'];rates=[];requirements=[];pairs=[]
    epoch_budgets=set();epoch_total=0
    for count,length in cfg['schedule_segments']:
        epoch_total+=length*(cfg['burn']+(count+1)*cfg['horizon']);epoch_budgets.add(epoch_total)
    available={}
    for route in ('npg','ce'):
        for rank in cfg['ranks']:
            for method in ('dense','truncated'):
                group=[r for r in rows if r['route']==route and r['rank']==rank and r['method']==method]
                if not group:continue
                grid=sorted(set(r['transitions'] for r in group)); groupseeds=sorted(set(r['seed'] for r in group));n=len(groupseeds)
                assert n==len([r for r in group if r['transitions']==grid[-1]])
                available[route,rank,method]=groupseeds
                for eps in (epsilon,epsilon/2):
                    curve=[]
                    for budget in grid:
                        current=[r for r in group if r['transitions']==budget];assert len(current)==n
                        count=sum(success(r,eps) for r in current)
                        instability=sum(r['failure']=='controller_instability' or (r['failure']=='prior_failure' and
                                            any(x['failure']=='controller_instability' and x['seed']==r['seed'] for x in group)) for r in current)
                        numerical=sum(r['failure'] in ('numerical_failure','riccati_failure') or (r['failure']=='prior_failure' and
                                            any(x['failure']=='numerical_failure' and x['seed']==r['seed'] for x in group)) for r in current)
                        valid=[r['gap'] for r in current if r['stable'] and r['observed']]
                        lo,hi=wilson(count,n); il,ih=wilson(instability,n)
                        row=dict(route=route,rank=rank,method=method,epsilon=eps,transitions=budget,seeds=n,
                                 successes=count,success_rate=count/n,success_ci95_low=lo,success_ci95_high=hi,
                                 failures=n-count,failure_rate=1-count/n,failure_ci95_low=1-hi,failure_ci95_high=1-lo,
                                 instabilities=instability,instability_rate=instability/n,
                                 instability_ci95_low=il,instability_ci95_high=ih,numerical_failures=numerical,
                                 stable_observed=len(valid),gap_median=float(np.median(valid)) if valid else None,
                                 gap_q25=float(np.quantile(valid,.25)) if valid else None,
                                 gap_q75=float(np.quantile(valid,.75)) if valid else None,
                                 relative_gap_median=float(np.median(valid))/next(x['initial_gap'] for x in verification['invariants'] if x['rank']==rank) if valid else None)
                        curve.append(row);rates.append(row)
                    first,sustained,prev=threshold(curve,cfg['required_success_fraction'])
                    coarse=[r for r in curve if (r['transitions'] in epoch_budgets if route=='npg' else
                              (r['transitions']-cfg['burn'])>0 and
                              ((r['transitions']-cfg['burn']) & (r['transitions']-cfg['burn']-1))==0)]
                    coarse_first,coarse_sustained,_=threshold(coarse,cfg['required_success_fraction'])
                    # Paired cluster bootstrap across the complete seed curves.
                    hits=np.array([[success(next(r for r in group if r['seed']==seed and r['transitions']==budget),eps)
                                    for budget in grid] for seed in groupseeds],dtype=float)
                    rng=np.random.default_rng(81132)
                    weights=rng.multinomial(n,np.full(n,1/n),size=2000)
                    boot_rates=weights@hits/n
                    boot_good=boot_rates>=cfg['required_success_fraction']-1e-12
                    boot_first=np.array([grid[np.flatnonzero(g)[0]] if g.any() else np.inf for g in boot_good])
                    # Order statistics avoid interpolating finite and infinite censored values.
                    order=np.sort(boot_first);bl=float(order[int(.025*len(order))]);bh=float(order[int(.975*len(order))])
                    endpoint=curve[-1]
                    requirements.append(dict(route=route,rank=rank,method=method,epsilon=eps,seeds=n,
                         N_hat_epsilon_90=first,status='reached' if first is not None else 'not reached',
                         coarse_geometric_N_hat=coarse_first,coarse_geometric_sustained_N_hat=coarse_sustained,
                         sustained_N_hat=sustained,previous_tested_budget=prev,max_budget=grid[-1],
                         bootstrap95_low=None if np.isinf(bl) else int(bl),bootstrap95_high=None if np.isinf(bh) else int(bh),
                         bootstrap95_low_censored=bool(np.isinf(bl)),bootstrap95_high_censored=bool(np.isinf(bh)),
                         bootstrap_censoring_fraction=float(np.mean(np.isinf(boot_first))),
                         success_at_N_hat=next((r['success_rate'] for r in curve if r['transitions']==first),None),
                         success_ci95_at_N_hat=next(([r['success_ci95_low'],r['success_ci95_high']] for r in curve if r['transitions']==first),None),
                         max_budget_successes=endpoint['successes'],max_budget_success_rate=endpoint['success_rate'],
                         max_budget_success_ci95=[endpoint['success_ci95_low'],endpoint['success_ci95_high']],
                         max_budget_failure_rate=endpoint['failure_rate'],max_budget_instabilities=endpoint['instabilities'],
                         max_budget_failure_ci95=[endpoint['failure_ci95_low'],endpoint['failure_ci95_high']],
                         max_budget_instability_rate=endpoint['instability_rate'],
                         max_budget_instability_ci95=[endpoint['instability_ci95_low'],endpoint['instability_ci95_high']],
                         max_budget_numerical_failures=endpoint['numerical_failures'],max_budget_gap_median=endpoint['gap_median']))
            # Same seed-pair differences, preserving unstable runs in separate counts.
            ds=[r for r in rows if r['route']==route and r['rank']==rank and r['method']=='dense']
            ts=[r for r in rows if r['route']==route and r['rank']==rank and r['method']=='truncated']
            if not ds or not ts:continue
            budget=max(r['transitions'] for r in ds);values=[];win=0;common=[]
            for d in [r for r in ds if r['transitions']==budget]:
                t=next(r for r in ts if r['seed']==d['seed'] and r['transitions']==budget)
                common.append(d['seed']);win+=int(success(t,epsilon))-int(success(d,epsilon))
                if d['stable'] and t['stable'] and d['observed'] and t['observed']:values.append(t['gap']-d['gap'])
            ci=[None,None]
            if values:
                rng=np.random.default_rng(60017);v=np.array(values)
                boots=v[rng.integers(len(v),size=(2000,len(v)))].mean(axis=1);ci=np.quantile(boots,[.025,.975]).tolist()
            pairs.append(dict(route=route,rank=rank,transitions=budget,all_paired_seeds=len(common),
                              truncated_minus_dense_success_fraction=win/len(common),jointly_stable_pairs=len(values),
                              conditional_gap_difference_mean=float(np.mean(values)) if values else None,
                              conditional_gap_difference_ci95=ci))
    oracle_summary=[]
    for item in verification['invariants']:
        rank=item['rank'];row=dict(item)
        for kind in ('exact','finite_H'):
            group=[r for r in verification['oracle'] if r['rank']==rank and r['kind']==kind]
            row[kind+'_iterations']=next((r['stage'] for r in group if r['gap']<=epsilon),None)
            row[kind+'_sensitivity_iterations']=next((r['stage'] for r in group if r['gap']<=epsilon/2),None)
            row[kind+'_gap_at_learning_endpoint']=next(r['gap'] for r in group if r['stage']==sum(x[1] for x in cfg['schedule_segments']))
        oracle_summary.append(row)
    csv_write(report/'all_checkpoints.csv',rows);csv_write(report/'success_by_budget.csv',rates)
    csv_write(report/'sample_complexity.csv',requirements);csv_write(report/'systems_and_oracle.csv',oracle_summary)
    csv_write(report/'paired_comparisons.csv',pairs);csv_write(report/'sources.csv',sources)
    joined=[]
    for o in oracle_summary:
        row={key:o[key] for key in ('rank','initial_gap','exact_iterations','finite_H_iterations')}
        for route in ('npg','ce'):
            for method in ('dense','truncated'):
                cell=next((r for r in requirements if r['route']==route and r['method']==method and r['rank']==o['rank'] and r['epsilon']==epsilon),None)
                if cell is None:continue
                prefix=route+'_'+method+'_'
                for key in ('N_hat_epsilon_90','status','max_budget','max_budget_success_rate','max_budget_success_ci95',
                            'max_budget_failure_rate','max_budget_failure_ci95','max_budget_instability_rate',
                            'max_budget_instability_ci95','bootstrap95_low','bootstrap95_high'):
                    row[prefix+key]=cell[key]
        joined.append(row)
    csv_write(report/'summary_table.csv',joined)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':120,
                         'savefig.dpi':180,'axes.grid':True,'grid.alpha':.2})
    colors={'dense':'#b94835','truncated':'#176da0'}
    # Censor arrows retain all requested ranks, even when neither method attains.
    fig,axes=plt.subplots(1,2,figsize=(12,4.9),constrained_layout=True)
    for ax,route,title in zip(axes,('npg','ce'),('Stein NPG','Certainty equivalence')):
        for method,offset in [('dense',-.12),('truncated',.12)]:
            group=[r for r in requirements if r['route']==route and r['method']==method and r['epsilon']==epsilon]
            group.sort(key=lambda r:r['rank'])
            if not group:continue
            xx=np.array([cfg['ranks'].index(r['rank']) for r in group])+offset
            yy=[r['N_hat_epsilon_90'] if r['N_hat_epsilon_90'] is not None else r['max_budget'] for r in group]
            attained_y=[y if r['N_hat_epsilon_90'] is not None else np.nan for y,r in zip(yy,group)]
            ax.plot(xx,attained_y,color=colors[method],lw=1,alpha=.45)
            for x,y,row in zip(xx,yy,group):
                hit=row['N_hat_epsilon_90'] is not None
                if hit and row['bootstrap95_low'] is not None and row['bootstrap95_high'] is not None:
                    lo,hi=row['bootstrap95_low'],row['bootstrap95_high']
                    ax.vlines(x,lo,hi,color=colors[method],lw=1.3,alpha=.8)
                    ax.hlines([lo,hi],x-.035,x+.035,color=colors[method],lw=1.3,alpha=.8)
                ax.scatter(x,y,marker='o' if hit else '^',s=52,color=colors[method],facecolors=colors[method] if hit else 'none',zorder=3)
                if not hit:ax.annotate('',xy=(x,y*1.6),xytext=(x,y),arrowprops=dict(arrowstyle='->',color=colors[method]))
            ax.plot([],[],color=colors[method],marker='o',label=method.capitalize())
        ax.set(yscale='log',xticks=range(len(cfg['ranks'])),xticklabels=cfg['ranks'],xlabel='Actuation rank',title=title,
               ylabel='Primitive transitions for >=90% point success')
        ax.legend(loc='best');ax.margins(y=.25)
    fig.suptitle(f'100d rank sweep | absolute target {epsilon:.6f}\nBars: seed-bootstrap 95% CI | open arrows: not reached')
    savefig(fig,report/'sample_complexity_vs_rank')
    for route in ('npg','ce'):
        fig,axes=plt.subplots(1,5,figsize=(17,3.7),sharey=True,constrained_layout=True)
        for ax,rank in zip(axes,cfg['ranks']):
            for method in ('dense','truncated'):
                vals=[r for r in rates if r['route']==route and r['rank']==rank and r['method']==method and r['epsilon']==epsilon and r['transitions']>0]
                if not vals:continue
                vals.sort(key=lambda r:r['transitions']);xx=[r['transitions'] for r in vals]
                ax.plot(xx,[r['success_rate'] for r in vals],color=colors[method],marker='.',label=method)
                ax.fill_between(xx,[r['success_ci95_low'] for r in vals],[r['success_ci95_high'] for r in vals],color=colors[method],alpha=.12)
            ax.axhline(.9,color='#444',ls='--',lw=.8);ax.set(title=f'r={rank}',xscale='log',xlabel='Transitions',ylim=(-.03,1.03))
        axes[0].set_ylabel('Success probability (Wilson 95% CI)');axes[0].legend()
        fig.suptitle(f'{route.upper()} | common absolute target {epsilon:.6f} | {phase}')
        savefig(fig,report/f'{route}_success_probability')
    for relative in (False,True):
        fig,axes=plt.subplots(2,5,figsize=(17,7),constrained_layout=True)
        for j,rank in enumerate(cfg['ranks']):
            initial=next(r['initial_gap'] for r in oracle_summary if r['rank']==rank)
            for i,route in enumerate(('npg','ce')):
                ax=axes[i,j]
                for method in ('dense','truncated'):
                    vals=[r for r in rates if r['route']==route and r['rank']==rank and r['method']==method and r['epsilon']==epsilon and r['transitions']>0]
                    vals.sort(key=lambda r:r['transitions']); divisor=initial if relative else 1.
                    xx=[r['transitions'] for r in vals];mid=[r['gap_median']/divisor if r['gap_median'] is not None else np.nan for r in vals]
                    lo=[r['gap_q25']/divisor if r['gap_q25'] is not None else np.nan for r in vals]
                    hi=[r['gap_q75']/divisor if r['gap_q75'] is not None else np.nan for r in vals]
                    ax.plot(xx,mid,color=colors[method],label=method);ax.fill_between(xx,lo,hi,color=colors[method],alpha=.12)
                ax.axhline(epsilon/(initial if relative else 1.),color='#444',ls='--',lw=.8)
                ax.set(xscale='log',yscale='log',xlabel='Transitions',title=f'{route.upper()}, r={rank}')
        axes[0,0].set_ylabel('Gap / initial gap' if relative else 'Absolute gap');axes[1,0].set_ylabel('Gap / initial gap' if relative else 'Absolute gap')
        axes[0,0].legend();fig.suptitle('Stable observed seeds: median and IQR; all failures remain in success plots')
        savefig(fig,report/('relative_gap_convergence' if relative else 'absolute_gap_convergence'))
    fig,ax=plt.subplots(figsize=(8.5,4.6),constrained_layout=True)
    palette=['#334e80','#05827b','#72a02d','#bc7435','#92559b']
    for rank,color in zip(cfg['ranks'],palette):
        for kind,style in [('exact','-'),('finite_H','--')]:
            vals=[r for r in verification['oracle'] if r['rank']==rank and r['kind']==kind]
            ax.plot([r['stage'] for r in vals],[max(r['gap'],1e-12) for r in vals],ls=style,color=color,label=f'r={rank}' if kind=='exact' else None)
    ax.axhline(epsilon,color='#111',ls=':',label='Absolute target');ax.set(yscale='log',xlabel='Oracle updates',ylabel='Absolute gap',title='Oracle optimization | solid: exact | dashed: finite H')
    ax.legend(ncol=3);savefig(fig,report/'oracle_convergence')
    result=dict(status='partial' if len(raw)<expected else 'complete',phase=phase,epsilon=epsilon,sensitivity_epsilon=epsilon/2,
                identity=ident,n=cfg['n'],m=cfg['n'],ranks=cfg['ranks'],system_seed=cfg['system_seed'],
                learning_updates=sum(x[1] for x in cfg['schedule_segments']),verification_execution=verification.get('execution'),
                source_job_submission=read(out/'submission.json') if (out/'submission.json').exists() else None,
                expected_tasks=expected,completed_tasks=len(raw),conditional_on_one_system=True,
                physical_transitions=sum(d['physical_transitions'] for d in raw),
                algorithm_charged_transitions=sum(sum(d['algorithm_actual_transitions'].values()) if d['route']=='npg' else 2*d['physical_transitions'] for d in raw),
                oracle_summary=oracle_summary,requirements=requirements,paired_comparisons=pairs)
    atomic_json(report/'summary.json',result)
    # Plain-text report is generated as part of the requested result artifacts.
    lines=[f'# 100d rank sweep ({phase})',f'',f'Completed {len(raw)}/{expected} paired task groups. epsilon={epsilon:.12g}.',
           '', 'Pointwise Nhat uses the first tested budget with >=90% empirical success. Sustained thresholds are also saved.',
           'Wilson intervals describe seed success conditional on the single fixed system. They do not certify a population success probability >=90%.',
           'Bootstrap intervals resample complete seed curves; a null upper endpoint denotes censoring at the maximum budget.',
           'NPG success requires a stable complete learning path; CE success requires a stable final true-system policy.',
           'Relative gap means (J-Jstar)/(J0-Jstar); the absolute target is shared across ranks.',
           'All burn-in and baseline transitions are charged. Paired computations shared before a fork are counted for each algorithm; physical simulation work is logged separately.',
           '', '| Rank | Initial gap | Exact / finite-H oracle iterations | NPG dense / truncated | CE dense / truncated |',
           '|---|---:|---:|---:|---:|']
    for row in oracle_summary:
        rank=row['rank'];values=[]
        for route in ('npg','ce'):
            cell=[]
            for method in ('dense','truncated'):
                r=next((r for r in requirements if r['route']==route and r['rank']==rank and r['method']==method and r['epsilon']==epsilon),None)
                cell.append(f"{r['N_hat_epsilon_90']:,}" if r and r['N_hat_epsilon_90'] is not None else 'not reached')
            values.append(' / '.join(cell))
        lines.append(f"| {rank} | {row['initial_gap']:.8f} | {row['exact_iterations']} / {row['finite_H_iterations']} | {values[0]} | {values[1]} |")
    lines+=['','See sample_complexity.csv for failure rates, instability rates, Wilson 95% intervals, bootstrap censoring, and sensitivity results.',
            'Cross-rank changes alter controllability and exploration state distributions; no cross-rank estimator-only causal conclusion is identified.']
    (report/'findings.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],phase=phase,completed_tasks=len(raw),
                         report=str(report),sample_complexity_rows=len(requirements))),flush=True)


def savefig(fig,path):
    for ext in ('png','svg'):fig.savefig(str(path)+'.'+ext)
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--phase',choices=['pilot','confirm'],default='confirm');parser.add_argument('--partial',action='store_true')
    args=parser.parse_args();make_report(read(args.manifest),args.phase,args.partial)
