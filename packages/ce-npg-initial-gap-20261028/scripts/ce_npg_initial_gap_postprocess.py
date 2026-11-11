"""Read-only normalization of archived output tables; no learning/model/simulator imports."""
import collections
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import statistics
import sys
import time

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[1]
CFG_PATH=ROOT/'configs/ce_npg_initial_gap_postprocess_20261028.json'
CFG=json.loads(CFG_PATH.read_text(encoding='utf-8'))
BASE=Path('/scratch/user/changze/lqr_experiments')
INPUT=BASE/'results'/CFG['input_study']/'report'
OUT=BASE/'results'/CFG['name']
GROUP_FIELDS=['algorithm','A_family','spectrum','n','r','mode']
METRICS=['absolute','relative_initial']
COLORS={'dense':'#53687b','truncated':'#008c83','adaptive':'#cb741d',
        'k2':'#008c83','k4':'#8b57a0','k8':'#c08628'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(path)


def write_csv(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(rows)


def parse_row(raw):
    row={}
    for key,value in raw.items():
        if value=='':row[key]=None
        elif value in ['True','False']:row[key]=value=='True'
        else:
            try:row[key]=json.loads(value)
            except (ValueError,TypeError):row[key]=value
    return row


def key_for(row):return tuple(row[k] for k in GROUP_FIELDS)


def metric_value(row,metric):
    if not row['stable']:return math.inf
    return row['absolute_gap'] if metric=='absolute' else row['relative_initial_gap']


def load_inputs():
    hashes={name:sha(INPUT/name) for name in CFG['input_files_sha256']}
    assert hashes==CFG['input_files_sha256'],'Input identity mismatch: preserve original report'
    certificates=json.loads((INPUT/'system_certificates.json').read_text(encoding='utf-8'))
    baselines={c['task_id']:c for c in certificates}
    assert len(baselines)==2064==len(certificates)
    physical={};denominators=[]
    for task,c in baselines.items():
        initial=c['initial_gap']
        assert math.isfinite(initial) and initial>0,('Undefined normalization',task,initial)
        assert math.isclose(initial,c['J0']-c['Jstar'],rel_tol=1e-10,abs_tol=1e-10)
        key=tuple(c[k] for k in ['A_family','spectrum','n','r','system'])
        if key in physical:assert math.isclose(initial,physical[key],rel_tol=1e-12,abs_tol=1e-12)
        physical[key]=initial
        denominators.append({k:c[k] for k in ['task_id','algorithm','A_family','spectrum','n','r','system','trial','J0','Jstar','initial_gap']})
    rows=[];max_relative_mismatch=0.
    with (INPUT/'all_records.csv').open(encoding='utf-8',newline='') as stream:
        for raw in csv.DictReader(stream):
            row=parse_row(raw);c=baselines[row['task_id']]
            for k in ['algorithm','A_family','spectrum','n','r','system','trial']:assert row[k]==c[k]
            stable=bool(row['stable']);initial=c['initial_gap']
            gap=row['gap'] if stable else None
            if stable:
                assert gap is not None and math.isfinite(gap) and gap>=0
                relative=gap/initial;stored=row['relative_gap']
                assert stored is not None and math.isfinite(stored)
                difference=abs(relative-stored)/max(1.,abs(relative))
                max_relative_mismatch=max(max_relative_mismatch,difference)
                assert difference<1e-10,('Saved relative gap disagrees with per-instance denominator',row['task_id'])
            else:relative=None
            item={k:row.get(k) for k in GROUP_FIELDS+['task_id','system','trial','transitions','N','stage']}
            item.update(stable=stable,initial_gap=initial,absolute_gap=gap,relative_initial_gap=relative,
                failure_inclusive_absolute_gap=gap if stable else 'inf',
                failure_inclusive_relative_gap=relative if stable else 'inf',
                failure=row.get('failure'),actual_transitions_at_output=row.get('actual_transitions_at_output'))
            rows.append(item)
    assert len(rows)==96600
    trajectories=collections.defaultdict(list)
    for row in rows:trajectories[(row['task_id'],row['mode'])].append(row)
    failed_paths=[]
    for key,values in trajectories.items():
        values.sort(key=lambda r:r['transitions'])
        if values[0]['algorithm']!='NPG':continue
        assert len(values)==49
        failed=False
        for row in values:
            assert not (failed and row['stable']),'Failure absorption lost'
            failed=failed or not row['stable']
            if row['stage']==0:assert row['stable'] and math.isclose(row['relative_initial_gap'],1.,rel_tol=1e-10)
        if failed:failed_paths.append(key)
    assert len(failed_paths)==228
    return rows,denominators,trajectories,hashes,max_relative_mismatch


def aggregate(rows):
    groups=collections.defaultdict(list)
    for row in rows:groups[(key_for(row),row['transitions'])].append(row)
    result=[]
    for (key,budget),values in groups.items():
        assert len(values)==24
        row=dict(zip(GROUP_FIELDS,key));stable=[r for r in values if r['stable']]
        initial=[r['initial_gap'] for r in values]
        row.update(transitions=budget,N=values[0]['N'],stage=values[0]['stage'],count=24,
            stable_count=len(stable),failed_count=24-len(stable),stable_fraction=len(stable)/24,
            initial_gap_min=min(initial),initial_gap_median=statistics.median(initial),initial_gap_max=max(initial))
        for metric in METRICS:
            median=statistics.median(metric_value(r,metric) for r in values)
            finite=[metric_value(r,metric) for r in stable]
            row[metric+'_median']=None if math.isinf(median) else median
            row[metric+'_median_is_infinite']=math.isinf(median)
            row[metric+'_stable_median']=statistics.median(finite) if finite else None
            row[metric+'_stable_q25']=float(np.quantile(finite,.25)) if finite else None
            row[metric+'_stable_q75']=float(np.quantile(finite,.75)) if finite else None
        assert row['absolute_median_is_infinite']==row['relative_initial_median_is_infinite']==(len(stable)<=12)
        result.append(row)
    assert len(result)==4025
    return result,groups


def attainment(rows,trajectories,groups):
    cohorts=collections.defaultdict(list)
    for (key,budget),values in groups.items():cohorts[key].append((budget,values))
    attained=[];paired=[]
    for key,points in cohorts.items():
        points.sort(key=lambda p:p[0]);maximum=points[-1][0]
        initial=[r['initial_gap'] for r in points[-1][1]]
        all_targets={}
        for epsilon in CFG['relative_targets']:
            for metric in METRICS:
                successes=[(budget,sum(metric_value(r,metric)<=epsilon for r in values)) for budget,values in points]
                first=next(((b,c) for b,c in successes if c>=22),None)
                row=dict(zip(GROUP_FIELDS,key));row.update(metric=metric,epsilon=epsilon,cohort_count=24,required_success_count=22,
                    attainment_transitions=first[0] if first else None,success_count_at_attainment=first[1] if first else None,
                    right_censored=first is None,censoring_budget=maximum if first is None else None,
                    maximum_measured_budget=maximum,maximum_success_count=max(c for _,c in successes),
                    success_count_at_maximum=successes[-1][1],stable_count_at_maximum=sum(r['stable'] for r in points[-1][1]),
                    initial_gap_min=min(initial),initial_gap_median=statistics.median(initial),initial_gap_max=max(initial),
                    equivalent_absolute_tolerance_min=epsilon if metric=='absolute' else epsilon*min(initial),
                    equivalent_absolute_tolerance_max=epsilon if metric=='absolute' else epsilon*max(initial))
                attained.append(row);all_targets[metric,epsilon]=row
            absolute=all_targets['absolute',epsilon];relative=all_targets['relative_initial',epsilon]
            row=dict(zip(GROUP_FIELDS,key));row.update(epsilon=epsilon,cohort_count=24,
                absolute_attainment_transitions=absolute['attainment_transitions'],absolute_right_censored=absolute['right_censored'],
                relative_attainment_transitions=relative['attainment_transitions'],relative_right_censored=relative['right_censored'],
                maximum_measured_budget=maximum,initial_gap_min=min(initial),initial_gap_median=statistics.median(initial),initial_gap_max=max(initial),
                relative_equivalent_absolute_tolerance_min=epsilon*min(initial),relative_equivalent_absolute_tolerance_max=epsilon*max(initial),
                absolute_success_count_at_maximum=absolute['success_count_at_maximum'],relative_success_count_at_maximum=relative['success_count_at_maximum'],
                stable_count_at_maximum=absolute['stable_count_at_maximum'])
            paired.append(row)
    assert len(attained)==1038 and len(paired)==519
    # Exact equality to the original absolute-precision report prevents criterion drift.
    index={(key_for(r),r['metric'],r['epsilon']):r for r in attained}
    old=list(csv.DictReader((INPUT/'fixed_accuracy.csv').open(encoding='utf-8')))
    for raw in old:
        r=parse_row(raw);r['spectrum']='exact';new=index[key_for(r),'absolute',r['epsilon']]
        assert new['attainment_transitions']==r['attainment_transitions']
        assert new['right_censored']==r['censored']
    assert len(old)==144
    per_run=[]
    for (task,mode),values in trajectories.items():
        for metric in METRICS:
            for epsilon in CFG['relative_targets']:
                success=[metric_value(r,metric)<=epsilon for r in values]
                first=next((r['transitions'] for r,yes in zip(values,success) if yes),None)
                confirm=None
                if values[0]['algorithm']=='NPG':
                    confirm=next((values[i+3]['transitions'] for i in range(len(values)-3) if all(success[i:i+4])),None)
                failed=[r['transitions'] for r in values if not r['stable']]
                row={k:values[0][k] for k in GROUP_FIELDS+['task_id','system','trial']}
                row.update(metric=metric,epsilon=epsilon,initial_gap=values[0]['initial_gap'],
                    first_attainment_transitions=first,right_censored=first is None,
                    censoring_budget=values[-1]['transitions'] if first is None else None,
                    maximum_measured_budget=values[-1]['transitions'],four_point_confirmation_transitions=confirm,
                    final_stable=values[-1]['stable'],final_success=success[-1],ever_failed=bool(failed),
                    first_failure_transitions=failed[0] if failed else None,
                    first_attained_but_later_failed=first is not None and bool(failed))
                per_run.append(row)
    assert len(per_run)==24912
    return attained,paired,per_run


def select(rows,**filters):return [r for r in rows if all(r.get(k)==v for k,v in filters.items())]


def draw(ax,values,mode,metric,label=None,color=None,offset=0):
    values=sorted(select(values,mode=mode),key=lambda r:r['transitions'])
    if not values:return
    xs=[r['transitions'] for r in values];ys=[r[metric+'_median'] if r[metric+'_median'] is not None else np.nan for r in values]
    color=color or COLORS.get(mode,'#8874a0')
    ax.plot(xs,ys,'o-',ms=2.6,lw=1.5,color=color,label=label or mode.title())
    lo=[r[metric+'_stable_q25'] if r['stable_count']==24 else np.nan for r in values]
    hi=[r[metric+'_stable_q75'] if r['stable_count']==24 else np.nan for r in values]
    ax.fill_between(xs,lo,hi,color=color,alpha=.1)
    if values[-1][metric+'_median_is_infinite']:
        ax.text(xs[-1],.94-offset*.09,'∞',transform=ax.get_xaxis_transform(),ha='right',va='top',color=color,fontsize=12)


def style(ax,metric):
    ax.set_xscale('symlog',linthresh=200);ax.set_yscale('log');ax.grid(alpha=.18,which='both')
    ax.set_xlabel('Transitions (all burn / baseline counted)')
    ax.set_ylabel('Absolute gap' if metric=='absolute' else 'Gap / own initial gap')
    if metric=='relative_initial':ax.axhline(1.,ls=':',color='#aaa',lw=.8)


def save(fig,report,name):
    fig.savefig(report/(name+'.png'),dpi=190,bbox_inches='tight')
    fig.savefig(report/(name+'.svg'),bbox_inches='tight');plt.close(fig)


def learning_figure(report,agg,algorithm,family,cells,name):
    fig,axes=plt.subplots(2,len(cells),figsize=(4.4*len(cells),7.3),squeeze=False,layout='constrained')
    for j,(n,rank) in enumerate(cells):
        values=select(agg,algorithm=algorithm,A_family=family,spectrum='exact',n=n,r=rank)
        for i,metric in enumerate(METRICS):
            ax=axes[i,j]
            for offset,mode in enumerate(['dense','truncated']):draw(ax,values,mode,metric,offset=offset)
            style(ax,metric);ax.set_xlim(0,max(r['transitions'] for r in values)*1.08)
            ax.set_title(f'{algorithm}, n=m={n}, r={rank} | '+('absolute' if metric=='absolute' else 'initial-gap normalized'))
            final=[max(select(values,mode=mode),key=lambda r:r['transitions']) for mode in ['dense','truncated']]
            ax.text(.02,.02,' / '.join(r['mode'].title()+f": {r['stable_count']}/24 stable" for r in final),
                transform=ax.transAxes,fontsize=7,bbox=dict(facecolor='white',edgecolor='none',alpha=.85))
    axes[0,0].legend(fontsize=8)
    fig.suptitle(f'{algorithm}: same saved policies, absolute and relative progress | {family} A')
    fig.text(.5,-.015,'Each point includes all 24 repeats. Failures count as infinity; no survivor-only median. Shading is shown only when all outputs are stable.',ha='center',fontsize=7)
    save(fig,report,name)


def budget_figure(report,attained,family,name):
    fig,axes=plt.subplots(2,2,figsize=(12,7.5),layout='constrained')
    palette={.1:'#4378a7',.03:'#c57b2a',.01:'#9567a6'}
    legend=[]
    for i,algorithm in enumerate(['CE','NPG']):
        for j,metric in enumerate(METRICS):
            ax=axes[i,j];ceiling=[]
            for epsilon in CFG['relative_targets']:
                for mode,marker,ls in [('dense','s','--'),('truncated','o','-')]:
                    data=[next(r for r in attained if all(r[k]==v for k,v in dict(
                        algorithm=algorithm,A_family=family,spectrum='exact',r=2,n=n,mode=mode,metric=metric,epsilon=epsilon).items())) for n in [12,24,48]]
                    ax.plot([r['n'] for r in data],[r['attainment_transitions'] if not r['right_censored'] else np.nan for r in data],
                        marker=marker,linestyle=ls,color=palette[epsilon],ms=4,lw=1.3)
                    censored=[r for r in data if r['right_censored']]
                    if censored:ax.scatter([r['n'] for r in censored],[r['censoring_budget'] for r in censored],
                        marker='^',facecolors='none',edgecolors=palette[epsilon],s=55,zorder=4)
                    ceiling.extend(r['maximum_measured_budget'] for r in data)
                    if i==0 and j==0:legend.append(Line2D([],[],color=palette[epsilon],marker=marker,ls=ls,label=f'{mode.title()}, eps={epsilon:g}'))
            ax.set(xlabel='n=m (r=2)',ylabel='Transitions to >=22/24 observed success',title=f'{algorithm}: '+('absolute precision' if metric=='absolute' else 'fraction of own initial gap'))
            ax.set_yscale('log');ax.set_xlim(10,50);ax.set_xticks([12,24,48]);ax.grid(alpha=.18,which='both')
            ax.set_ylim(top=max(ceiling)*2)
    legend.append(Line2D([],[],color='#555',marker='^',ls='none',markerfacecolor='none',label='Censored at maximum measured budget'))
    fig.legend(handles=legend,ncol=4,loc='lower center',bbox_to_anchor=(.5,-.07),fontsize=7)
    fig.suptitle('Fixed-precision budgets: absolute vs initial-gap normalized | '+family+' A')
    fig.text(.5,-.10,'Hollow triangles are NOT attained budgets. Failed and stable-but-inaccurate runs remain in all denominators; no interpolation or extrapolation.',ha='center',fontsize=7)
    save(fig,report,name)


def fullrank_figure(report,agg,family,name):
    fig,axes=plt.subplots(4,2,figsize=(11,12),layout='constrained')
    for i,(algorithm,spectrum) in enumerate([(a,s) for a in ['CE','NPG'] for s in ['gapped','smooth']]):
        rows=select(agg,algorithm=algorithm,A_family=family,spectrum=spectrum,n=16)
        modes=['dense','k2','k4','adaptive'] if algorithm=='CE' else ['dense','k2','k4','k8']
        for j,metric in enumerate(METRICS):
            ax=axes[i,j]
            for offset,mode in enumerate(modes):draw(ax,rows,mode,metric,offset=offset)
            style(ax,metric);ax.set_title(f'{algorithm}, {spectrum}, n=m=16 | '+('absolute' if metric=='absolute' else 'initial-gap normalized'))
            ax.legend(fontsize=7)
    fig.suptitle('Full-rank saved learning paths | '+family+' A | adaptive CE only')
    save(fig,report,name)


def flat_figure(report,agg):
    fig,axes=plt.subplots(2,2,figsize=(11,7.5),layout='constrained')
    for i,algorithm in enumerate(['CE','NPG']):
        rows=select(agg,algorithm=algorithm,A_family='scalar',spectrum='flat',n=16)
        for j,metric in enumerate(METRICS):
            for offset,mode in enumerate(['dense','k2','k8']+(['adaptive'] if algorithm=='CE' else [])):
                draw(axes[i,j],rows,mode,metric,offset=offset)
            style(axes[i,j],metric);axes[i,j].set_title(algorithm+' flat spectrum | '+metric.replace('_',' '));axes[i,j].legend(fontsize=7)
    fig.suptitle('Flat-spectrum control: the same saved gains in both metrics')
    save(fig,report,'appendix_flat_absolute_relative')


def fmt(value):return 'NR' if value is None else f'{value:,.0f}'


def main():
    assert os.environ.get('SLURM_JOB_ID'),'Numerical reporting must run on a real Grace compute node'
    start=time.monotonic();report=OUT/'report';report.mkdir(parents=True,exist_ok=True)
    assert not (report/'summary.json').exists(),'Completed postprocessing exists; verify instead of replaying'
    rows,baselines,trajectories,hashes,mismatch=load_inputs();agg,groups=aggregate(rows)
    attained,paired,per_run=attainment(rows,trajectories,groups)
    write_csv(report/'normalized_records.csv',rows);write_csv(report/'initial_gap_by_task.csv',baselines)
    write_csv(report/'aggregate_absolute_relative.csv',agg);write_csv(report/'attainment_absolute_relative.csv',attained)
    write_csv(report/'attainment_side_by_side.csv',paired);write_csv(report/'per_run_attainment_and_censoring.csv',per_run)
    write_csv(report/'censored_cohorts.csv',[r for r in attained if r['right_censored']])
    write_csv(report/'failed_outputs_preserved.csv',[r for r in rows if not r['stable']])
    plt.rcParams.update({'font.size':8.2,'axes.spines.top':False,'axes.spines.right':False})
    dimensions=[(12,2),(24,2),(48,2)];ranks=[(24,r) for r in [1,2,4,8]]
    for family in ['scalar','dense']:
        prefix='' if family=='scalar' else 'appendix_'
        for algorithm in ['CE','NPG']:
            learning_figure(report,agg,algorithm,family,dimensions,prefix+'figure_'+algorithm.lower()+'_absolute_relative')
            learning_figure(report,agg,algorithm,family,ranks,'appendix_'+algorithm.lower()+'_rank_absolute_relative_'+family)
        budget_figure(report,attained,family,prefix+'figure_fixed_precision_budgets')
        fullrank_figure(report,agg,family,'appendix_fullrank_absolute_relative_'+family)
    flat_figure(report,agg)
    inputs_after={name:sha(INPUT/name) for name in hashes};assert inputs_after==hashes
    censor_counts={metric:sum(r['right_censored'] for r in attained if r['metric']==metric) for metric in METRICS}
    summary=dict(status='PASS',operation='saved-table postprocessing only',normalization=CFG['normalization'],
        input_rows=len(rows),input_trajectories=len(baselines),variant_paths=len(trajectories),aggregate_rows=len(agg),
        all_NPG_unstable_paths_retained=228,failed_output_rows=sum(not r['stable'] for r in rows),
        initial_gap_min=min(r['initial_gap'] for r in baselines),initial_gap_max=max(r['initial_gap'] for r in baselines),
        per_instance_normalization_before_aggregation=True,saved_relative_gap_maximum_scaled_mismatch=mismatch,
        original_absolute_budget_rows_reproduced_exactly=144,cohort_threshold_rows=len(attained),per_run_threshold_rows=len(per_run),
        censored_cohort_thresholds=censor_counts,targets=CFG['relative_targets'],cohort_success_requirement='>=22 of all 24 repeats',
        new_learning_runs=0,new_training_transitions=0,new_control_solves=0,original_inputs_unchanged=True,
        input_files_sha256=hashes,source_sha256=sha(Path(__file__)),config_sha256=sha(CFG_PATH),
        elapsed_seconds=time.monotonic()-start,
        provenance=dict(job=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),
            cpus=os.environ.get('SLURM_CPUS_PER_TASK'),temp=os.environ['TMPDIR'],cache=os.environ['XDG_CACHE_HOME']))
    atomic_json(report/'summary.json',summary)
    lines=['# 初始gap归一化：CE/NPG已有结果补充（2026-10-28）','',
        '逐次定义 relative=(J(K)-Jstar)/(J(K0)-Jstar)，先归一化再汇总；absolute为J(K)-Jstar。',
        '读取全部96,600个已保存输出和2,064个已有任务基线；新增学习运行、训练transitions及控制求解均为0。',
        '相对精度为10%/3%/1%。每个设置的全24重复中至少22个达标才记该预算达到90%观察成功率。',
        '失稳作为正无穷纳入；未达标记NR并保留最大已测预算，不删除失败、不插值、不外推。',
        '不同设置的相对目标对应不同绝对容差；二者是在回答不同的精度问题。',
        f"全部228条NPG失稳路径及其{summary['failed_output_rows']}个失败阶段输出保留。原absolute预算144行逐项完全复现。",'',
        '## 固定r=2、epsilon=0.1：absolute与relative并列','',
        '|A|算法|n|方法|初始gap中位数|absolute达标预算|relative达标预算|relative最大预算成功数/24|',
        '|---|---|---:|---|---:|---:|---:|---:|']
    for r in paired:
        if r['spectrum']=='exact' and r['r']==2 and r['mode'] in ['dense','truncated'] and r['epsilon']==.1:
            lines.append(f"|{r['A_family']}|{r['algorithm']}|{r['n']}|{r['mode']}|{r['initial_gap_median']:.6g}|{fmt(r['absolute_attainment_transitions'])}|{fmt(r['relative_attainment_transitions'])}|{r['relative_success_count_at_maximum']}|")
    lines+=['','## 已完成图表与完整记录','',
        '主图：figure_ce_absolute_relative、figure_npg_absolute_relative、figure_fixed_precision_budgets；同时保存PNG与SVG。',
        '耦合A复现、n24的四秩扫描、两类满秩谱及平坦谱均有并列图；所有设置和方法都保留在完整统计表。',
        'attainment_side_by_side.csv给出同一个数值epsilon下两种定义的预算，以及相对目标对应的绝对容差范围。',
        'per_run_attainment_and_censoring.csv保留全部个体未达标和失稳记录；NPG另给连续4点确认预算。',
        '首个达标点是离线评估，不改变原输出、停止点或迭代。首次达标不保证所有后续点持续达标；个体后续失稳标志单独保存。',
        '误差带仅在全部24重复稳定时绘制稳定样本IQR；部分失败时仍用失败计入后的中位数，绝不以幸存者中位数替换。',
        '本归一化没有改变任何同一系统的dense/truncated逐对gap倍率；跨系统聚合排序和固定精度预算可以改变。',
        '如果初始gap为0，该归一化未定义；本数据所有基线严格为正，未使用分母截断。',
        '所有原始输入哈希在前后均核对一致；费用由本后处理作业单独记录，不声称新增了学习证据。']
    (report/'findings.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    files={p.name:sha(p) for p in report.iterdir() if p.is_file() and p.name!='SHA256SUMS'}
    (report/'SHA256SUMS').write_text(''.join(d+'  '+name+'\n' for name,d in sorted(files.items())),encoding='ascii')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
