"""Report v2: all-seed K0 counterfactual, explicit failure markers; no learning replay."""
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
from ce_npg_argument_grid import NAME,OUT,OLD,CFG,all_specs,schedule
from ce_npg_argument_run import identity,provenance,sha,plant,assess,atomic_json,require_compute
from manuscript_three_groups_report import write_csv,median,group_stats,paired_bootstrap

COLORS={'dense':'#53687b','truncated':'#008c83','adaptive':'#ce731f','k2':'#008c83','k4':'#8c58a4'}


def select(rows,**filters):return [r for r in rows if all(r.get(k)==v for k,v in filters.items())]


def finite(value):return np.nan if value is None else value


def load_all():
    audit=json.loads((OUT/'reuse-audit.json').read_text());assert audit['status']=='PASS' and audit['count']==336
    verified={r['id']:r for r in audit['verified']};expected=all_specs()
    wanted={s['id'] for s in expected if s['reuse_id'] is None}
    found={p.stem for p in (OUT/'raw').glob('*.json') if '.checkpoint.' not in p.name}
    assert found==wanted,('incomplete or unexpected grid',len(found),len(wanted))
    records=[];diagnostics=[];sources=[];certificates=[];plants={}
    for spec in expected:
        reused=spec['reuse_id'] is not None
        path=(OLD/'raw'/(spec['reuse_id']+'.json')) if reused else OUT/'raw'/(spec['id']+'.json')
        data=json.loads(path.read_text());assert sha(path.with_suffix('.npz'))==data['arrays_sha256']
        if reused:assert sha(path)==verified[spec['id']]['json_sha256']
        else:assert data['identity']==identity()
        key=tuple(spec[k] for k in ['n','r','A_family','spectrum','system'])
        if key not in plants:plants[key]=plant(spec)
        s,basis,cert=plants[key]
        meta={key:spec[key] for key in ['algorithm','n','r','A_family','spectrum','system','trial']}
        meta.update(task_id=spec['id'],reused=reused)
        certificates.append(dict(**meta,**{k:v for k,v in cert.items() if k not in meta}))
        source=dict(**meta,status=data.get('status','complete'),seconds=data['seconds'],
            actual_transitions=data['actual_transitions'],assigned_transitions=data['assigned_transitions'],
            job=data['provenance']['job'],source_json=str(path),arrays_sha256=data['arrays_sha256'])
        sources.append(source)
        old_rows=data['rows']
        if spec['algorithm']=='CE':
            with np.load(path.with_suffix('.npz'),allow_pickle=False) as arrays:
                for original in old_rows:
                    row=dict(original);mode=row['mode'];row['mode']='truncated' if mode=='oracle_rank' else mode
                    if reused and row['stable']:
                        q=assess(s,arrays[f"K_{row['N']}_{mode}"],basis)
                        assert abs(q['gap']-row['gap'])<1e-7*max(1.,row['cost'])
                        row.update(q)
                    records.append(dict(**meta,**row))
        else:
            saved={r['stage']:dict(r) for r in old_rows};transition=0
            with np.load(path.with_suffix('.npz'),allow_pickle=False) as arrays:
                for stage in range(len(schedule())+1):
                    if stage:transition+=(13+schedule()[stage-1])*12
                    row=saved.get(stage,dict(stage=stage,transitions=transition,stable=False,gap=None,
                        failure='absorbed_after_'+data['status']))
                    row['actual_transitions_at_output']=row['transitions'] if stage in saved else data['actual_transitions']
                    row['transitions']=transition
                    if reused and row['stable']:
                        q=assess(s,arrays['policies'][stage],basis)
                        assert abs(q['gap']-row['gap'])<1e-7*max(1.,row['cost'])
                        row.update(q)
                    records.append(dict(**meta,mode=spec['mode'],k=spec['k'],**row))
            raw_diagnostics=data.get('same_blocks_diagnostic',data.get('same_first_blocks_diagnostic',[]))
            for original in raw_diagnostics:
                row=dict(original);row.setdefault('stage',1)
                row.setdefault('transitions',(13+schedule()[0])*12)
                row.setdefault('k',spec['r'] if spec['spectrum']=='exact' else spec['k'])
                if row.get('projected_cost') is not None:row['projected_gap']=row['projected_cost']-s['Jstar']
                diagnostics.append(dict(**meta,source_mode=spec['mode'],**{k:v for k,v in row.items() if k!='source_mode'}))
    assert len(sources)==2064 and sum(s['reused'] for s in sources)==336
    return records,diagnostics,sources,certificates


