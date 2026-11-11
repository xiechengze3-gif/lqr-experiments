"""Budget envelopes for uncommitted transitions after the CE216 timeout."""
import csv
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys


def read(p):return json.loads(p.read_text())


def finite(v):return float(v) if math.isfinite(v) else None


def quantile(v,q):
    v=sorted(v);x=(len(v)-1)*q;i=int(math.floor(x));j=int(math.ceil(x))
    if i==j or v[i]==v[j]:return v[i]
    return v[i]*(j-x)+v[j]*(x-i)


def audit(cfg):
    out=Path(cfg['output']);dest=out/'report-confirm';summary=read(dest/'summary.json')
    recovery=read(out/'recovery_plan.json');budgets=summary['budgets'];seeds=cfg['confirm_seeds']
    cases=[recovery]+recovery.get('additional_cases',[])
    lost=sum(c['discarded_uncommitted_transition_upper_bound'] for c in cases)
    affected={(c['rank'],c['seed']):(i,c) for i,c in enumerate(cases)}
    assert len(affected)==len(cases)
    maximum_mask=(1<<len(cases))-1
    curves={};allrows=[]
    for rank in cfg['ranks']:
        for seed in seeds:
            raw=read(out/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json');allrows+=raw['records']
            for method in ('dense','truncated'):curves[rank,method,seed]=[r for r in raw['records'] if r['method']==method]
    def available(rank,method,seed,budget,waste):
        candidate=dict(stable=True,gap=cfg['initial_gap'])
        for row in curves[rank,method,seed]:
            entry=affected.get((rank,seed))
            case=entry[1] if entry else None
            offset=case['discarded_uncommitted_transition_upper_bound'] if entry and waste&(1<<entry[0]) and row['ols_samples']>case['committed_OLS_samples'] else 0
            if row['transitions']+offset<=budget:candidate=row
        return candidate
    comparisons=[];rates=[];gaps=[];all_equal=True
    for rank in cfg['ranks']:
        for method in ('dense','truncated'):
            for target in cfg['relative_targets']:
                hits={0:[],maximum_mask:[]}
                for b in budgets:
                    flags={}
                    for waste in (0,maximum_mask):
                        flags[waste]=[]
                        for seed in seeds:
                            r=available(rank,method,seed,b,waste)
                            flags[waste].append(bool(r['stable'] and r['gap'] is not None and r['gap']<=target))
                        if sum(flags[waste])>=27:hits[waste].append(b)
                    same=flags[0]==flags[maximum_mask];all_equal=all_equal and same
                    rates.append(dict(rank=rank,method=method,target=target,transitions=b,
                        successes_zero_discard=sum(flags[0]),successes_max_discard=sum(flags[maximum_mask]),
                        identical_seed_success_indicators=same))
                nominal=next(r for r in summary['requirements'] if r['rank']==rank and r['method']==method and r['relative_target']==target)['N_hat_90']
                endpoints={w:(hits[w][0] if hits[w] else None) for w in (0,maximum_mask)}
                assert endpoints[0]==endpoints[maximum_mask]==nominal,(rank,method,target,endpoints,nominal)
                comparisons.append(dict(rank=rank,method=method,target=target,nominal_N90=nominal,
                    zero_discard_N90=endpoints[0],maximum_discard_N90=endpoints[maximum_mask],sample_complexity_unchanged=True))
            for b in budgets:
                scenarios={}
                for w in range(maximum_mask+1):
                    vals=[]
                    for seed in seeds:
                        r=available(rank,method,seed,b,w);vals.append(r['gap'] if r['stable'] and r['gap'] is not None else math.inf)
                    scenarios[w]=vals
                gaps.append(dict(rank=rank,method=method,transitions=b,
                    gap_median_zero_discard=finite(statistics.median(scenarios[0])),
                    gap_median_max_discard=finite(statistics.median(scenarios[maximum_mask])),
                    gap_q25_max_discard=finite(quantile(scenarios[maximum_mask],.25)),
                    gap_q75_max_discard=finite(quantile(scenarios[maximum_mask],.75)),
                    gap_median_cost_envelope_low=finite(min(statistics.median(v) for v in scenarios.values())),
                    gap_median_cost_envelope_high=finite(max(statistics.median(v) for v in scenarios.values()))))
    assert all_equal,'No bootstrap equivalence claim unless every seed success event is unchanged'
    physical=read(out/'preflight.json')['diagnostic_primitive_transitions']+read(out/'report-pilot/audit.json')['physical_transitions']+summary['audit']['physical_transitions']+read(out/'identification-audit/audit.json')['diagnostic_primitive_transitions']
    result=dict(status='PASS',cases=[{k:c[k] for k in ('rank','seed','failed_job_id','resume_array','committed_OLS_samples','discarded_uncommitted_transition_upper_bound')} for c in cases],
        resource_timeout_attempts_retained=len(cases),
        all_independent_discard_cost_corners_checked=maximum_mask+1,
        additional_uncommitted_transitions_lower=0,additional_uncommitted_transitions_upper=lost,
        discarded_transition_count_exact=False,total_primitive_transitions_lower=physical,
        total_primitive_transitions_upper=physical+lost,
        final_resumed_policy_physical_cost_intervals=[dict(rank=c['rank'],seed=c['seed'],lower=1048832,upper=1048832+c['discarded_uncommitted_transition_upper_bound']) for c in cases],
        all_twenty_N90_values_unchanged=True,all_seed_success_events_at_all_budgets_unchanged=True,
        Wilson_and_paired_bootstrap_N90_intervals_unchanged=True,requirements=comparisons,
        rule='At each physical budget use the latest committed policy whose execution cost fits. Max-discard scenario holds the latest pre-resume policy until its successor fits; all three runs had already met both targets. Raw physical_transitions fields count committed data only; add the lost-work interval for actual execution totals.')
    (dest/'execution_cost_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    for name,rr in [('executed_budget_success_envelopes',rates),('executed_budget_gaps',gaps)]:
        with (dest/(name+'.csv')).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rr[0]));writer.writeheader();writer.writerows(rr)
    plots(cfg,dest,gaps,lost,len(cases))
    return result


