"""Paired matched-gap reports and independent saved-policy audits."""
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import rank_sweep100 as e
import rank_sweep100_pi as pi
from rank_sweep100_pi_report import summarize
from rank_sweep100_report import csv_write,success
from ce_matched_initial_gap_report import interval
from matched_gap_npg_pi import options,load


def audit(cfg,phase,route):
    folder=Path(cfg['output']);checked=0;full_pairs=0;maximum=0.;critic_checks=0
    for rank in cfg['ranks']:
        s,_=load(cfg,rank)
        for seed in cfg[phase+'_seeds']:
            stem=f'{route}-r{rank:03d}-s{seed:04d}'
            raw=e.read(folder/'raw'/(stem+'.json'));path=folder/'policies'/(stem+'.npz')
            assert e.sha(path)==raw['policy_sha256']
            with np.load(path) as z:ks={m:z[m].copy() for m in z.files}
            critics=None
            if route=='pi':
                path=folder/'critics'/(stem+'.npz');assert e.sha(path)==raw['critic_sha256']
                with np.load(path) as z:critics={m:z[m].copy() for m in z.files}
            for m in ('dense','truncated'):
                group=[v for v in raw['records'] if v['method']==m]
                assert len(group)==len(ks[m]);stable=True
                for row,k in zip(group,ks[m]):
                    if not row['observed']:continue
                    if row['failure']=='numerical_failure':continue
                    q,_=e.evaluate(s,k);assert q['stable']==row['stable']
                    stable=stable and q['stable'];assert stable==row['whole_path_stable']
                    if q['stable']:
                        f=s['A']-s['B']@k;cov=solve_discrete_lyapunov(f,s['W']);delta=k-s['Kstar']
                        alternative=float(np.trace(cov@delta.T@(s['R']+s['B'].T@s['Pstar']@s['B'])@delta))
                        err=max(abs(q['gap']-row['gap']),abs(alternative-row['gap']))
                        assert err<1e-9;maximum=max(maximum,err)
                    if critics is not None and row['stage']>0 and row['failure'] is None:
                        h=critics[m][row['stage']]
                        np.testing.assert_allclose(pi.update(h[100:,100:]-s['R'],h[100:,:100],s['R'],m,rank),k,atol=2e-12)
                        critic_checks+=1
                    checked+=1
            if rank==100:
                np.testing.assert_array_equal(ks['dense'],ks['truncated']);full_pairs+=len(ks['dense'])
                if critics is not None:np.testing.assert_array_equal(critics['dense'],critics['truncated'])
    return dict(status='PASS',checked_policies=checked,performance_identity_max_error=maximum,
        full_rank_bitwise_pairs=full_pairs,independent_PI_actor_replays=critic_checks)