def aggregate(records):
    groups={}
    for row in records:
        keys=['algorithm','A_family','spectrum','n','r','mode','transitions']
        keys += ['N'] if row['algorithm']=='CE' else ['stage']
        key=tuple((k,row.get(k)) for k in keys);groups.setdefault(key,[]).append(row)
    result=[]
    for key,rows in groups.items():
        assert len(rows)==24,(key,len(rows))
        stat=group_stats(dict(key),rows)
        for source,dest in [('projected_gap','projected_gap_median'),('P_relative_max','P_relative_max_median')]:
            stat[dest]=median([r[source] for r in rows if r['stable'] and r.get(source) is not None])
        stat['containment_rate']=sum(r['stable'] and r.get('CE_containment' if r['algorithm']=='CE' else 'NPG_containment',False) for r in rows)/len(rows)
        stat['failed_count']=len(rows)-stat['stable_count']
        result.append(stat)
    return result


def curve(ax,rows,mode,y='failure_inclusive_gap_median',label=None,color=None,linestyle='-'):
    selected=sorted(select(rows,mode=mode),key=lambda r:r['transitions'])
    if not selected:return
    xs=[r['transitions'] for r in selected];ys=[finite(r.get(y)) for r in selected]
    color=color or COLORS.get(mode,'#8c58a4')
    ax.plot(xs,ys,linestyle,marker='o',ms=2.5,lw=1.55,color=color,label=label or mode)
    if y=='failure_inclusive_gap_median':
        lo=[finite(r['stable_gap_q25']) if r['stable_rate']==1 else np.nan for r in selected]
        hi=[finite(r['stable_gap_q75']) if r['stable_rate']==1 else np.nan for r in selected]
        ax.fill_between(xs,lo,hi,color=color,alpha=.1)


def style(ax,xlabel='Transitions (burn + baseline included)',ylabel='Absolute cost gap',logx=True,logy=True):
    ax.set(xlabel=xlabel,ylabel=ylabel);ax.grid(alpha=.18,which='both')
    if logx:ax.set_xscale('symlog',linthresh=200)
    if logy:ax.set_yscale('log')


def save(fig,report,name):
    fig.savefig(report/(name+'.png'),dpi=190,bbox_inches='tight')
    fig.savefig(report/(name+'.svg'),bbox_inches='tight');plt.close(fig)


def stability_labels(ax,rows,mode,xkey,offset):
    for row in rows:
        ax.text(row[xkey],.025+.075*offset,f"{row['stable_count']}/24",
            transform=ax.get_xaxis_transform(),ha='center',va='bottom',fontsize=6.5,color=COLORS[mode],
            bbox=dict(facecolor='white',edgecolor='none',alpha=.8,pad=.5))
        if row['failure_inclusive_gap_median'] is None:
            ax.text(row[xkey],.94-.1*offset,'∞',transform=ax.get_xaxis_transform(),
                ha='center',va='top',fontsize=13,color=COLORS[mode])


