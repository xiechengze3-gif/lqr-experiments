"""Failure-inclusive reporting for the frozen three-group experiment."""
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from manuscript_three_groups import (CFG,OUT,identity,provenance,require_compute,
    schedule,sha,specs,atomic_json)


def write_csv(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(rows)


def median(values):
    y=sorted(values);n=len(y)
    if not n:return None
    if not np.isfinite(y[n//2]):return None
    return float(y[n//2]) if n%2 else float((y[n//2-1]+y[n//2])/2)


def group_stats(key,rows):
    good=[r for r in rows if r['stable'] and r.get('gap') is not None and np.isfinite(r['gap'])]
    gaps=[r['gap'] for r in good]
    result=dict(**key,count=len(rows),stable_count=len(good),stable_rate=len(good)/len(rows),
        failure_inclusive_gap_median=median([r['gap'] if r in good else float('inf') for r in rows]),
        stable_gap_median=median(gaps),stable_gap_q25=float(np.quantile(gaps,.25)) if gaps else None,
        stable_gap_q75=float(np.quantile(gaps,.75)) if gaps else None,
        success_gap_01=sum(g<=.1 for g in gaps)/len(rows),success_gap_001=sum(g<=.01 for g in gaps)/len(rows))
    for source,dest in [('redundant_cost','redundant_median'),('k','rank_median'),('retained_rank','retained_rank_median')]:
        values=[r[source] for r in good if r.get(source) is not None]
        result[dest]=median(values)
    return result


def paired_bootstrap(rows,reference,alternative):
    by={}
    for row in rows:
        if row['mode'] in [reference,alternative]:by.setdefault((row['system'],row['trial']),{})[row['mode']]=row
    valid=[]
    for (system,trial),pair in by.items():
        if len(pair)==2 and all(r['stable'] and r.get('gap',0)>0 for r in pair.values()):
            valid.append((system,trial,pair[reference]['gap']/pair[alternative]['gap']))
    if not valid:return dict(paired_count=0,ratio=None,ratio_ci_low=None,ratio_ci_high=None)
    systems=sorted({r[0] for r in valid});rng=np.random.default_rng(271028)
    draws=[]
    for _ in range(800):
        values=[]
        for system in rng.choice(systems,size=len(systems),replace=True):
            a=[r[2] for r in valid if r[0]==system]
            values.extend(rng.choice(a,size=len(a),replace=True))
        draws.append(np.median(values))
    return dict(paired_count=len(valid),ratio=float(np.median([r[2] for r in valid])),
        ratio_ci_low=float(np.quantile(draws,.025)),ratio_ci_high=float(np.quantile(draws,.975)))


def select(rows,**filters):
    return [r for r in rows if all(r.get(k)==v for k,v in filters.items())]


COLORS={'dense':'#52667a','oracle_rank':'#008b83','truncated':'#008b83','adaptive':'#c86a1d'}
LABELS={'dense':'Dense','oracle_rank':'Truncated (true rank)','truncated':'Truncated','adaptive':'Adaptive (fixed c=1)'}


def curve(ax,rows,mode,x='transitions',y='failure_inclusive_gap_median',label=None,color=None):
    rows=sorted([r for r in rows if r['mode']==mode],key=lambda r:r[x])
    xx=[r[x] for r in rows];yy=[r[y] if r.get(y) is not None else np.nan for r in rows]
    ax.plot(xx,yy,'o-',ms=3,lw=1.7,color=color or COLORS.get(mode),label=label or LABELS.get(mode,mode))
    if y=='failure_inclusive_gap_median':
        lower=[r['stable_gap_q25'] if r['stable_rate']==1 else np.nan for r in rows]
        upper=[r['stable_gap_q75'] if r['stable_rate']==1 else np.nan for r in rows]
        ax.fill_between(xx,lower,upper,color=color or COLORS.get(mode),alpha=.1)


def style(ax,xlabel='Transitions (including burn-in)',ylabel='Absolute cost gap'):
    ax.set(xlabel=xlabel,ylabel=ylabel);ax.grid(True,which='both',alpha=.18)


def save(fig,report,name):
    fig.savefig(report/(name+'.png'),dpi=180,bbox_inches='tight')
    fig.savefig(report/(name+'.svg'),bbox_inches='tight');plt.close(fig)


def figures(report,agg,scaling,ce_raw):
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    for family in CFG['A_families']:
        fig,axes=plt.subplots(1,3,figsize=(13,3.7),layout='constrained')
        rows=select(agg,algorithm='CE',A_family=family,spectrum='exact',n=48)
        for mode in ['dense','oracle_rank','adaptive']:
            curve(axes[0],rows,mode);curve(axes[1],rows,mode,y='redundant_median')
            sr=select(scaling,A_family=family,mode=mode)
            axes[2].plot([r['n']/2 for r in sr],[r['failure_inclusive_gap_median'] for r in sr],
                'o-',color=COLORS[mode],label=LABELS[mode])
        for ax in axes[:2]:ax.set_xscale('log');ax.set_yscale('log');style(ax)
        axes[0].set_title('(a) Same fitted model, n=48, r=2')
        axes[1].set_title('(b) True redundant cost, n=48');axes[1].set_ylabel('J(K) - J(Pi_R K)')
        style(axes[2],'n / r','Absolute cost gap');axes[2].set_yscale('log')
        axes[2].set_title('(c) Fixed N / (n+m) = 64');axes[0].legend(fontsize=8)
        fig.suptitle('Exact-rank CE | '+('A = 0.5 I' if family=='scalar' else 'Independent dense A = 0.5 O'))
        save(fig,report,'figure1_exact_ce_'+family)
        fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
        for ax,n in zip(axes.flat,CFG['exact_dims']):
            rows=select(agg,algorithm='CE',A_family=family,spectrum='exact',n=n)
            for mode in ['dense','oracle_rank','adaptive']:curve(ax,rows,mode)
            ax.set_xscale('log');ax.set_yscale('log');style(ax);ax.set_title(f'n=m={n}, rank=2')
        axes[0,0].legend(fontsize=8);save(fig,report,'figureS_exact_all_dimensions_'+family)
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        for i,spectrum in enumerate(['gapped','smooth']):
            rows=select(agg,algorithm='CE',A_family=family,spectrum=spectrum,n=16)
            for N,color in [(256,'#4878a8'),(1024,'#39a28e'),(16384,'#c77c2c'),(65536,'#9d6b9e')]:
                fixed=sorted([r for r in rows if r['N']==N and r['mode']!='adaptive'],key=lambda r:int(r['mode'][1:]) if r['mode'].startswith('k') else 16)
                axes[i,0].plot([int(r['mode'][1:]) if r['mode'].startswith('k') else 16 for r in fixed],
                    [r['failure_inclusive_gap_median'] if r['failure_inclusive_gap_median'] is not None else np.nan for r in fixed],
                    'o-',ms=3,color=color,label=f'N={N}')
            axes[i,0].set_yscale('log');style(axes[i,0],'Truncation rank k');axes[i,0].set_title(spectrum+' full-rank spectrum')
            for mode,color in [('dense',COLORS['dense']),('k2','#008b83'),('k4','#8351a0'),('adaptive',COLORS['adaptive'])]:
                curve(axes[i,1],rows,mode,color=color,label={'k2':'Fixed k=2','k4':'Fixed k=4'}.get(mode))
            axes[i,1].set_xscale('log');axes[i,1].set_yscale('log');style(axes[i,1])
            adaptive=select(rows,mode='adaptive')
            curve(axes[i,2],adaptive,'adaptive',y='rank_median')
            envelope=[]
            for N in CFG['ce_budgets']:
                fixed=[r for r in rows if r['N']==N and r['mode']!='adaptive' and r['failure_inclusive_gap_median'] is not None]
                best=min(fixed,key=lambda r:r['failure_inclusive_gap_median'])
                envelope.append(dict(transitions=N+CFG['ce_burn'],k=16 if best['mode']=='dense' else int(best['mode'][1:])))
            axes[i,2].plot([r['transitions'] for r in envelope],[r['k'] for r in envelope],'s--',label='Best fixed-k median (oracle)',color='#52667a')
            axes[i,2].set_xscale('log');style(axes[i,2],ylabel='Retained rank');axes[i,2].set_ylim(-.5,16.5)
        for ax in axes[0]:ax.legend(fontsize=7)
        fig.suptitle('Full-rank CE | '+family+' A | c=1 frozen before formal data')
        save(fig,report,'figure2_approximate_ce_'+family)
        fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
        for i,spectrum in enumerate(['gapped','smooth']):
            for j,N in enumerate([1024,16384]):
                rows=select(agg,algorithm='CE',A_family=family,spectrum=spectrum,n=16,N=N)
                fixed=sorted([r for r in rows if r['mode']!='adaptive'],key=lambda r:int(r['mode'][1:]) if r['mode'].startswith('k') else 16)
                ks=[int(r['mode'][1:]) if r['mode'].startswith('k') else 16 for r in fixed]
                axes[i,j].plot(ks,[r['failure_inclusive_gap_median'] for r in fixed],'o-',color='#008b83',label='Observed median gap')
                ax2=axes[i,j].twinx()
                source=select(ce_raw,A_family=family,spectrum=spectrum,n=16,N=N,system=101,trial=100)
                bymode={r['mode']:r for r in source}
                bounds=[bymode[r['mode']]['bound_shape'] for r in fixed]
                ax2.plot(ks,bounds,'s--',color='#9d6b9e',alpha=.75,label='k(n+m)/N + tail squared')
                axes[i,j].set_yscale('log');ax2.set_yscale('log')
                style(axes[i,j],'Truncation rank k');ax2.set_ylabel('Uncalibrated bound shape',color='#9d6b9e')
                axes[i,j].set_title(f'{spectrum}, N={N}')
                if i==0 and j==0:
                    lines1,labels1=axes[i,j].get_legend_handles_labels();lines2,labels2=ax2.get_legend_handles_labels()
                    axes[i,j].legend(lines1+lines2,labels1+labels2,fontsize=7)
        fig.suptitle('Bias / variance mechanism | '+family+' A | independent vertical scales')
        save(fig,report,'figureS_bias_variance_'+family)
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        for j,spectrum in enumerate(CFG['spectra']):
            rows=select(agg,algorithm='NPG',A_family=family,spectrum=spectrum,n=12)
            for mode in ['dense','truncated']:
                curve(axes[0,j],rows,mode);curve(axes[1,j],rows,mode,y='stable_rate')
            axes[0,j].set_xscale('symlog',linthresh=1e4);axes[0,j].set_yscale('log');style(axes[0,j])
            axes[0,j].set_title(spectrum+(' (fixed k=4)' if spectrum=='smooth' else ' (fixed k=2)'))
            axes[1,j].set_xscale('symlog',linthresh=1e4);axes[1,j].set_ylim(-.03,1.03);style(axes[1,j],ylabel='Stable fraction (all 24 repeats)')
        axes[0,0].legend();fig.suptitle('Single continuous trajectory NPG | '+family+' A | all transitions counted')
        save(fig,report,'figure3_npg_'+family)


def main():
    require_compute();report=OUT/'report';report.mkdir(exist_ok=True)
    raw=list((OUT/'raw').glob('*.json'));assert len(raw)==576
    expected={s['id'] for system in CFG['systems'] for trial in CFG['trials'] for s in specs(system,trial)}
    assert {p.stem for p in raw}==expected
    records=[];diagnostics=[];accounting=[];certificates=[];identity_ref=identity();observed={}
    for p in sorted(raw):
        data=json.loads(p.read_text());assert data['identity']==identity_ref
        assert sha(p.with_suffix('.npz'))==data['arrays_sha256']
        spec=data['spec'];meta={k:spec[k] for k in ['algorithm','n','A_family','spectrum','system','trial']}
        meta['task_id']=spec['id'];cert=data['certificates'];certificates.append(dict(**meta,**{k:v for k,v in cert.items() if k not in meta}))
        accounting.append(dict(**meta,actual_transitions=data['actual_transitions'],assigned_transitions=data['assigned_transitions'],
            seconds=data['seconds'],status=data.get('status','complete'),job=data['provenance']['job']))
        if spec['algorithm']=='CE':
            for row in data['rows']:records.append(dict(**meta,**row))
        else:
            observed[(spec['A_family'],spec['spectrum'],spec['system'],spec['trial'],spec['mode'])]=data
            bystage={r['stage']:r for r in data['rows']};transition=0
            for stage in range(len(schedule())+1):
                if stage:transition+=(CFG['burn_blocks']+1+schedule()[stage-1])*CFG['H']
                row=bystage.get(stage,dict(stage=stage,transitions=transition,stable=False,gap=None,
                    failure='absorbed_after_'+data['status']))
                records.append(dict(**meta,mode=spec['mode'],**row))
            for row in data['same_first_blocks_diagnostic']:
                diagnostics.append(dict(**meta,source_method=spec['mode'],**row))
    for key,data in observed.items():
        if key[-1]=='dense':
            other=observed[key[:-1]+('truncated',)]
            assert data['same_first_blocks_diagnostic']==other['same_first_blocks_diagnostic'],'First-stage pairing mismatch'
    groups={}
    for row in records:
        keys=['algorithm','A_family','spectrum','n','mode','transitions']+(['N'] if row['algorithm']=='CE' else ['stage'])
        key=tuple((k,row[k]) for k in keys);groups.setdefault(key,[]).append(row)
    agg=[group_stats(dict(key),rows) for key,rows in groups.items()]
    assert all(r['count']==24 for r in agg)
    ce=[r for r in records if r['algorithm']=='CE'];scaling=[];effects=[];envelopes=[];mechanisms=[]
    for family in CFG['A_families']:
        for n in CFG['exact_dims']:
            rows=select(ce,A_family=family,spectrum='exact',n=n,N=128*n)
            for mode in ['dense','oracle_rank','adaptive']:
                stat=next(r for r in agg if all(r.get(k)==v for k,v in dict(algorithm='CE',A_family=family,spectrum='exact',n=n,mode=mode,N=128*n).items()))
                scaling.append(dict(stat))
            for mode in ['oracle_rank','adaptive']:
                effects.append(dict(A_family=family,n=n,N=128*n,alternative=mode,**paired_bootstrap(rows,'dense',mode)))
                paired={}
                for row in rows:
                    if row['mode'] in ['dense',mode]:paired.setdefault((row['system'],row['trial']),{})[row['mode']]=row
                valid=[p for p in paired.values() if len(p)==2 and all(r['stable'] for r in p.values())]
                deltas=[p['dense']['gap']-p[mode]['gap'] for p in valid]
                redundant_deltas=[p['dense']['redundant_cost']-p[mode]['redundant_cost'] for p in valid]
                shares=[dr/dg for dr,dg in zip(redundant_deltas,deltas) if dg>0]
                mechanisms.append(dict(A_family=family,n=n,N=128*n,alternative=mode,paired_count=len(valid),
                    gap_reduction_median=median(deltas),redundant_reduction_median=median(redundant_deltas),
                    redundant_share_median_among_improved=median(shares),improved_count=sum(d>0 for d in deltas),
                    dense_redundant_median=median([p['dense']['redundant_cost'] for p in valid]),
                    truncated_redundant_median=median([p[mode]['redundant_cost'] for p in valid])))
        for spectrum in ['gapped','smooth']:
            for N in CFG['ce_budgets']:
                rows=select(agg,algorithm='CE',A_family=family,spectrum=spectrum,n=16,N=N)
                fixed=[r for r in rows if r['mode']!='adaptive' and r['failure_inclusive_gap_median'] is not None]
                best=min(fixed,key=lambda r:r['failure_inclusive_gap_median'])
                adaptive=next(r for r in rows if r['mode']=='adaptive');dense=next(r for r in rows if r['mode']=='dense')
                envelopes.append(dict(A_family=family,spectrum=spectrum,N=N,best_fixed_k=16 if best['mode']=='dense' else int(best['mode'][1:]),
                    best_fixed_median=best['failure_inclusive_gap_median'],adaptive_gap=adaptive['failure_inclusive_gap_median'],
                    adaptive_rank=adaptive['rank_median'],dense_gap=dense['failure_inclusive_gap_median']))
    diag_groups={}
    for row in diagnostics:
        if row['source_method']!='dense':continue
        key=(row['A_family'],row['spectrum'],row['mode']);diag_groups.setdefault(key,[]).append(row)
    diag_summary=[]
    for (family,spectrum,mode),rows in diag_groups.items():
        diag_summary.append(dict(A_family=family,spectrum=spectrum,mode=mode,count=len(rows),
            stable_rate=sum(r['stable'] for r in rows)/len(rows),Z_error_fro2_median=median([r['Z_error_fro2'] for r in rows]),
            Z_error_op_median=median([r['Z_error_op'] for r in rows]),redundant_median=median([r['redundant_cost'] for r in rows if r.get('redundant_cost') is not None])))
    write_csv(report/'all_records.csv',records);write_csv(report/'aggregate.csv',agg)
    write_csv(report/'sampling_accounting.csv',accounting);write_csv(report/'same_blocks_diagnostic.csv',diagnostics)
    write_csv(report/'same_blocks_summary.csv',diag_summary);write_csv(report/'exact_dimension_scaling.csv',scaling)
    write_csv(report/'paired_effects_bootstrap.csv',effects);write_csv(report/'approximate_rank_envelopes.csv',envelopes)
    write_csv(report/'exact_redundant_mechanism.csv',mechanisms)
    atomic_json(report/'system_certificates.json',certificates)
    figures(report,agg,scaling,ce)
    endpoints=[r for r in agg if r['algorithm']=='NPG' and r['stage']==len(schedule())]
    summary=dict(status='PASS',planned_trajectories=576,completed_files=len(raw),
        CE_trajectories=288,NPG_trajectories=288,formal_observations=len(records),
        formal_actual_transitions=sum(r['actual_transitions'] for r in accounting),
        formal_assigned_transitions=sum(r['assigned_transitions'] for r in accounting),
        actor_unstable=sum(r['status']=='unstable' for r in accounting),
        actor_numerical_failures=sum(r['status']=='numerical_failure' for r in accounting),
        ce_failed_outputs=sum(not r['stable'] for r in ce),
        maximum_decomposition_residual=max(r.get('decomposition_residual',0.) for r in records),
        exact_paired_effects=effects,exact_redundant_mechanism=mechanisms,NPG_endpoints=endpoints,approximate_envelopes=envelopes,
        same_blocks_summary=diag_summary,identity=identity_ref,provenance=provenance(),report_source_sha256=sha(__file__))
    atomic_json(report/'summary.json',summary)
    lines=['# 三组主实验：实际结果（2026-10-27）','',
        '全部576条正式采集轨迹已记录。每个设置24重复=3个系统种子×8个采样种子。',
        f"CE失败输出{summary['ce_failed_outputs']}；NPG失稳轨迹{summary['actor_unstable']}；NPG数值失败{summary['actor_numerical_failures']}。",
        f"正式实际采样{summary['formal_actual_transitions']:,} transitions；分配上限{summary['formal_assigned_transitions']:,}。",
        '不稳定视为失败保留在分母；图中gap为失败按无穷大计的中位数，阴影仅画全部稳定点的IQR。','',
        '## Exact-rank CE：固定 N/(n+m)=64','',
        '|A|n/r|dense gap|true-rank gap|adaptive gap|dense/true-rank 配对中位比与95%区间|','|---|---:|---:|---:|---:|---|']
    def fmt(v):return '失败中位数为无穷大' if v is None else f'{v:.5g}'
    for family in CFG['A_families']:
        for n in CFG['exact_dims']:
            group=select(scaling,A_family=family,n=n)
            gaps={r['mode']:r['failure_inclusive_gap_median'] for r in group}
            effect=next(r for r in effects if r['A_family']==family and r['n']==n and r['alternative']=='oracle_rank')
            lines.append(f"|{family}|{n/2:g}|{fmt(gaps['dense'])}|{fmt(gaps['oracle_rank'])}|{fmt(gaps['adaptive'])}|{fmt(effect['ratio'])} [{fmt(effect['ratio_ci_low'])}, {fmt(effect['ratio_ci_high'])}]|")
    lines+=['','## 满秩CE：数据自适应与固定k的经验包络','',
        '|A|谱|N|经验最佳固定k|最佳固定gap|adaptive gap|adaptive rank|dense gap|','|---|---|---:|---:|---:|---:|---:|---:|']
    for r in envelopes:
        lines.append('|'+ '|'.join([r['A_family'],r['spectrum'],str(r['N']),str(r['best_fixed_k']),fmt(r['best_fixed_median']),fmt(r['adaptive_gap']),fmt(r['adaptive_rank']),fmt(r['dense_gap'])])+'|')
    lines+=['','## 单轨迹NPG：最终累计预算','',
        '|A|谱|方法|transitions|gap中位数（失败=∞）|稳定数/24|','|---|---|---|---:|---:|---:|']
    for r in endpoints:
        lines.append(f"|{r['A_family']}|{r['spectrum']}|{r['mode']}|{r['transitions']:,}|{fmt(r['failure_inclusive_gap_median'])}|{r['stable_count']}/24|")
    lines+=['','## 解读边界','',
        '固定k最优值和真实子空间投影只用于离线诊断。adaptive常数1在正式生成前固定；split误差代理没有被验证为理论置信半径。',
        '上界形状k(n+m)/N+tau_k²及全部tail数据在逐输出CSV；系统常数未标定，不将它当作实际最优k预测器。',
        '标量A系统的旋转保持动力学等价；稠密A相对于B独立生成。结果为经验比较，不宣称验证渐近维度指数或问题类下界。',
        'NPG方法分叉后使用不同状态，只配对外生噪声。48步是预先固定排程，未用真实cost选择迭代或拒绝更新。',
        '完整结果主存储在Grace；本地只取回报告、配置和收据。']
    (report/'findings.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    hashes={p.name:sha(p) for p in report.iterdir() if p.is_file() and p.name!='SHA256SUMS'}
    (report/'SHA256SUMS').write_text(''.join(h+'  '+p+'\n' for p,h in sorted(hashes.items())))
    print(json.dumps({k:v for k,v in summary.items() if k not in ['identity','NPG_endpoints','approximate_envelopes','exact_paired_effects','same_blocks_summary']},indent=2))


if __name__=='__main__':main()