def plots(cfg,dest,gaps,lost,case_count):
    if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    for stem in ('absolute_relative_gap_convergence','same_budget_gap_improvement'):
        for ext in ('png','svg'):
            source=dest/(stem+'.'+ext);backup=dest/(stem+'_OLS_prefix.'+ext)
            if source.exists() and not backup.exists():shutil.copyfile(source,backup)
    plt.rcParams.update({'axes.grid':True,'grid.alpha':.2,'font.size':10})
    colors={'dense':'#ba4737','truncated':'#1476a3'}
    fig,axes=plt.subplots(1,5,figsize=(17,3.8),sharey=True,layout='constrained')
    for ax,rank in zip(axes,cfg['ranks']):
        for method,color in colors.items():
            rows=[r for r in gaps if r['rank']==rank and r['method']==method];x=[r['transitions'] for r in rows]
            med=[r['gap_median_max_discard'] for r in rows]
            ax.plot(x,med,'-' if method=='truncated' else '--',color=color,label=method)
            ax.fill_between(x,[r['gap_q25_max_discard'] for r in rows],[r['gap_q75_max_discard'] for r in rows],color=color,alpha=.12)
            ax.fill_between(x,[r['gap_median_cost_envelope_low'] for r in rows],
                            [r['gap_median_cost_envelope_high'] for r in rows],color='#e59c28',alpha=.4)
        for target in cfg['relative_targets']:ax.axhline(target,color='.5',ls=':')
        ax.set(xscale='log',yscale='log',xlabel='Primitive transition budget',title=f'rank {rank}')
    axes[0].set_ylabel('Absolute / relative gap');axes[-1].legend()
    fig.suptitle(f'Executed-budget gaps | medians/IQR at maximum discarded-work cost\nOrange: median envelope from 0 to {lost:,} total lost transitions ({case_count} resumed seed runs)')
    for ext in ('png','svg'):fig.savefig(dest/('absolute_relative_gap_convergence.'+ext),dpi=180,facecolor='white')
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.2),layout='constrained')
    reference={r['transitions']:r['gap_median_max_discard'] for r in gaps if r['rank']==cfg['n'] and r['method']=='dense'}
    for rank in cfg['ranks']:
        rows=[r for r in gaps if r['rank']==rank and r['method']=='truncated']
        ax.plot([r['transitions'] for r in rows],[reference[r['transitions']]/r['gap_median_max_discard'] for r in rows],'-o',ms=3,label=f'rank {rank} + truncation')
    ax.axhline(1,color='.4',ls=':');ax.set(xscale='log',yscale='log',xlabel='Primitive transition budget',
        ylabel='Full-rank dense median gap / truncated median gap',title='Same executed budget | maximum discarded-work scenario')
    ax.legend()
    for ext in ('png','svg'):fig.savefig(dest/('same_budget_gap_improvement.'+ext),dpi=180,facecolor='white')
    plt.close(fig)