def figure1(report,agg,family,name):
    fig,axes=plt.subplots(2,3,figsize=(13.5,7.4),layout='constrained')
    for i,algorithm in enumerate(['CE','NPG']):
        base=select(agg,algorithm=algorithm,A_family=family,spectrum='exact')
        learning=select(base,n=24,r=2)
        for mode in ['dense','truncated']:curve(axes[i,0],learning,mode,label=mode.title())
        style(axes[i,0]);axes[i,0].set_title(f'{algorithm}: learning, n=m=24, r=2')
        for offset,mode in enumerate(['dense','truncated']):
            values=[]
            for n in [12,24,48]:
                vals=select(base,n=n,r=2,mode=mode)
                chosen=next(r for r in vals if r.get('N')==128*n) if algorithm=='CE' else next(r for r in vals if r['stage']==48)
                values.append(chosen)
            axes[i,1].plot([r['n'] for r in values],[finite(r['failure_inclusive_gap_median']) for r in values],
                'o-',color=COLORS[mode],label=mode.title())
            if algorithm=='NPG':stability_labels(axes[i,1],values,mode,'n',offset)
            values=[]
            for rank in [1,2,4,8]:
                vals=select(base,n=24,r=rank,mode=mode)
                chosen=next(r for r in vals if r.get('N')==3072) if algorithm=='CE' else next(r for r in vals if r['stage']==48)
                values.append(chosen)
            axes[i,2].plot([r['r'] for r in values],[finite(r['failure_inclusive_gap_median']) for r in values],
                'o-',color=COLORS[mode],label=mode.title())
            if algorithm=='NPG':stability_labels(axes[i,2],values,mode,'r',offset)
        style(axes[i,1],'n = m',logx=False);style(axes[i,2],'True rank r (n=m=24)',logx=False)
        axes[i,1].set_title('CE: N/(n+m)=64' if algorithm=='CE' else 'NPG: M=25,075,008 per arm')
        axes[i,2].set_title(f'{algorithm}: rank sweep at fixed budget')
        axes[i,0].legend(fontsize=8)
        if algorithm=='NPG':
            end=[next(r for r in learning if r['mode']==mode and r['stage']==48) for mode in ['dense','truncated']]
            axes[i,0].text(.03,.97,'\n'.join(r['mode'].title()+f": {r['stable_count']}/24 stable" for r in end),
                transform=axes[i,0].transAxes,va='top',fontsize=7,
                bbox=dict(facecolor='white',edgecolor='none',alpha=.85))
    fig.suptitle('Exact-rank learning and dimension benefits | '+family+' A | 24 repeats per point')
    fig.text(.5,-.012,'Colored counts: stable/24. Infinity symbols indicate an infinite failure-inclusive median; their height is not a finite cost.',
        ha='center',fontsize=7)
    save(fig,report,name)


def figure2(report,agg,diagnostics,family,name):
    fig,axes=plt.subplots(2,3,figsize=(13.5,7.2),layout='constrained')
    for i,algorithm in enumerate(['CE','NPG']):
        rows=select(agg,algorithm=algorithm,A_family=family,spectrum='exact',n=24,r=2)
        for mode in ['dense','truncated']:
            curve(axes[i,0],rows,mode,y='redundant_median',label=mode.title())
            curve(axes[i,1],rows,mode,y='projected_gap_median',label=mode.title())
        style(axes[i,0],ylabel='D(K), stable policies');style(axes[i,1],ylabel='Projected gap, stable policies')
        axes[i,0].set_title(f'{algorithm}: redundant control cost')
        axes[i,1].set_title(f'{algorithm}: remaining effective loss')
    ce=select(agg,algorithm='CE',A_family=family,spectrum='exact',n=24,r=2,N=3072)
    xs=np.arange(2);width=.35
    for j,mode in enumerate(['dense','truncated']):
        row=next(r for r in ce if r['mode']==mode)
        axes[0,2].bar(xs+(j-.5)*width,[finite(row['failure_inclusive_gap_median']),finite(row['redundant_median'])],
            width,color=COLORS[mode],label=mode.title())
    axes[0,2].set_xticks(xs,['Total gap','Redundant cost']);style(axes[0,2],'Same OLS, N=3,072',logx=False)
    axes[0,2].set_title('CE: identical trajectory and model estimate')
    same=select(diagnostics,A_family=family,spectrum='exact',n=24,r=2,source_mode='dense',stage=1)
    for j,mode in enumerate(['dense','truncated']):
        rows=select(same,mode=mode);assert len(rows)==24
        vals=[]
        for key in ['gap','redundant_cost']:
            vals.append(median([r.get(key,float('inf')) if r['stable'] else float('inf') for r in rows]))
        axes[1,2].bar(xs+(j-.5)*width,[finite(v) for v in vals],width,color=COLORS[mode],label=mode.title())
    axes[1,2].set_xticks(xs,['Next-step gap','Next-step D']);style(axes[1,2],'Same K0, same first blocks; all 24 repeats',logx=False)
    axes[1,2].set_title('NPG: shared-data single-step updates')
    axes[0,0].legend(fontsize=8);axes[0,2].legend(fontsize=8)
    fig.suptitle('Noise-to-redundant-cost mechanism | '+family+' A | estimated subspaces may have nonzero D')
    save(fig,report,name)