def report(parent,phase):
    out=Path(parent['output']);dest=out/f'report-{phase}';dest.mkdir(exist_ok=True)
    allreq=[];allrates=[];contrasts=[];audits={};summaries={}
    idx=np.random.default_rng(2026101901).integers(0,len(parent[phase+'_seeds']),size=(2000,len(parent[phase+'_seeds'])))
    for route in ('npg','pi'):
        cfg=options(parent,route);summary,rates,rows,sources=summarize(cfg,Path(cfg['output']),phase)
        for q in summary['requirements']+rates:q['route']=route
        audits[route]=audit(cfg,phase,route)
        summary.update(route=route,audit=audits[route]);summaries[route]=summary
        allreq+=summary['requirements'];allrates+=rates
        e.atomic_json(dest/(route+'-summary.json'),summary)
        csv_write(dest/(route+'-all-checkpoints.csv'),rows);csv_write(dest/(route+'-sources.csv'),sources)
        grid=sorted({r['transitions'] for r in rows});boots={}
        for rank in cfg['ranks']:
            for method in ('dense','truncated'):
                for eps in parent['relative_targets']:
                    hits=np.array([[success(next(r for r in rows if r['rank']==rank and r['method']==method and r['seed']==seed and r['transitions']==budget),eps)
                        for budget in grid] for seed in cfg[phase+'_seeds']])
                    good=hits[idx].mean(axis=1)>=.9-1e-12
                    boots[rank,method,eps]=np.where(good.any(axis=1),np.asarray(grid)[good.argmax(axis=1)],np.inf)
        for eps in parent['relative_targets']:
            full=next(q for q in summary['requirements'] if q['rank']==100 and q['method']=='dense' and q['epsilon']==eps)
            for rank in cfg['ranks']:
                low=next(q for q in summary['requirements'] if q['rank']==rank and q['method']=='truncated' and q['epsilon']==eps)
                a,b=full['N_hat_epsilon_90'],low['N_hat_epsilon_90']
                if a is None or b is None:
                    ratio_ci=dict(low=None,high=None,undefined=True,
                        numerator_censored=a is None,denominator_censored=b is None)
                else:
                    numerator=boots[100,'dense',eps];denominator=boots[rank,'truncated',eps]
                    censored=~np.isfinite(numerator)|~np.isfinite(denominator)
                    if censored.any():
                        ratio_ci=dict(low=None,high=None,undefined=True,
                            bootstrap_censored_fraction=float(censored.mean()))
                    else:
                        ratio_ci=interval(numerator/denominator)
                contrasts.append(dict(route=route,rank=rank,relative_target=eps,full_dense_N=a,low_truncated_N=b,
                    full_over_low_ratio=a/b if a is not None and b is not None else None,
                    paired_bootstrap95=ratio_ci,full_status=full['status'],low_status=low['status']))
    csv_write(dest/'sample_complexity.csv',allreq);csv_write(dest/'success_by_budget.csv',allrates)
    csv_write(dest/'low_truncated_vs_full_dense.csv',contrasts)
    e.atomic_json(dest/'summary.json',dict(status='complete',phase=phase,requirements=allreq,contrasts=contrasts,audits=audits,
        seeds=parent[phase+'_seeds'],relative_targets=parent['relative_targets'],initial_gap=1,
        interpretation='Conditional on one fixed system family; ranks change control and exploration. Grid threshold, not continuous optimum.',
        physical_transitions=sum(s['physical_transitions'] for s in summaries.values()),
        algorithm_charged_transitions=sum(s['algorithm_charged_transitions'] for s in summaries.values())))
    plt.rcParams.update({'font.size':9,'axes.grid':True,'grid.alpha':.18})
    colors={'dense':'#b94835','truncated':'#176da0'}
    def save(fig,name):
        for ext in ('png','svg'):fig.savefig(dest/(name+'.'+ext),dpi=180,facecolor='white')
        plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for axesrow,route in zip(axes,('npg','pi')):
        for ax,eps in zip(axesrow,parent['relative_targets']):
            for method in colors:
                rr=[q for q in allreq if q['route']==route and q['method']==method and q['epsilon']==eps]
                ax.plot([q['rank'] for q in rr],
                    [q['N_hat_epsilon_90'] if q['N_hat_epsilon_90'] is not None else np.nan for q in rr],
                    '-o',color=colors[method],label=method)
                for q in rr:
                    if q['N_hat_epsilon_90'] is None:ax.plot(q['rank'],q['max_budget'],'^',mfc='none',mec=colors[method])
                    elif q['bootstrap95_low'] is not None:
                        upper=q['bootstrap95_high'] if q['bootstrap95_high'] is not None else q['max_budget']
                        ax.vlines(q['rank'],q['bootstrap95_low'],upper,color=colors[method])
                        if q['bootstrap95_high'] is None:
                            ax.annotate('',xy=(q['rank'],upper*1.15),xytext=(q['rank'],upper),arrowprops=dict(arrowstyle='->',color=colors[method]))
            ax.set(yscale='log',xticks=parent['ranks'],xlabel='Actuation rank',ylabel='Transitions for >=90% empirical success',title=f'{route.upper()} | relative target {eps:g}')
            ax.legend()
            ax.set_ylim(top=max(q['max_budget'] for q in allreq if q['route']==route)*1.3)
    fig.suptitle(f'Initial gap = 1 | {len(parent[phase+"_seeds"])} seeds | open triangles: not reached; arrows: censored CI\nPaired bootstrap 95% intervals; lines break at censored rank points')
    save(fig,'sample_complexity_vs_rank')
    for eps in parent['relative_targets']:
        fig,axes=plt.subplots(2,5,figsize=(17,7),sharey=True,layout='constrained')
        for rowaxes,route in zip(axes,('npg','pi')):
            for ax,rank in zip(rowaxes,parent['ranks']):
                for method in colors:
                    rr=[q for q in allrates if q['route']==route and q['rank']==rank and q['method']==method and q['epsilon']==eps and q['transitions']>0]
                    xx=[q['transitions'] for q in rr];ax.plot(xx,[q['success_rate'] for q in rr],'-',color=colors[method],label=method)
                    ax.fill_between(xx,[q['success_ci95_low'] for q in rr],[q['success_ci95_high'] for q in rr],color=colors[method],alpha=.13)
                ax.axhline(.9,color='.4',ls=':');ax.set(xscale='log',ylim=(-.03,1.03),xlabel='Cumulative transitions',title=f'{route.upper()} | rank {rank}')
            rowaxes[0].set_ylabel('Success probability');rowaxes[-1].legend()
        fig.suptitle(f'Relative target {eps:g} | stable whole path required | Wilson 95% intervals')
        save(fig,'success_probability_'+str(eps).replace('.','p'))
    fig,axes=plt.subplots(2,5,figsize=(17,7),sharey=True,layout='constrained')
    for rowaxes,route in zip(axes,('npg','pi')):
        for ax,rank in zip(rowaxes,parent['ranks']):
            for method in colors:
                rr=[q for q in allrates if q['route']==route and q['rank']==rank and q['method']==method and q['epsilon']==.1 and q['transitions']>0]
                xx=[q['transitions'] for q in rr]
                ax.plot(xx,[q['gap_median'] for q in rr],color=colors[method],label=method)
                ax.fill_between(xx,[q['gap_q25'] for q in rr],[q['gap_q75'] for q in rr],color=colors[method],alpha=.13)
            for eps in parent['relative_targets']:ax.axhline(eps,ls=':',color='.4')
            ax.set(xscale='log',yscale='log',xlabel='Cumulative transitions',title=f'{route.upper()} | rank {rank}')
        rowaxes[0].set_ylabel('Absolute = relative gap');rowaxes[-1].legend()
    fig.suptitle('Gap convergence | median and IQR among stable observed runs\nFailures retained in success probabilities and tables; common initial gap = 1')
    save(fig,'absolute_relative_gap_convergence')
    print('Report complete: '+str(dest),flush=True)
