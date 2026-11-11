"""Compare completed equal-mode CE gains with the earlier one-unstable-mode family.

Saved-data postprocessing only. Primary conclusions remain sample thresholds.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import ScalarFormatter,NullFormatter


def read_csv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for q in iter(lambda:f.read(8*1024*1024),b''):h.update(q)
    return h.hexdigest()


def write_csv(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def n90(success,budgets):
    hit=success.mean(axis=-2)>=.9-1e-12
    return np.where(hit.any(axis=-1),np.array(budgets)[hit.argmax(axis=-1)],np.inf)


def main():
    p=argparse.ArgumentParser();p.add_argument('--new-root',type=Path,required=True)
    p.add_argument('--old-review',type=Path,required=True);p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--old-rank4',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    new_report=a.new_root/'report-confirm';summary=json.loads((new_report/'summary.json').read_text(encoding='utf-8'))
    assert summary['status']=='complete' and summary['audit']['paired_tasks']==150
    execution=json.loads((new_report/'execution_cost_audit.json').read_text(encoding='utf-8'))
    assert execution['status']=='PASS'
    charged=read_csv(new_report/'charged_checkpoints.csv')
    new=read_csv(new_report/'sample_complexity.csv');old=read_csv(a.old_review/'sample_complexity.csv')
    raw=read_csv(new_report/'all_checkpoints.csv');ranks=[2,4,8,32];targets=[.1,.05]
    inputs=[new_report/n for n in ('summary.json','sample_complexity.csv','all_checkpoints.csv','policy_spectral_diagnostics.csv')]
    inputs.extend([a.old_review/'sample_complexity.csv',new_report/'execution_cost_audit.json',new_report/'charged_checkpoints.csv',new_report/'executed_success_by_budget.csv'])
    sources={str(q):sha(q) for q in inputs};records=[];fits=[];adjacent=[]
    recovery_checks=[]
    for planpath in sorted(a.new_root.glob('recovery-plan-*.json')):
        rp=json.loads(planpath.read_text(encoding='utf-8'));sources[str(planpath)]=sha(planpath)
        for case in rp['cases']:
            stem=f"ce-r{case['rank']:03d}-s{case['seed']:04d}"
            receiptpath=a.new_root/'recovery-receipts'/(stem+'.json')
            receipt=json.loads(receiptpath.read_text(encoding='utf-8'))
            backup=a.new_root/receipt['backup_checkpoint'];assert sha(backup)==case['checkpoint_sha256']
            with np.load(backup,allow_pickle=False) as arr:metadata=json.loads(str(arr['meta']))
            assert metadata['done']==case['done'] and metadata['rows']==receipt['original_rows']
            assert all(metadata[k]==receipt['initial_rng_states'][k] for k in ('pulse_rng','noise_rng'))
            finalpath=a.new_root/'raw'/(stem+'.json');final=json.loads(finalpath.read_text(encoding='utf-8'))
            assert final['records'][:len(metadata['rows'])]==metadata['rows']
            assert receipt['new_committed_transitions']==final['budgets'][-1]-case['done'] and not receipt['burn_repeated']
            sources[str(receiptpath)]=sha(receiptpath);sources[str(backup)]=case['checkpoint_sha256']
            recovery_checks.append(dict(rank=case['rank'],seed=case['seed'],status='PASS',original_checkpoint_and_RNG_verified=True,
                original_rows_preserved=True,new_transitions=receipt['new_committed_transitions'],
                discarded_transition_upper=case['discarded_uncommitted_transition_upper_bound']))
    assert len(recovery_checks)==execution['case_count']
    assert sum(q['discarded_transition_upper'] for q in recovery_checks)==execution['discarded_sampling_transitions_upper']
    write_csv(a.output/'independent_recovery_audit.csv',recovery_checks)
    indices=np.random.default_rng(2026102022).integers(0,30,size=(2000,30))
    boot={}
    for rank in ranks+[500]:
        rr=[q for q in raw if int(q['rank'])==rank and q['method']==('dense' if rank==500 else 'truncated')]
        budgets=sorted({int(q['transitions']) for q in rr})
        gaps=np.array([[float(next(q for q in rr if int(q['seed'])==s and int(q['transitions'])==b)['gap'])
                        if next(q for q in rr if int(q['seed'])==s and int(q['transitions'])==b)['stable']=='True' else np.inf
                        for b in budgets] for s in range(200,230)])
        for t in targets:
            success=gaps<=t;point=float(n90(success,budgets));boot[rank,t]=n90(success[indices],budgets)
            reported=next(q for q in new if int(q['rank'])==rank and q['method']==('dense' if rank==500 else 'truncated') and float(q['relative_target'])==t)
            assert point==float(reported['N_hat_90']) if reported['N_hat_90'] else np.isinf(point)
            upper_costs=[]
            for seed in range(200,230):
                qq=[q for q in charged if int(q['rank'])==rank and int(q['seed'])==seed and q['method']==('dense' if rank==500 else 'truncated')]
                hh=[int(q['executed_transitions_upper']) for q in qq if q['stable']=='True' and float(q['gap'])<=t]
                upper_costs.append(min(hh) if hh else np.inf)
            boot[rank,t]=np.sort(np.array(upper_costs)[indices],axis=1)[:,26]
    for target in targets:
        for label,table in (('old',old),('equal_modes',new)):
            base=next(q for q in table if int(q['rank'])==500 and q['method']=='dense' and float(q['relative_target'])==target)
            full=float(base['N_hat_90']) if base['N_hat_90'] else None
            if label=='equal_modes':
                er=next(q for q in execution['requirements'] if q['rank']==500 and q['method']=='dense' and q['relative_target']==target)
                full=er['N90_execution_upper']
            for rank in ranks+[500]:
                q=next(q for q in table if int(q['rank'])==rank and q['method']=='truncated' and float(q['relative_target'])==target)
                value=float(q['N_hat_90']) if q['N_hat_90'] else None
                upper_gain=None;value_lower=value
                if label=='equal_modes':
                    eq=next(z for z in execution['requirements'] if z['rank']==rank and z['method']=='truncated' and z['relative_target']==target)
                    value_lower,value=eq['N90_execution_lower'],eq['N90_execution_upper']
                    eg=next(z for z in execution['low_rank_vs_full_rank'] if z['rank']==rank and z['relative_target']==target)
                    upper_gain=eg['sample_saving_upper']
                lo=hi=None
                if label=='equal_modes' and np.isfinite(boot[rank,target]).all() and np.isfinite(boot[500,target]).all():
                    lo,hi=np.quantile(boot[500,target]/boot[rank,target],[.025,.975],method='nearest')
                    lo,hi=eg['bootstrap95_saving_lower'],eg['bootstrap95_saving_upper']
                records.append(dict(family=label,relative_target=target,rank=rank,full_dense_N=full,
                    truncated_N=value,gain=full/value if full and value else None,
                    truncated_N_lower=value_lower,gain_execution_upper=upper_gain,
                    gain_bootstrap95_low=float(lo) if lo is not None else None,
                    gain_bootstrap95_high=float(hi) if hi is not None else None,
                    successes=int(q['successes']),success_ci95_low=float(q['success_ci95_low']),
                    success_ci95_high=float(q['success_ci95_high']),previous_tested_committed_budget=q['previous_tested_budget']))
            group=[q for q in records if q['family']==label and q['relative_target']==target and q['rank'] in ranks]
            if all(q['gain'] is not None for q in group):
                x=np.array([500/q['rank'] for q in group]);y=np.array([q['gain'] for q in group])
                alpha,lc=np.polyfit(np.log(x),np.log(y),1);ci_alpha=[None,None]
                if label=='equal_modes':
                    valid=np.logical_and.reduce([np.isfinite(boot[r,target]) for r in ranks+[500]])
                    yy=np.log(np.array([boot[500,target][valid]/boot[r,target][valid] for r in ranks]))
                    xx=np.log(x)-np.mean(np.log(x))
                    alphas=(xx[:,None]*yy).sum(axis=0)/(xx@xx)
                    ci_alpha=np.quantile(alphas,[.025,.975]).tolist() if valid.all() else [None,None]
                fits.append(dict(family=label,relative_target=target,alpha=float(alpha),c=float(np.exp(lc)),
                    zero_intercept_c=float(x@y/(x@x)),bootstrap_alpha95_low=ci_alpha[0],bootstrap_alpha95_high=ci_alpha[1]))
                for lower,upper in zip(group[:-1],group[1:]):
                    adjacent.append(dict(family=label,relative_target=target,low_rank=lower['rank'],high_rank=upper['rank'],
                        observed_gain_ratio=lower['gain']/upper['gain'],expected_ratio=upper['rank']/lower['rank']))
    write_csv(a.output/'sample_gain_comparison.csv',records)
    prefactors=[dict(rank=q['rank'],relative_target=q['relative_target'],
        N_epsilon_over_r_n_plus_m_lower=q['truncated_N_lower']*q['relative_target']/(q['rank']*1000),
        N_epsilon_over_r_n_plus_m_upper=q['truncated_N']*q['relative_target']/(q['rank']*1000))
        for q in records if q['family']=='equal_modes' and q['truncated_N']]
    write_csv(a.output/'rank_normalized_sample_prefactors.csv',prefactors)
    if fits:write_csv(a.output/'gain_scaling_fits.csv',fits)
    if adjacent:write_csv(a.output/'adjacent_gain_comparison.csv',adjacent)
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,2,figsize=(11,4.7),layout='constrained')
    for ax,target in zip(axes,targets):
        for label,color,style in (('old','#8c9299','s--'),('equal_modes','#176b9c','o-')):
            group=[q for q in records if q['family']==label and q['relative_target']==target and q['rank'] in ranks]
            y=[q['gain'] or np.nan for q in group]
            ax.plot(ranks,y,style,color=color,label='Original: one unstable mode' if label=='old' else 'Equal unstable controlled modes')
            if label=='equal_modes':
                for q in group:
                    if q['gain'] and q['gain_execution_upper']:ax.vlines(q['rank'],q['gain'],q['gain_execution_upper'],color=color,lw=3)
                    if q['gain'] and q['gain_bootstrap95_low'] is not None:
                        ax.errorbar(q['rank'],q['gain'],yerr=[[q['gain']-q['gain_bootstrap95_low']],[q['gain_bootstrap95_high']-q['gain']]],fmt='none',ecolor=color,capsize=4,lw=1)
            if label=='equal_modes' and group[0]['gain']:
                rr=np.geomspace(2,32,200);ax.plot(rr,group[0]['gain']*2/rr,':',color='#db8b20',label='1/r reference anchored at rank 2')
                ax.plot(rr,500/rr,':',color='.4',label='500/r reference, unit coefficient')
                for q in group:
                    if q['gain']:ax.annotate(f"{q['gain']:.2f}x",(q['rank'],q['gain']),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
        ax.set(xscale='log',yscale='log',xlabel='Actuation rank r',ylabel='Sample-saving factor: full dense / rank-r trunc',title=f'Relative target {target:g}',xticks=ranks)
        ax.xaxis.set_major_formatter(ScalarFormatter());ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('CE500 | matched initial gap = 1 | 30 formal seeds per family')
    for ext in ('png','svg'):fig.savefig(a.output/('gain_scaling_comparison.'+ext),dpi=180)
    plt.close(fig)
    rates=read_csv(new_report/'executed_success_by_budget.csv')
    fig,axes=plt.subplots(2,5,figsize=(17,6),sharey=True,layout='constrained')
    colors={'dense':'#ba4737','truncated':'#1476a3'}
    for i,target in enumerate(targets):
        for ax,rank in zip(axes[i],ranks+[500]):
            for method,color in colors.items():
                qq=[q for q in rates if int(q['rank'])==rank and q['method']==method and float(q['relative_target'])==target]
                xx=[int(q['transitions']) for q in qq];yy=[float(q['success_rate_lower']) for q in qq]
                ax.step(xx,yy,where='post',label=method,color=color)
                ax.fill_between(xx,[float(q['Wilson95_lower']) for q in qq],[float(q['Wilson95_upper']) for q in qq],step='post',alpha=.12,color=color)
                ax.fill_between(xx,yy,[float(q['success_rate_upper']) for q in qq],step='post',alpha=.3,color='orange')
            ax.axhline(.9,color='.5',ls=':');ax.set(xscale='log',ylim=(-.02,1.02),xlabel='Executed transitions',title=f'rank{rank}, target{target:g}')
            ticks=np.geomspace(min(xx),max(xx),3)
            ax.set_xticks(ticks)
            ax.set_xticklabels([f'{v/1e6:.2g}M' if v>=1e6 else f'{v/1000:.0f}k' for v in ticks],fontsize=9)
            ax.xaxis.set_minor_formatter(NullFormatter())
    axes[0,0].set_ylabel('Success probability');axes[1,0].set_ylabel('Success probability');axes[1,-1].legend(fontsize=8)
    fig.suptitle('30seeds | bands: Wilson95% at maximum lost cost | orange: unknown sampling-cost range')
    for ext in ('png','svg'):fig.savefig(a.output/('executed_success_with_CI.'+ext),dpi=180)
    plt.close(fig)
    # Direct old/new mode-energy diagnostic; no new model or policy solves.
    mode_rows=[];new_diag=read_csv(new_report/'policy_spectral_diagnostics.csv')
    for q in new_diag:
        if q['method']=='truncated' and int(q['rank']) in ranks:
            mode_rows.append(dict(family='equal_modes',rank=int(q['rank']),seed=int(q['seed']),
                first_active_over_average=float(q['first_active_over_average']),spectral_shape=float(q['spectral_shape']),
                deltaK_op2=float(q['deltaK_op2']),deltaK_fro2_per_rank=float(q['deltaK_fro2'])/int(q['rank']),
                gap_per_rank=float(q['gap'])/int(q['rank'])))
    for rank in ranks:
        root=a.old_rank4 if rank==4 else a.old_root
        sp=root/'systems'/f'r{rank:03d}.npz';sources[str(sp)]=sha(sp)
        verification=json.loads((root/'verification.json').read_text(encoding='utf-8'))
        assert sha(sp)==verification['system_hashes'][str(rank)]
        with np.load(sp,allow_pickle=False) as d:v=d['V'];ks=d['Kstar']
        for seed in range(200,230):
            rp=root/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json';r=json.loads(rp.read_text(encoding='utf-8'));sources[str(rp)]=sha(rp)
            q=next(q for q in r['records'] if q['method']=='truncated' and q['transitions']==131328)
            kp=root/q['policy_file'];assert sha(kp)==q['policy_sha256'];sources[str(kp)]=q['policy_sha256']
            with np.load(kp,allow_pickle=False) as d:delta=d['truncated']-ks
            energies=np.sum((v[:,:rank].T@delta)**2,axis=1)
            ds=np.linalg.svd(delta,compute_uv=False)
            mode_rows.append(dict(family='old',rank=rank,seed=seed,first_active_over_average=float(energies[0]/energies.mean()),
                spectral_shape=float(np.sum(delta**2)/(rank*ds[0]**2)),deltaK_op2=float(ds[0]**2),
                deltaK_fro2_per_rank=float(np.sum(delta**2)/rank),gap_per_rank=float(q['gap'])/rank))
    write_csv(a.output/'mode_energy_diagnostics.csv',mode_rows)
    mode_summary=[]
    for label in ('old','equal_modes'):
        for rank in ranks:
            q=[r for r in mode_rows if r['family']==label and r['rank']==rank]
            mode_summary.append(dict(family=label,rank=rank,seeds=len(q),
                median_first_active_over_average=float(np.median([r['first_active_over_average'] for r in q])),
                median_spectral_shape=float(np.median([r['spectral_shape'] for r in q])),
                median_deltaK_op2=float(np.median([r['deltaK_op2'] for r in q])),
                median_deltaK_fro2_per_rank=float(np.median([r['deltaK_fro2_per_rank'] for r in q])),
                median_gap_per_rank=float(np.median([r['gap_per_rank'] for r in q]))))
    write_csv(a.output/'mode_energy_summary.csv',mode_summary)
    fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
    for ax,key,title in zip(axes,('median_deltaK_fro2_per_rank','median_gap_per_rank'),
                            ('Policy Frobenius error squared / rank','Control optimality gap / rank')):
        for label,color,style in (('old','#8c9299','s--'),('equal_modes','#176b9c','o-')):
            group=[q for q in mode_summary if q['family']==label]
            ax.plot(ranks,[q[key] for q in group],style,color=color,
                    label='Original: one unstable mode' if label=='old' else 'Equal unstable controlled modes')
        ax.set(xscale='log',xlabel='Actuation rank',title=title,xticks=ranks)
        ax.xaxis.set_major_formatter(ScalarFormatter());ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Auxiliary diagnostic at 131,072 committed OLS samples +256 burn | medians over30seeds')
    for ext in ('png','svg'):fig.savefig(a.output/('rank_normalized_error_diagnostic.'+ext),dpi=180)
    plt.close(fig)
    result=dict(status='complete',primary_metric='Same-gap empirical N90 saving at maximum discarded-work cost; vertical ranges cover unknown executed-transition costs',
        records=records,fits=fits,adjacent_gain_ratios=adjacent,mode_diagnostics=mode_summary,
        executed_gain_fit_bounds=execution['descriptive_gain_fits'],executed_adjacent_gain_bounds=execution['adjacent_gain_ratios'],
        independently_verified_checkpoint_recoveries=len(recovery_checks),
        empirical_sample_prefactors=prefactors,
        caveats=['New A varies with rank; the stable complement is also simplified. This is not a single-factor causal proof.',
                 'Old/new families use different sampling routes; pairing is within each family across ranks, not across families.',
                 'Bootstrap intervals are conditional on one system and the tested grid; they do not remove budget-grid uncertainty.',
                 'Old/new evaluation grids differ; gain exponents are descriptive comparisons, not matched-grid causal tests.',
                 'Equal per-mode difficulty does not require an unchanged operator/Frobenius spectral-shape ratio: operator error and shape can compensate.',
                 'Auxiliary mode-energy diagnostics do not replace same-final-gap sample complexity.'],source_sha256=sources)
    (a.output/'analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    rows=''.join(f"<tr><td>{q['rank']}</td><td>{q['relative_target']}</td><td>{q['truncated_N'] or 'not reached'}</td><td>{q['full_dense_N'] or 'not reached'}</td><td>{format(q['gain'],'.3f') if q['gain'] else 'not reached'}</td></tr>" for q in records if q['family']=='equal_modes')
    page=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>CE500 等模态：样本收益对照</title>
<style>body{{font:16px/1.6 system-ui;max-width:1150px;margin:30px auto;padding:0 20px}}img{{max-width:100%}}td,th{{border:1px solid #ccd4dd;padding:7px 12px}}table{{border-collapse:collapse}}</style>
<h1>CE500：复制同样困难的模态后，截断收益如何缩放</h1>
<p>固定初始 gap=1，targets=.1/.05；每个rank30个正式seeds。新系统每个受控模态均为1.2，未受控模态0.45，
B_r=U_rV_rᵀ。完整trajectory联合OLS，同数据dense/truncated，仅截断Bhat。预算包含256 burn-in。</p>
<p>主表采用未提交采样的最大成本，图中竖线给出执行成本上下界。全部失败与断点恢复均保留；bootstrap统计区间采用最大成本情形，完整成本包络见原报告。</p>
<table><tr><th>Rank</th><th>Target</th><th>Trunc N90</th><th>Full500 dense N90</th><th>省样本倍数</th></tr>{rows}</table>
<img src="gain_scaling_comparison.png" alt="同一最终gap下的样本收益">
<p>收益图细误差线为配对bootstrap95%加中断成本包络，粗竖线为中断成本区间；参考线同时显示500/r和rank2对齐的1/r。</p>
<img src="executed_success_with_CI.png" alt="成功率与Wilson95%置信区间">
<img src="rank_normalized_error_diagnostic.png" alt="辅助诊断：每个rank的误差贡献">
<p>描述性拟合：{json.dumps(fits,ensure_ascii=False)}。</p>
<p>相邻收益比：{json.dumps(adjacent,ensure_ascii=False)}。</p>
<p>新系统的A随rank改变，稳定补空间也被简化；结果可检验等模态构造下是否出现近似1/r，不能单独证明旧结果只由一个不稳定模态造成。
固定预算的误差谱/模态诊断仅用于解释，主结论始终来自同一最终gap的实测N90。</p>
<p>新旧预算网格不同（新实验关键区间约1.08倍），指数对照仅作描述；bootstrap区间不包含网格分辨率误差。</p>
<p>新实验低rank的实测N×epsilon/[r(n+m)]约1.05–1.22，full500约0.225。因此低rank之间接近线性，并不等于与full比较的绝对收益恰好500/r。
这只显示实测系数仍不同，不能单凭这个系数诊断是A误差、B误差还是探索协方差造成。</p>
<p>成功率区间为Wilson95%；30/30的下界约0.886，并不是置信下界达到0.9。点bootstrap不消除预算网格分辨率。</p>
<p><a href="../report-confirm/results.html">完整成功率、收敛曲线及审计</a> · <a href="analysis.json">全部对照与来源哈希</a> ·
<a href="sample_gain_comparison.csv">样本收益CSV</a> · <a href="mode_energy_summary.csv">辅助模态诊断</a></p></html>'''
    (a.output/'results.html').write_text(page,encoding='utf-8')
    shutil.copy2(__file__,a.output/Path(__file__).name)
    (a.output/'manifest.sha256.json').write_text(json.dumps({p.name:sha(p) for p in a.output.iterdir() if p.is_file() and p.name!='manifest.sha256.json'},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='complete',fits=fits,adjacent=adjacent,mode_summary=mode_summary),indent=2))


if __name__=='__main__':main()