def rank_panel(ax,rows,algorithm,spectrum):
    if algorithm=='CE':points=[256,1024,16384,65536];field='N'
    else:points=[12,24,36,48];field='stage'
    for value,color in zip(points,['#4575a5','#319982','#c77b2d','#9466a6']):
        selected=[r for r in rows if r.get(field)==value and r['mode']!='adaptive']
        selected=sorted(selected,key=lambda r:16 if r['mode']=='dense' else int(r['mode'][1:]))
        ks=[16 if r['mode']=='dense' else int(r['mode'][1:]) for r in selected]
        if not selected:continue
        label=f'N={value:,}' if algorithm=='CE' else f"M={selected[0]['transitions']/1e6:.2f}M"
        ax.plot(ks,[finite(r['failure_inclusive_gap_median']) for r in selected],'o-',ms=3,color=color,label=label)
    style(ax,'Truncation rank k',logx=False);ax.set_title(f'{algorithm}: {spectrum} full rank');ax.legend(fontsize=6.5)


def figure3(report,agg,family,name):
    fig,axes=plt.subplots(2,4,figsize=(17,7.6),layout='constrained')
    for i,algorithm in enumerate(['CE','NPG']):
        for j,spectrum in enumerate(['gapped','smooth']):
            rows=select(agg,algorithm=algorithm,A_family=family,spectrum=spectrum,n=16)
            rank_panel(axes[i,j],rows,algorithm,spectrum)
    ce=select(agg,algorithm='CE',A_family=family,spectrum='smooth',n=16)
    for mode in ['dense','k2','adaptive']:curve(axes[0,2],ce,mode,label=mode.title())
    style(axes[0,2]);axes[0,2].set_title('CE: fixed rank and frozen adaptive c=1');axes[0,2].legend(fontsize=7)
    for spectrum,color in [('gapped','#008c83'),('smooth','#8c58a4')]:
        rows=select(agg,algorithm='CE',A_family=family,spectrum=spectrum,n=16)
        curve(axes[0,3],rows,'adaptive',y='rank_median',label=spectrum,color=color)
    style(axes[0,3],ylabel='Adaptive retained rank',logy=False);axes[0,3].set_ylim(-.5,16.5)
    axes[0,3].set_title('CE: data-selected ranks');axes[0,3].legend(fontsize=7)
    npg=select(agg,algorithm='NPG',A_family=family,spectrum='smooth',n=16)
    for mode in ['dense','k2','k4']:curve(axes[1,2],npg,mode,label=mode.title())
    style(axes[1,2]);axes[1,2].set_title('NPG: fixed k and changing budget');axes[1,2].legend(fontsize=7)
    for algorithm,color in [('CE','#ce731f'),('NPG','#008c83')]:
        rows=select(agg,algorithm=algorithm,A_family='scalar',spectrum='flat',n=16)
        rows=[r for r in rows if (r.get('N')==65536 if algorithm=='CE' else r.get('stage')==48) and r['mode']!='adaptive']
        dense=next(r for r in rows if r['mode']=='dense')['failure_inclusive_gap_median']
        ordered=sorted(rows,key=lambda r:16 if r['mode']=='dense' else int(r['mode'][1:]))
        axes[1,3].plot([16 if r['mode']=='dense' else int(r['mode'][1:]) for r in ordered],
            [finite(r['failure_inclusive_gap_median'])/dense if dense else np.nan for r in ordered],
            'o-',color=color,label=algorithm+' / own dense')
    axes[1,3].axhline(1,color='#aaa',ls='--',lw=1)
    style(axes[1,3],'Truncation rank k','Gap / own dense gap',logx=False)
    axes[1,3].set_title('Flat spectrum control (scalar A)');axes[1,3].legend(fontsize=7)
    fig.suptitle('Full-rank spectra, bias/variance tradeoff and unknown-rank CE | '+family+' A')
    save(fig,report,name)


