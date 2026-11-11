"""Charge interrupted sampling, preserving finite-budget and seed uncertainty."""
import argparse
import itertools
import json
import math
import os
from pathlib import Path
import shutil

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ce500_report import write_csv,wilson,boot_interval,finite


def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')


def audit(cfg):
    out=Path(cfg['output']);dest=out/'report-confirm';summary=read(dest/'summary.json')
    assert summary['audit']['status']=='PASS';seeds=cfg['confirm_seeds'];n=len(seeds)
    cases={};complete=[]
    for p in sorted(out.glob('recovery-plan-*.json')):
        plan=read(p);complete+=plan['science_complete_resource_failures']
        for c in plan['cases']:
            key=c['rank'],c['seed'];assert key not in cases;cases[key]=c
            receipt=read(out/'recovery-receipts'/f'ce-r{key[0]:03d}-s{key[1]:04d}.json')
            assert receipt['status']=='complete' and receipt['prior_rows_and_policy_hashes_preserved'] and not receipt['burn_repeated']
    complete=list({q['task']:q for q in complete}.values())
    data={};charged=[];hits={};requirements=[];rates=[];curves=[]
    ix=np.random.default_rng(cfg['bootstrap_seed']).integers(0,n,size=(cfg['bootstrap_replicates'],n))
    boot={};cut=math.ceil(.9*n)-1
    for r in cfg['ranks']:
        for method in ('dense','truncated'):
            for seed in seeds:
                raw=read(out/'raw'/f'ce-r{r:03d}-s{seed:04d}.json');c=cases.get((r,seed))
                rows=[dict(q) for q in raw['records'] if q['method']==method]
                for q in rows:
                    extra=c['discarded_uncommitted_transition_upper_bound'] if c and q['ols_samples']>c['done'] else 0
                    q['executed_transitions_lower']=q['transitions'];q['executed_transitions_upper']=q['transitions']+extra
                data[r,method,seed]=rows;charged+=rows
            budgets=sorted({q[k] for seed in seeds for q in data[r,method,seed] for k in ('executed_transitions_lower','executed_transitions_upper')})
            for target in cfg['relative_targets']:
                costs=[]
                for seed in seeds:
                    rows=data[r,method,seed];ok=[q['stable'] and q['gap'] is not None and q['gap']<=target for q in rows]
                    # This permits an exact componentwise bound, rather than assuming nonmonotone policies can be freely retained.
                    assert all(not a or b for a,b in zip(ok,ok[1:])),('Nonmonotone target indicators need full availability sweep',r,seed,method,target)
                    first=next((q for q,yes in zip(rows,ok) if yes),None)
                    costs.append([first['executed_transitions_lower'],first['executed_transitions_upper']] if first else [np.inf,np.inf])
                arr=np.array(costs);hits[r,method,target]=arr
                lo,hi=np.sort(arr,axis=0)[cut];bb=np.sort(arr[ix],axis=1)[:,cut,:];boot[r,method,target]=bb
                ci0,ci1=boot_interval(bb[:,0]),boot_interval(bb[:,1])
                nominal=next(q for q in summary['requirements'] if (q['rank'],q['method'],q['relative_target'])==(r,method,target))
                assert finite(lo)==nominal['N_hat_90']
                endpoint=max(q['executed_transitions_upper'] for seed in seeds for q in data[r,method,seed])
                observed_budget=hi if np.isfinite(hi) else endpoint
                wins=int(np.count_nonzero(arr[:,1]<=observed_budget));wl,wh=wilson(wins,n)
                requirement=dict(rank=r,method=method,relative_target=target,seeds=n,N90_execution_lower=finite(lo),N90_execution_upper=finite(hi),
                    N90_committed=nominal['N_hat_90'],status='reached' if np.isfinite(hi) else 'not reached',
                    bootstrap95_execution_lower=ci0['low'],bootstrap95_execution_upper=ci1['high'],
                    execution_uncertainty_changes_N90=bool(lo!=hi),max_executed_budget_upper=endpoint,
                    successes_at_execution_upper=wins,success_Wilson95_lower=wl,success_Wilson95_upper=wh,
                    nominal_successes=nominal['successes'],nominal_success_ci95_low=nominal['success_ci95_low'],nominal_success_ci95_high=nominal['success_ci95_high'],
                    instabilities=nominal['instabilities'],instability_ci95_low=nominal['instability_ci95_low'],instability_ci95_high=nominal['instability_ci95_high'])
                requirements.append(requirement)
                for b in budgets:
                    w0=int(np.count_nonzero(arr[:,0]<=b));w1=int(np.count_nonzero(arr[:,1]<=b));cl,ch=wilson(w1,n)
                    rates.append(dict(rank=r,method=method,relative_target=target,transitions=b,seeds=n,
                        success_rate_lower=w1/n,success_rate_upper=w0/n,successes_at_maximum_lost_cost=w1,Wilson95_lower=cl,Wilson95_upper=ch))
            for b in budgets:
                vals=[]
                for field in ('executed_transitions_lower','executed_transitions_upper'):
                    vv=[]
                    for seed in seeds:
                        available=[q for q in data[r,method,seed] if q[field]<=b]
                        q=available[-1] if available else dict(stable=True,gap=1.)
                        vv.append(q['gap'] if q['stable'] and q['gap'] is not None else np.inf)
                    vals.append(vv)
                curves.append(dict(rank=r,method=method,transitions=b,median_zero_lost=finite(np.median(vals[0])),
                    median_max_lost=finite(np.median(vals[1])),q25_max_lost=finite(np.quantile(vals[1],.25)),q75_max_lost=finite(np.quantile(vals[1],.75))))
    contrasts=[];fits=[];adjacent=[]
    for target in cfg['relative_targets']:
        full=next(q for q in requirements if (q['rank'],q['method'],q['relative_target'])==(cfg['n'],'dense',target))
        gains=[]
        for r in cfg['ranks']:
            q=next(q for q in requirements if (q['rank'],q['method'],q['relative_target'])==(r,'truncated',target))
            fl,fh=full['N90_execution_lower'],full['N90_execution_upper'];ll,lh=q['N90_execution_lower'],q['N90_execution_upper']
            numerator=boot[cfg['n'],'dense',target];denominator=boot[r,'truncated',target]
            with np.errstate(invalid='ignore',divide='ignore'):
                bs0=numerator[:,0]/denominator[:,1];bs1=numerator[:,1]/denominator[:,0]
            finite_boot=bool(np.isfinite(bs0).all() and np.isfinite(bs1).all())
            ci0,ci1=(boot_interval(bs0),boot_interval(bs1)) if finite_boot else ({'low':None},{'high':None})
            row=dict(rank=r,relative_target=target,full_dense_N90_lower=fl,full_dense_N90_upper=fh,truncated_N90_lower=ll,truncated_N90_upper=lh,
                sample_saving_lower=fl/lh if fl and lh else None,sample_saving_upper=fh/ll if fh and ll else None,
                bootstrap95_saving_lower=ci0['low'],bootstrap95_saving_upper=ci1['high'])
            contrasts.append(row)
            if r!=cfg['n']:gains.append(row)
        x=np.log([cfg['n']/q['rank'] for q in gains]);slopes=[]
        if all(q['sample_saving_lower'] for q in gains):
            for bits in itertools.product((0,1),repeat=len(gains)):
                y=np.log([q['sample_saving_upper' if b else 'sample_saving_lower'] for q,b in zip(gains,bits)])
                slopes.append(float(np.polyfit(x,y,1)[0]))
            fits.append(dict(relative_target=target,ranks=[2,4,8,32],power_alpha_execution_lower=min(slopes),power_alpha_execution_upper=max(slopes)))
            for a,b in zip(gains,gains[1:]):
                adjacent.append(dict(relative_target=target,low_rank=a['rank'],high_rank=b['rank'],
                    gain_ratio_lower=a['sample_saving_lower']/b['sample_saving_upper'],gain_ratio_upper=a['sample_saving_upper']/b['sample_saving_lower'],inverse_rank_prediction=b['rank']/a['rank']))
    lost=sum(c['discarded_uncommitted_transition_upper_bound'] for c in cases.values())
    committed=summary['audit']['physical_transitions'];other=read(out/'preflight.json')['diagnostic_primitive_transitions']+read(out/'report-pilot/audit.json')['physical_transitions']
    result=dict(status='PASS',case_count=len(cases),science_complete_resource_failures=complete,unique_resource_failed_scientific_tasks=len(cases)+len(complete),
        discarded_sampling_transitions_lower=0,discarded_sampling_transitions_upper=lost,discarded_count_exact=False,
        formal_committed_transitions=committed,formal_executed_transitions_lower=committed,formal_executed_transitions_upper=committed+lost,
        campaign_executed_transitions_lower=committed+other,campaign_executed_transitions_upper=committed+other+lost,
        requirements=requirements,low_rank_vs_full_rank=contrasts,descriptive_gain_fits=fits,adjacent_gain_ratios=adjacent,
        all_target_success_indicators_monotone=True,resource_failures_are_not_controller_instabilities=True,
        rule='Each trajectory includes burn once. Prefixes after interruption pay an unknown discarded-work cost in [0,next_budget-checkpoint_done]. N90 endpoints and bootstrap envelope bound every independent per-seed discarded-work value. All failed scheduler attempts retained.')
    for name,rows in [('executed_sample_complexity',requirements),('executed_low_rank_vs_full_rank',contrasts),('executed_success_by_budget',rates),
                      ('executed_gap_convergence',curves),('charged_checkpoints',charged),('executed_adjacent_gain_ratios',adjacent)]:write_csv(dest/(name+'.csv'),rows)
    save(dest/'execution_cost_audit.json',result)
    summary['execution_cost_accounting']=result;summary['original_requirements_budget_definition']='Committed OLS prefix plus burn; execution-cost intervals are in execution_cost_accounting.'
    save(dest/'summary.json',summary)
    for stem in ('sample_saving_vs_rank','sample_complexity_vs_rank','success_probability_vs_budget','absolute_relative_gap_convergence'):
        for ext in ('png','svg'):
            source=dest/(stem+'.'+ext);backup=dest/(stem+'_committed_prefix.'+ext)
            if source.exists() and not backup.exists():shutil.copyfile(source,backup)
    plt.rcParams.update({'axes.grid':True,'grid.alpha':.2,'font.size':10})
    for saving,stem in [(True,'sample_saving_vs_rank'),(False,'sample_complexity_vs_rank')]:
        fig,axes=plt.subplots(1,2,figsize=(11,4.4),layout='constrained')
        for ax,target in zip(axes,cfg['relative_targets']):
            if saving:
                qq=[q for q in contrasts if q['relative_target']==target and q['rank']!=cfg['n']]
                for q in qq:
                    low,high=q['sample_saving_lower'],q['sample_saving_upper'];mid=(low+high)/2
                    ax.errorbar(q['rank'],mid,yerr=[[mid-low],[high-mid]],fmt='o',color='#1476a3',capsize=4)
                rr=np.geomspace(2,32,100);ax.plot(rr,qq[0]['sample_saving_lower']*2/rr,'--',label='1/r reference, rank2 anchored')
                ax.plot(rr,cfg['n']/rr,':',color='.5',label='500/r reference, unit coefficient')
                ax.set(ylabel='Saving: full500 dense / low-rank truncated',xlim=(1.8,36),xticks=[2,4,8,32]);ax.set_xticklabels([2,4,8,32]);ax.legend(fontsize=8)
            else:
                for method in ('dense','truncated'):
                    qq=[q for q in requirements if q['relative_target']==target and q['method']==method and q['N90_execution_upper']]
                    xx=[q['rank'] for q in qq];yy=[q['N90_execution_upper'] for q in qq]
                    ax.plot(xx,yy,'o-',label=method)
                    for q in qq:ax.vlines(q['rank'],q['N90_execution_lower'],q['N90_execution_upper'])
                    censored=[q for q in requirements if q['relative_target']==target and q['method']==method and q['N90_execution_upper'] is None]
                    for q in censored:ax.plot(q['rank'],q['max_executed_budget_upper'],'^',color='.5');ax.annotate('NR',(q['rank'],q['max_executed_budget_upper']),xytext=(3,5),textcoords='offset points',fontsize=8)
                ax.set(ylabel='Primitive transitions for empirical90% success');ax.legend()
            ax.set(xscale='log',yscale='log',xlabel='Actuation rank',title=f'Relative target {target:g}')
        fig.suptitle('Equal controlled-mode difficulty | initial gap1 | bars: lost-work cost bounds')
        for ext in ('png','svg'):fig.savefig(dest/(stem+'.'+ext),dpi=180,facecolor='white')
        plt.close(fig)
    fig,axes=plt.subplots(2,5,figsize=(17,6),sharey=True,layout='constrained')
    for i,target in enumerate(cfg['relative_targets']):
        for ax,r in zip(axes[i],cfg['ranks']):
            for method in ('dense','truncated'):
                rows=[q for q in rates if (q['rank'],q['method'],q['relative_target'])==(r,method,target)]
                x=[q['transitions'] for q in rows];low=[q['success_rate_lower'] for q in rows];high=[q['success_rate_upper'] for q in rows]
                ax.step(x,low,where='post',label=method);ax.fill_between(x,low,high,step='post',alpha=.2)
            ax.axhline(.9,color='.5',ls=':');ax.set(xscale='log',xlabel='Executed transitions',title=f'rank{r}, target{target:g}',ylim=(-.02,1.02))
    axes[0,0].set_ylabel('Success probability');axes[1,-1].legend();fig.suptitle('30seeds | shaded region: unknown lost-sampling cost')
    for ext in ('png','svg'):fig.savefig(dest/('success_probability_vs_budget.'+ext),dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(1,5,figsize=(17,3.8),sharey=True,layout='constrained')
    for ax,r in zip(axes,cfg['ranks']):
        for method in ('dense','truncated'):
            rows=[q for q in curves if (q['rank'],q['method'])==(r,method)];x=[q['transitions'] for q in rows]
            ax.plot(x,[q['median_max_lost'] for q in rows],label=method)
            ax.fill_between(x,[q['q25_max_lost'] for q in rows],[q['q75_max_lost'] for q in rows],alpha=.12)
            ax.fill_between(x,[q['median_zero_lost'] for q in rows],[q['median_max_lost'] for q in rows],alpha=.2,color='orange')
        for t in cfg['relative_targets']:ax.axhline(t,color='.5',ls=':')
        ax.set(xscale='log',yscale='log',xlabel='Executed transitions',title=f'rank{r}')
    axes[0].set_ylabel('Absolute / relative optimality gap');axes[-1].legend();fig.suptitle('Median/IQR, maximum lost-work cost | orange: median execution-cost envelope')
    for ext in ('png','svg'):fig.savefig(dest/('absolute_relative_gap_convergence.'+ext),dpi=180)
    plt.close(fig)
    rows=''.join(f"<tr><td>{q['rank']}</td><td>{q['relative_target']}</td><td>{q['truncated_N90_lower']:,}–{q['truncated_N90_upper']:,}</td><td>{q['sample_saving_lower']:.3f}–{q['sample_saving_upper']:.3f}</td></tr>" for q in contrasts)
    html=dest/'results.html';content=html.read_text();notice=f'''<h2>执行预算核算（主结果）</h2><p>{len(cases)} 个任务从断点补完；保留全部失败记录。额外未提交采样为0–{lost:,} transitions。
以下区间只表示采样成本不确定性；统计95%区间另见 executed_low_rank_vs_full_rank.csv。下方原表为已提交前缀预算。</p>
<table><tr><th>Rank</th><th>Target</th><th>Truncated executed N90区间</th><th>相对full500省样本倍数</th></tr>{rows}</table>
<p><a href="execution_cost_audit.json">执行成本与区间核查</a> · <a href="executed_sample_complexity.csv">含统计区间的样本需求</a></p>'''
    content=content.replace('<table><tr><th>Rank</th>',notice+'<h2>已提交前缀预算（原始记录）</h2><table><tr><th>Rank</th>',1);html.write_text(content,encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='requirements'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args();assert os.environ.get('SLURM_JOB_ID');audit(read(a.manifest))
