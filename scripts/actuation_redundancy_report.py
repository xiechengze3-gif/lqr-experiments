"""Summaries and scientific plots for the fixed effective actuation experiment."""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

COLORS = {'dense':'#b84a39','truncated':'#2168a1'}
LABELS = {'dense':'Dense NPG','truncated':'Rank-4 truncated NPG'}


def write_csv(path, rows):
    keys=list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys); writer.writeheader(); writer.writerows(rows)


def stats(values):
    values=np.array([v for v in values if v is not None],dtype=float)
    if not len(values):return dict(n=0,median=None,q25=None,q75=None,mean=None,sd=None)
    return dict(n=len(values),median=float(np.median(values)),q25=float(np.quantile(values,.25)),
                q75=float(np.quantile(values,.75)),mean=float(np.mean(values)),
                sd=float(np.std(values,ddof=1)) if len(values)>1 else 0.)


def wilson(successes, total):
    z=1.95996398454;p=successes/total;den=1+z*z/total
    mid=(p+z*z/(2*total))/den; half=z*np.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [float(max(0,mid-half)),float(min(1,mid+half))]


def fmt(value):
    return 'censored' if value is None else f'{value:,.4g}'


def report(out):
    out=Path(out); cfg=json.loads((out/'resolved_config.json').read_text(encoding='utf-8'))
    ident=cfg['identity']; expected=len(cfg['action_dimensions'])*len(cfg['trial_seeds'])
    files=list((out/'raw').glob('*.json')); assert len(files)==expected,(len(files),expected)
    rows=[]
    for path in sorted(files):
        data=json.loads(path.read_text(encoding='utf-8')); assert data['identity']==ident
        rows.extend([dict(m=data['m'],redundant_dimensions=data['m']-cfg['rank'],seed=data['seed'],**r) for r in data['records']])
    stages=len(cfg['schedule']); final=[r for r in rows if r['stage']==stages]
    report_dir=out/'report'; report_dir.mkdir(exist_ok=True)
    write_csv(report_dir/'all_checkpoints.csv',rows); write_csv(report_dir/'endpoints.csv',final)
    groups={}; summaries=[]; aggregates=[]; sample_rows=[]; thresholds=[]; pairs=[]
    for m in cfg['action_dimensions']:
        for method in cfg['methods']:
            cell=[r for r in rows if r['m']==m and r['method']==method]
            group=[r for r in final if r['m']==m and r['method']==method]; groups[m,method]=cell
            stable=[r for r in group if r['stable'] and r['observed']]
            instability_seeds={r['seed'] for r in cell if r.get('failure')=='controller_instability'}
            numerical_seeds={r['seed'] for r in cell if r.get('failure')=='numerical_failure'}
            summary=dict(m=m,redundant_dimensions=m-cfg['rank'],method=method,seeds=len(group),stable=len(stable),
                         instability_count=len(instability_seeds),instability_rate=len(instability_seeds)/len(group),
                         instability_rate_95ci=wilson(len(instability_seeds),len(group)),
                         numerical_failure_count=len(numerical_seeds),
                         assigned_transitions=group[0]['transitions'],
                         actual_transitions_sum=sum(r['actual_transitions'] for r in group))
            for key in ('gap','relative_gap','redundant_loss','effective_loss'):
                for metric,val in stats([r[key] for r in stable]).items():summary[key+'_'+metric]=val
            for target in cfg['relative_targets']:
                success=sum(r['stable'] and r['observed'] and r['relative_gap']<=target for r in group)
                summary['success_'+str(target)]=success/len(group)
            summaries.append(summary)
            for stage in range(stages+1):
                current=[r for r in cell if r['stage']==stage]
                stable_current=[r for r in current if r['stable'] and r['observed']]
                ag=dict(m=m,method=method,stage=stage,transitions=current[0]['transitions'],
                        total=len(current),stable=len(stable_current))
                for key in ('gap','relative_gap','redundant_loss','effective_loss'):
                    ag.update({key+'_'+k:v for k,v in stats([r[key] for r in stable_current]).items()})
                for target in cfg['relative_targets']:
                    ag['success_'+str(target)]=sum(r['relative_gap']<=target for r in stable_current)/len(current)
                aggregates.append(ag)
            for target in cfg['relative_targets']:
                for seed in cfg['trial_seeds']:
                    ordered=sorted([r for r in cell if r['seed']==seed],key=lambda r:r['stage'])
                    hits=np.array([r['observed'] and r['stable'] and r['relative_gap']<=target for r in ordered])
                    sustained=np.logical_and.accumulate(hits[::-1])[::-1]
                    first=next((r['transitions'] for r,hit in zip(ordered,hits) if hit),None)
                    sustained_n=next((r['transitions'] for r,hit in zip(ordered,sustained) if hit),None)
                    sample_rows.append(dict(m=m,method=method,seed=seed,target=target,first_transitions=first,
                                            sustained_transitions=sustained_n,first_right_censored=first is None,
                                            sustained_right_censored=sustained_n is None,
                                            censoring_budget=ordered[-1]['transitions']))
                selected=[r for r in aggregates if r['m']==m and r['method']==method]
                values=np.array([r['success_'+str(target)] for r in selected])
                good=values>=cfg['required_success_fraction']-1e-12
                sustained=np.logical_and.accumulate(good[::-1])[::-1]
                first=next((r['transitions'] for r,hit in zip(selected,good) if hit),None)
                sustain=next((r['transitions'] for r,hit in zip(selected,sustained) if hit),None)
                individual=[r for r in sample_rows if r['m']==m and r['method']==method and r['target']==target]
                thresholds.append(dict(m=m,method=method,target=target,required_success_fraction=cfg['required_success_fraction'],
                                       first_90pct_grid_transitions=first,sustained_90pct_grid_transitions=sustain,
                                       first_right_censored=first is None,sustained_right_censored=sustain is None,
                                       individual_first_attainment_count=sum(r['first_transitions'] is not None for r in individual),
                                       individual_sustained_attainment_count=sum(r['sustained_transitions'] is not None for r in individual),
                                       max_budget=selected[-1]['transitions']))
        # Bootstrap resamples paired sampling seeds, conditional on joint stability.
        values=[]
        for seed in cfg['trial_seeds']:
            d=next(r for r in final if r['m']==m and r['seed']==seed and r['method']=='dense')
            t=next(r for r in final if r['m']==m and r['seed']==seed and r['method']=='truncated')
            if d['stable'] and t['stable']:
                values.append(t['gap']-d['gap'])
        if values:
            v=np.array(values); rng=np.random.default_rng(7716+m)
            boots=np.mean(v[rng.integers(len(v),size=(10000,len(v)))],axis=1)
            ci=np.quantile(boots,[.025,.975]).tolist()
            pairs.append(dict(m=m,paired_stable_seeds=len(v),truncated_minus_dense_mean=float(v.mean()),
                              bootstrap95_low=ci[0],bootstrap95_high=ci[1],truncated_win_fraction=float(np.mean(v<0)),
                              conditional_on_both_stable=True))
        else:pairs.append(dict(m=m,paired_stable_seeds=0,truncated_minus_dense_mean=None,bootstrap95_low=None,bootstrap95_high=None))
    for name,table in [('summary',summaries),('curve_statistics',aggregates),('sample_requirements',thresholds),
                       ('individual_attainment',sample_rows),('paired_comparison',pairs)]:
        write_csv(report_dir/(name+'.csv'),table)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130,
                         'savefig.dpi':180,'axes.grid':True,'grid.alpha':.2})
    fig,axes=plt.subplots(2,3,figsize=(14,8),constrained_layout=True)
    for ax,m in zip(axes.flat,cfg['action_dimensions']):
        for method in cfg['methods']:
            g=[r for r in aggregates if r['m']==m and r['method']==method]
            x=np.array([r['transitions'] for r in g]); mid=np.array([r['relative_gap_median'] if r['stable'] else np.nan for r in g])
            lo=np.array([r['relative_gap_q25'] if r['stable'] else np.nan for r in g]); hi=np.array([r['relative_gap_q75'] if r['stable'] else np.nan for r in g])
            ax.plot(x,mid,color=COLORS[method],label=LABELS[method]);ax.fill_between(x,lo,hi,color=COLORS[method],alpha=.18)
        ax.axhline(.1,color='black',ls='--',lw=.8);ax.set_xscale('symlog',linthresh=40000);ax.set_yscale('log')
        availability=', '.join(f"{method}: {next(r for r in summaries if r['m']==m and r['method']==method)['stable']}/20" for method in cfg['methods'])
        ax.set_title(f'm={m}, m-r={m-cfg["rank"]}\nFinal stable {availability}',fontsize=10)
        ax.set_xlabel('Cumulative primitive transitions');ax.set_ylabel('Relative optimality gap')
    axes.flat[-1].axis('off');handles,labels=axes.flat[0].get_legend_handles_labels();axes.flat[-1].legend(handles,labels,loc='center')
    fig.suptitle('Fixed effective LQR: seed median and interquartile range\nPost-pulse first-order Stein; identical assigned transition budgets',fontsize=14)
    fig.savefig(report_dir/'relative_gap_curves.png');fig.savefig(report_dir/'relative_gap_curves.pdf');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
    for method in cfg['methods']:
        g=[r for r in summaries if r['method']==method];x=np.array([r['redundant_dimensions'] for r in g])
        for ax,key in zip(axes,('gap','relative_gap')):
            y=np.array([r[key+'_median'] if r['stable'] else np.nan for r in g]);low=np.array([r[key+'_q25'] if r['stable'] else np.nan for r in g]);high=np.array([r[key+'_q75'] if r['stable'] else np.nan for r in g])
            ax.errorbar(x,y,yerr=np.array([y-low,high-y]),color=COLORS[method],marker='o',capsize=4,label=LABELS[method])
            ax.set_xlabel('Redundant action dimensions (m-r)');ax.set_ylabel('Absolute excess cost' if key=='gap' else 'Relative optimality gap')
            ax.set_xscale('log',base=2);ax.set_xticks(x,[str(v) for v in x]);ax.set_yscale('log')
    axes[0].legend();fig.suptitle(f'Fixed final budget: {final[0]["transitions"]:,} primitive transitions per trajectory\n20 paired sampling seeds; median / IQR of stable seeds')
    fig.savefig(report_dir/'fixed_budget_excess.png');fig.savefig(report_dir/'fixed_budget_excess.pdf');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    for ax,method in zip(axes,cfg['methods']):
        g=[r for r in summaries if r['method']==method];x=np.arange(len(g))
        red=np.array([r['redundant_loss_mean'] if r['stable'] else np.nan for r in g]);eff=np.array([r['effective_loss_mean'] if r['stable'] else np.nan for r in g])
        ax.bar(x,eff,color='#79a69b',label='Effective-policy loss');ax.bar(x,red,bottom=eff,color='#d2a65c',label='Redundant-action loss')
        ax.set_xticks(x,[str(r['m']) for r in g]);ax.set_xlabel('Action dimension m');ax.set_ylabel('Mean absolute excess cost');ax.set_title(LABELS[method]);ax.legend(fontsize=9)
    fig.suptitle('Offline exact loss decomposition at the final budget\nMeans of the same stable-seed set; components sum to total excess cost')
    fig.savefig(report_dir/'loss_decomposition.png');fig.savefig(report_dir/'loss_decomposition.pdf');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,4.6),constrained_layout=True)
    for method in cfg['methods']:
        g=[r for r in summaries if r['method']==method];x=np.array([r['m'] for r in g]);color=COLORS[method]
        axes[0].plot(x,[r['instability_rate'] for r in g],'-o',color=color,label=LABELS[method])
        for target,style in zip(cfg['relative_targets'],('-', '--', ':')):
            axes[1].plot(x,[r['success_'+str(target)] for r in g],style,color=color,marker='o',label=f'{method}, g <= {target}')
        axes[2].plot(x,[r['relative_gap_sd'] if r['stable'] else np.nan for r in g],'-o',color=color,label=LABELS[method])
    for ax in axes:ax.set_xlabel('Action dimension m');ax.set_xscale('log',base=2);ax.set_xticks(cfg['action_dimensions'],[str(m) for m in cfg['action_dimensions']])
    axes[0].set_ylabel('Controller instability fraction');axes[0].set_ylim(-.03,1.03);axes[0].legend(fontsize=8)
    axes[1].set_ylabel('Final success fraction, denominator 20');axes[1].set_ylim(-.03,1.03);axes[1].legend(fontsize=8)
    axes[2].set_ylabel('Across-seed SD of final relative gap');axes[2].set_yscale('log')
    fig.suptitle('Failures, fixed-output accuracy and seed variability')
    fig.savefig(report_dir/'reliability_variability.png');fig.savefig(report_dir/'reliability_variability.pdf');plt.close(fig)
    confounds=[]
    for m in cfg['action_dimensions']:
        g=[r for r in rows if r['m']==m and r['method']=='dense' and r['stage']==1]
        confounds.append(dict(m=m,expected_pulse_energy=m*cfg['sigma']**2,
                              pure_pulse_cost_variance=2*m*cfg['sigma']**4,
                              realized_pulse_energy_mean=float(np.mean([r['pulse_energy_mean'] for r in g])),
                              initial_postpulse_return_variance_mean=float(np.mean([r['postpulse_return_variance'] for r in g])),
                              initial_injection_action_cost_variance_mean=float(np.mean([r['injection_action_cost_variance'] for r in g]))))
    write_csv(report_dir/'exploration_confounds.csv',confounds)
    maximum=max(abs(r.get('decomposition_residual',0) or 0) for r in rows)
    summary=dict(trajectories=len(final),paired_tasks=expected,checkpoints=len(rows),fixed_budget=final[0]['transitions'],
                 final_summary=summaries,paired_comparison=pairs,sample_requirements=thresholds,exploration_confounds=confounds,
                 max_decomposition_residual=maximum,identity=ident,
                 caveats=['One fixed effective system; 20 sampling seeds do not establish robustness across systems.',
                          'Exploration variance per coordinate is fixed; total pulse energy and physical action cost noise grow with m.',
                          'The existing post-pulse return excludes injection-instant action cost; its noise is diagnostic only.',
                          'Failure seeds are in success denominators; costs and moments are conditional on stability.',
                          'Attainment uses observed schedule checkpoints; right-censoring is not proof a method can never reach the target.'])
    (report_dir/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    lines=['# Actuation redundancy experiment (2026-10-16)','',
           f'Completed {len(final)} trajectories, 20 paired sampling seeds per m; fixed final budget {final[0]["transitions"]:,} primitive transitions. One fixed n30/r4 effective LQR.', '',
           '| m | method | stable | median absolute excess | median relative gap | mean redundant loss | mean effective loss | instability | g<=0.1 |',
           '|---:|:---|---:|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        lines.append(f'| {r["m"]} | {r["method"]} | {r["stable"]}/20 | {fmt(r["gap_median"])} | {fmt(r["relative_gap_median"])} | {fmt(r["redundant_loss_mean"])} | {fmt(r["effective_loss_mean"])} | {r["instability_count"]}/20 | {r["success_0.1"]:.0%} |')
    lines+=['','Paired final excess-cost difference = truncated minus dense; bootstrap95% CI over jointly stable paired seeds.','',
            '| m | paired seeds | mean difference | 95% CI | truncated win fraction |','|---:|---:|---:|:---|---:|']
    for r in pairs:
        lines.append(f'| {r["m"]} | {r["paired_stable_seeds"]} | {fmt(r["truncated_minus_dense_mean"])} | [{fmt(r["bootstrap95_low"])}, {fmt(r["bootstrap95_high"])}] | {r.get("truncated_win_fraction",0):.0%} |')
    lines+=['','## Observed sample requirements','',
            '90% = at least18/20 sampling seeds; sustained means this fraction is attained at every later assigned checkpoint. Censored entries retain the full final-budget lower bound. No truth-based stopping.', '',
            '| m | method | target g | first 90% grid budget | sustained 90% grid budget |','|---:|:---|---:|---:|---:|']
    for r in thresholds:
        lines.append(f'| {r["m"]} | {r["method"]} | {r["target"]} | {fmt(r["first_90pct_grid_transitions"])} | {fmt(r["sustained_90pct_grid_transitions"])} |')
    lines+=['','## Interpretation and limitations','',
            'Use the tables and plots to assess the observed direction rather than assume monotonicity. The same initial closed loop, P0, J0, Jstar and initial gap were checked across all five action dimensions. K0 has a nonzero null component of Frobenius norm .35. Learners receive no O, true subspace, model, true value or true-gradient input.', '',
            'Offline decomposition is exact: J(K)-Jstar = tr(K_null Sigma_K K_null^T) + J(Pi K)-Jstar. Means are additive over the same stable seeds. Medians of components are not necessarily additive. All policies and exact diagnostic fixtures are saved for independent audit.', '',
            f'Maximum absolute decomposition residual: {maximum:.3g}.', '',
            'Exploration energy rises from8 to128 per pulse at sigma=1, and the pure pulse-action-cost variance rises from16 to256. B B^T is invariant, so state forcing is unchanged in distribution. The retained post-pulse estimator does not include injection-instant action cost; the increasing physical action-cost noise therefore is not itself an extra term in its labels. Observed dimension effects can reflect noisy label dimensionality and estimated subspace error, and cannot be assigned entirely to the number of redundant axes or physical cost noise. See exploration_confounds.csv for measurements.', '',
            'This experiment is conditional on one effective system and one action rotation per m. It does not establish an exponent, a uniform benefit of truncation, or a minimum end-to-end sample complexity. Seeds quantify sampling variability. Fixed-output summaries include every seed in the success/failure denominator; stable-only cost summaries must be read alongside reliability.', '',
            'Files: relative_gap_curves.png, fixed_budget_excess.png, loss_decomposition.png, reliability_variability.png (also PDF); summary.csv; sample_requirements.csv; individual_attainment.csv; paired_comparison.csv; all_checkpoints.csv; endpoints.csv; exploration_confounds.csv. Raw stage policies and final continuous states are under ../policies; provenance and frozen sources under ../frozen.']
    (report_dir/'findings.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(report=str(report_dir),trajectories=len(final),summary=summaries,paired=pairs)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();report(a.output)