def attainment(agg,records):
    result=[];per_run=[]
    groups={}
    sample_index={}
    key_fields=['algorithm','A_family','n','r','mode']
    for row in records:
        if row['spectrum']=='exact' and row['mode'] in ['dense','truncated']:
            key=tuple((k,row[k]) for k in key_fields)
            sample_index.setdefault((key,row['transitions']),[]).append(row)
    for row in agg:
        if row['spectrum']!='exact' or row['mode'] not in ['dense','truncated']:continue
        key=tuple((k,row[k]) for k in key_fields);groups.setdefault(key,[]).append(row)
    for key,rows in groups.items():
        rows=sorted(rows,key=lambda r:r['transitions'])
        for epsilon in CFG['evaluation']['absolute_gap_targets']:
            # Success counts are reconstructed from all individual outputs, including absorbed failures.
            found=None;rate=None
            for row in rows:
                sample=sample_index[key,row['transitions']]
                assert len(sample)==24
                success=sum(x['stable'] and x.get('gap') is not None and x['gap']<=epsilon for x in sample)/24
                if success>=.9:found=row['transitions'];rate=success;break
            result.append(dict(**dict(key),epsilon=epsilon,attainment_transitions=found,success_rate_at_attainment=rate,
                censored=found is None,maximum_budget=max(r['transitions'] for r in rows)))
    trajectories={}
    for row in records:
        if row['algorithm']=='NPG' and row['spectrum']=='exact':trajectories.setdefault(row['task_id'],[]).append(row)
    for task_id,rows in trajectories.items():
        rows=sorted(rows,key=lambda r:r['stage'])
        for epsilon in CFG['evaluation']['absolute_gap_targets']:
            yes=[bool(r['stable'] and r.get('gap') is not None and r['gap']<=epsilon) for r in rows]
            first=next((r['transitions'] for r,ok in zip(rows,yes) if ok),None)
            confirm=next((rows[i+3]['transitions'] for i in range(len(rows)-3) if all(yes[i:i+4])),None)
            per_run.append(dict(task_id=task_id,epsilon=epsilon,first_hit_transitions=first,
                four_point_confirmation_transitions=confirm,**{k:rows[0][k] for k in ['A_family','n','r','mode','system','trial']}))
    return result,per_run


def fmt(value):return '未达到/失败中位数∞' if value is None else f'{value:.6g}'


def main():
    require_compute();report=OUT/'report';report.mkdir(parents=True,exist_ok=True)
    records,diagnostics,sources,certificates=load_all();agg=aggregate(records)
    # Save audited derived data before plotting, so visual corrections can reuse these tables.
    write_csv(report/'all_records.csv',records);write_csv(report/'aggregate.csv',agg)
    write_csv(report/'sampling_accounting.csv',sources);write_csv(report/'same_blocks_diagnostic.csv',diagnostics)
    matched=[r for r in agg if r['spectrum']=='exact' and r['mode'] in ['dense','truncated'] and
        (r.get('N')==128*r['n'] if r['algorithm']=='CE' else r.get('stage')==48)]
    write_csv(report/'matched_budget_statistics.csv',matched)
    endpoints={}
    for r in agg:
        key=tuple(r[k] for k in ['algorithm','A_family','spectrum','n','r','mode'])
        if key not in endpoints or r['transitions']>endpoints[key]['transitions']:endpoints[key]=r
    write_csv(report/'endpoint_all_denominators.csv',list(endpoints.values()))
    att,per_run=attainment(agg,records);effects=[];mechanisms=[]
    for family in ['scalar','dense']:
        for n,rank in [(12,2),(24,2),(48,2),(24,1),(24,4),(24,8)]:
            for algorithm in ['CE','NPG']:
                rows=select(records,algorithm=algorithm,A_family=family,spectrum='exact',n=n,r=rank)
                rows=[r for r in rows if (r.get('N')==128*n if algorithm=='CE' else r.get('stage')==48)]
                effects.append(dict(algorithm=algorithm,A_family=family,n=n,r=rank,
                    **paired_bootstrap(rows,'dense','truncated')))
                pairs={}
                for row in rows:
                    if row['mode'] in ['dense','truncated']:pairs.setdefault((row['system'],row['trial']),{})[row['mode']]=row
                valid=[p for p in pairs.values() if len(p)==2 and all(r['stable'] for r in p.values())]
                mechanisms.append(dict(algorithm=algorithm,A_family=family,n=n,r=rank,total_pairs=24,stable_pairs=len(valid),
                    gap_reduction_median=median([p['dense']['gap']-p['truncated']['gap'] for p in valid]),
                    redundant_reduction_median=median([p['dense']['redundant_cost']-p['truncated']['redundant_cost'] for p in valid]),
                    effective_gap_reduction_median=median([p['dense']['projected_gap']-p['truncated']['projected_gap'] for p in valid])))
    envelopes=[]
    for algorithm in ['CE','NPG']:
        for family in ['scalar','dense']:
            for spectrum in ['gapped','smooth']:
                rows=select(agg,algorithm=algorithm,A_family=family,spectrum=spectrum,n=16)
                budgets=sorted({r['transitions'] for r in rows})
                for budget in budgets:
                    fixed=[r for r in rows if r['transitions']==budget and r['mode']!='adaptive']
                    valid=[r for r in fixed if r['failure_inclusive_gap_median'] is not None]
                    best=min(valid,key=lambda r:r['failure_inclusive_gap_median']) if valid else None
                    dense=next(r for r in fixed if r['mode']=='dense')
                    adaptive=next((r for r in rows if r['transitions']==budget and r['mode']=='adaptive'),None)
                    envelopes.append(dict(algorithm=algorithm,A_family=family,spectrum=spectrum,transitions=budget,
                        best_fixed_k=(16 if best['mode']=='dense' else int(best['mode'][1:])) if best else None,
                        best_fixed_gap=best['failure_inclusive_gap_median'] if best else None,
                        dense_gap=dense['failure_inclusive_gap_median'],
                        adaptive_gap=adaptive['failure_inclusive_gap_median'] if adaptive else None,
                        adaptive_rank=adaptive['rank_median'] if adaptive else None))
    plt.rcParams.update({'font.size':8.5,'axes.spines.top':False,'axes.spines.right':False})
    for family in ['scalar','dense']:
        prefix='' if family=='scalar' else 'appendix_'
        figure1(report,agg,family,prefix+'figure1_learning_dimension')
        figure2(report,agg,diagnostics,family,prefix+'figure2_redundant_mechanism')
        figure3(report,agg,family,prefix+'figure3_fullrank_adaptive')
    fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    for ax,algorithm in zip(axes,['CE','NPG']):
        for mode in ['dense','k2']:
            xs=[];ys=[]
            for spectrum,tail in [('gapped001',.01),('gapped',.05),('gapped02',.2)]:
                rows=select(agg,algorithm=algorithm,A_family='scalar',spectrum=spectrum,n=16,mode=mode)
                row=next(r for r in rows if (r.get('N')==65536 if algorithm=='CE' else r.get('stage')==48))
                xs.append(14*tail**2);ys.append(finite(row['failure_inclusive_gap_median']))
            ax.plot(xs,ys,'o-',color=COLORS[mode],label=mode)
        style(ax,'Squared Frobenius tail of B at k=2',logx=True);ax.set_title(algorithm+': fixed k2 tail control');ax.legend()
    save(fig,report,'appendix_tail_strength')
    write_csv(report/'fixed_accuracy.csv',att);write_csv(report/'NPG_first_and_confirmed_hits.csv',per_run)
    write_csv(report/'paired_gap_effects.csv',effects);write_csv(report/'paired_mechanism.csv',mechanisms)
    write_csv(report/'rank_envelopes.csv',envelopes)
    failed_outputs=[r for r in records if not r['stable']];write_csv(report/'failed_outputs.csv',failed_outputs)
    flat=[r for r in agg if r['spectrum']=='flat' and (r.get('N')==65536 if r['algorithm']=='CE' else r.get('stage')==48)]
    summary=dict(status='PASS',study=NAME,report_version=2,learning_replayed=False,
        report_correction='Use all 24 first-stage shared-K0 counterfactuals; later-stage diagnostics are conditional on surviving source paths',
        all_planned_trajectories=2064,new_trajectories=1728,reused_trajectories=336,
        observations=len(records),new_actual_transitions=sum(s['actual_transitions'] for s in sources if not s['reused']),
        new_assigned_transitions=sum(s['assigned_transitions'] for s in sources if not s['reused']),
        reused_actual_transitions=sum(s['actual_transitions'] for s in sources if s['reused']),
        NPG_unstable=sum(s['algorithm']=='NPG' and s['status']=='unstable' for s in sources),
        NPG_numerical_failures=sum(s['algorithm']=='NPG' and s['status']=='numerical_failure' for s in sources),
        CE_failed_outputs=sum(r['algorithm']=='CE' and not r['stable'] for r in records),
        maximum_decomposition_residual=max(r.get('decomposition_residual',0.) for r in records),
        exact_effects=effects,paired_mechanisms=mechanisms,rank_envelopes=envelopes,flat_endpoints=flat,
        shared_block_diagnostics=len(diagnostics),identity=identity(),provenance=provenance(),report_source_sha256=sha(__file__))
    atomic_json(report/'summary.json',summary);atomic_json(report/'system_certificates.json',certificates)
    lines=['# CE / NPG 三张组合图：完整结果（2026-10-28）','',
        f"全部2,064条计划轨迹已纳入；新增1,728，复用336。每单元24重复=3系统种子×8采样种子。",
        f"新增实际采集{summary['new_actual_transitions']:,} transitions；新增分配预算{summary['new_assigned_transitions']:,}。复用数据不计为新增采样。",
        f"NPG失稳{summary['NPG_unstable']}条，数值失败{summary['NPG_numerical_failures']}条；CE失败输出{summary['CE_failed_outputs']}。全部保留在计划分母。",'',
        '## 图1：学习与维度、秩收益','',
        '|算法|A|n|r|dense/truncated 配对gap中位比|95%区间|有效配对/24|',
        '|---|---|---:|---:|---:|---|---:|']
    for row in effects:
        lines.append(f"|{row['algorithm']}|{row['A_family']}|{row['n']}|{row['r']}|{fmt(row['ratio'])}|[{fmt(row['ratio_ci_low'])},{fmt(row['ratio_ci_high'])}]|{row['paired_count']}|")
    lines+=['','CE取N/(n+m)=64，NPG取完整M=25,075,008。这里是gap倍率，不是样本加速比；失稳的配对不进入有限倍率，但失败保留在其余全分母统计。',
        '固定精度预算、右删失和NPG四点确认见fixed_accuracy.csv及NPG_first_and_confirmed_hits.csv。','',
        '## 图2：冗余噪声机制','',
        '|算法|A|n|r|配对gap下降|配对冗余代价下降|配对有效gap下降|稳定配对/24|',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for row in mechanisms:
        lines.append(f"|{row['algorithm']}|{row['A_family']}|{row['n']}|{row['r']}|{fmt(row['gap_reduction_median'])}|{fmt(row['redundant_reduction_median'])}|{fmt(row['effective_gap_reduction_median'])}|{row['stable_pairs']}|")
    lines+=['','分解按每条gain先计算再配对统计；三个中位数不要求相加相等。截断估计空间的真实冗余代价可非零。',
        'NPG单步反事实使用同一K、同一批blocks；完整两臂分叉后只有外生创新配对，不共享状态。',
        '主机制图使用全24重复共同K0的第一阶段；stage24/48仅对实际存活的来源路径存在，分母据实记录。',
        '完整轨迹的D和投影gap曲线是稳定策略上的诊断，不替代全计划分母的失败率与gap中位数。',
        '复用运行只有原来实际保存的首阶段反事实；没有重建或伪造其后续共同blocks。','',
        '## 图3：满秩谱、有效秩与Adaptive CE','',
        '|算法|A|谱|累计transitions|经验最佳固定k|最低gap|dense gap|adaptive gap|adaptive rank|',
        '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for row in envelopes:
        if row['algorithm']=='NPG' and row['transitions'] not in {sum((13+b)*12 for b in schedule()[:st]) for st in [12,24,36,48]}:continue
        lines.append('|'+ '|'.join([row['algorithm'],row['A_family'],row['spectrum'],str(row['transitions']),str(row['best_fixed_k']),
            fmt(row['best_fixed_gap']),fmt(row['dense_gap']),fmt(row['adaptive_gap']) if row['algorithm']=='CE' else '不适用',
            fmt(row['adaptive_rank']) if row['algorithm']=='CE' else '不适用'])+'|')
    lines+=['','### 平坦谱负对照（各算法自己的最大预算）','',
        '|算法|方法|稳定/24|gap中位数|', '|---|---|---:|---:|']
    for row in flat:
        lines.append(f"|{row['algorithm']}|{row['mode']}|{row['stable_count']}|{fmt(row['failure_inclusive_gap_median'])}|")
    lines+=['','## 解读与复现边界','',
        '两条主要路线分别与自己的dense比较。主图标量A，附录以独立耦合dense A复现；不混用两个A族的统计分母。',
        '上界不是每个有限系统的精确斜率。完整NPG预算变化同时伴随更新次数变化；不能单凭该曲线识别纯统计指数。',
        'Adaptive CE使用c=1的经验split代理，常数未按新正式数据真值调参；它不是已验证的理论置信半径。',
        '满秩系统没有真实冗余方向，head投影损失不叫redundant cost。B尾与当前Z_K尾、有限H偏差分别保存。',
        'NPG固定k不要求整个gain始终rank-k；不声称已验证唯一population floor。',
        '失败按无穷大纳入中位数；所有失败输出见failed_outputs.csv，所有阶段矩阵包含诊断见aggregate.csv。',
        'matched_budget_statistics.csv与endpoint_all_denominators.csv逐单元列出稳定/失败数，不能用稳定子集倍率替代全分母表现。',
        '标量A的旋转实例动力学等价，24重复不是24种独立系统难度。bootstrap仅作描述性区间。',
        '本轮未新增PI学习。匹配实现的历史PI用于附录；有限实验不验证所有算法的minimax下界。',
        '完整原始结果留在Grace，源码/配置/报告/收据保留于E盘。实际核时与账户结算另由accounting.json审计。']
    (report/'findings.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    hashes={p.name:sha(p) for p in report.iterdir() if p.is_file() and p.name!='SHA256SUMS'}
    (report/'SHA256SUMS').write_text(''.join(h+'  '+p+'\n' for p,h in sorted(hashes.items())),encoding='ascii')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['identity','exact_effects','paired_mechanisms','rank_envelopes','flat_endpoints']},indent=2))


if __name__=='__main__':main()
