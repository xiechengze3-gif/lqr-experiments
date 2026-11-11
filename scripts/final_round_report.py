"""Figures A-D and auditable system-level tables; no trajectory simulation."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dense_scaling import atomic_json
from final_npg_audit import write_csv

COLORS=dict(dense='#636363',known_rank='#0072B2',adaptive='#D55E00',forced_rank4='#CC79A7')
LABELS=dict(dense='Dense + PSD',known_rank='Known rank + joint SVD',adaptive='Data-only adaptive',forced_rank4='Forced rank 4')


def load_csv(path):
    with Path(path).open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))


def save(fig,out,name):
    fig.savefig(out/(name+'.png'),dpi=220,bbox_inches='tight')
    fig.savefig(out/(name+'.svg'),bbox_inches='tight');plt.close(fig)


def interval(values):
    # Resample independent systems, after averaging any data repeats within system.
    values=np.asarray(values,dtype=float);rng=np.random.default_rng(20261014)
    bootstrap=np.median(values[rng.integers(len(values),size=(2000,len(values)))],axis=1)
    return float(np.median(values)),np.quantile(bootstrap,[.025,.975],method='nearest')


def run(out):
    report=out/'report';report.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'svg.fonttype':'none','font.family':'DejaVu Sans'})
    fixed=[]
    for path in (out/'scaling').glob('*.json'):
        rows=json.loads(path.read_text()).get('rows',[])
        for row in rows:
            row['head_rank']=row['r'];row['algebraic_rank']=row['n'] if row['tau']>0 else row['r']
            row['diagnostic_only']=row['ablation']!='both_estimated'
        fixed+=rows
    actual=[r for r in fixed if r['ablation']=='both_estimated']
    write_csv(report/'fixed_policy.csv',fixed)
    central=[r for r in actual if r['n']==50 and r['r']==4 and r['tau']==0]
    fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    for ax,key,title in zip(axes,['G_error_fro2','Z_error_fro2'],['Curvature G','Residual Z']):
        for method in COLORS:
            selected=[r for r in central if r['method']==method]
            if not selected:continue
            xs=sorted({r['transitions'] for r in selected});ys=[]
            for x in xs:ys.append(np.mean([r[key] for r in selected if r['transitions']==x]))
            ax.loglog(xs,ys,'o-',color=COLORS[method],label=LABELS[method])
        ax.set(xlabel='Primitive transitions',ylabel='Squared Frobenius error',title=title);ax.grid(alpha=.2)
    axes[0].legend(fontsize=8);fig.suptitle('A  Matched fixed-policy Direct-Stein estimates (50d, rank 4)')
    fig.tight_layout();save(fig,report,'Figure_A')
    core=[];endpoints=[]
    for path in (out/'core').glob('n*.json'):
        data=json.loads(path.read_text());meta=data['meta'];last=data['rows'][-1]
        completed=meta['status']=='completed'
        endpoints.append(dict(meta,g=last['normalized_gap'],gap=last['gap'],
            stable=completed,success=bool(completed and last['normalized_gap']<=.1)))
        core.extend(dict(meta,**row) for row in data['rows'])
    write_csv(report/'learning_curves.csv',core);write_csv(report/'endpoints.csv',endpoints)
    budgets=sorted({r['blocks'] for r in endpoints});summary=[]
    fig,axes=plt.subplots(2,max(1,len(budgets)),figsize=(5*max(1,len(budgets)),7),squeeze=False)
    for j,budget in enumerate(budgets):
        ax=axes[0,j];bottom=axes[1,j]
        for method in ('dense','known_rank','adaptive'):
            selected=[r for r in core if r['blocks']==budget and r['method']==method]
            xs=[];med=[];lower=[];upper=[]
            for stage in range(9):
                rows=[r for r in selected if r['stage']==stage]
                by_system=defaultdict(list)
                for row in rows:by_system[row['system_seed']].append(row['normalized_gap'] if row['normalized_gap'] is not None else np.inf)
                for end in endpoints:
                    if end['blocks']==budget and end['method']==method and end['status']!='completed':
                        last_stage=max(r['stage'] for r in selected if r['system_seed']==end['system_seed'] and r['sampling_seed']==end['sampling_seed'])
                        if stage>last_stage:by_system[end['system_seed']].append(np.inf)
                if not by_system:continue
                values=[np.mean(v) for v in by_system.values()]
                center,ci=interval(values)
                xs.append(stage*(512+(budget+1)*16));med.append(center);lower.append(ci[0]);upper.append(ci[1])
            ax.semilogy(xs,med,'o-',color=COLORS[method],label=LABELS[method],markersize=3)
            ax.fill_between(xs,lower,upper,color=COLORS[method],alpha=.12)
            ends=[r for r in endpoints if r['blocks']==budget and r['method']==method]
            if not ends:continue
            summary.append(dict(blocks=budget,method=method,systems=len({r['system_seed'] for r in ends}),
                runs=len(ends),success=sum(r['success'] for r in ends),stable=sum(r['stable'] for r in ends),
                numerical_failures=sum(r['status']=='numerical_failure' for r in ends),
                controller_instabilities=sum(r['status']=='controller_instability' for r in ends),
                planned_transitions=ends[0]['planned_transitions'],
                median_g=(lambda x:float(x) if np.isfinite(x) else None)(np.median([r['g'] if r['g'] is not None else np.inf for r in ends]))))
        ax.axhline(.1,color='black',ls='--',lw=1);ax.set(title=f'{budget:,} blocks per update',xlabel='Primitive transitions',ylabel='Normalized gap g');ax.grid(alpha=.2)
        rows=[r for r in summary if r['blocks']==budget];x=np.arange(3)
        lookup={r['method']:r for r in rows}
        bottom.bar(x-.18,[lookup[m]['success']/lookup[m]['runs'] if m in lookup else np.nan for m in ('dense','known_rank','adaptive')],.36,label='Target success',color='#56B4E9')
        bottom.bar(x+.18,[lookup[m]['stable']/lookup[m]['runs'] if m in lookup else np.nan for m in ('dense','known_rank','adaptive')],.36,label='Completed and stable',color='#009E73')
        bottom.set(xticks=x,xticklabels=['Dense','Known rank','Adaptive'],ylim=(0,1.05),ylabel='Fraction of all runs')
    if budgets:axes[0,0].legend(fontsize=8);axes[1,0].legend(fontsize=8)
    draft=f'DRAFT {len(endpoints)}/72 trajectories returned: ' if len(endpoints)!=72 else ''
    fig.suptitle(draft+'B  Damped Direct-Stein PI, fixed 8 updates, common step 0.25\nMedian and system bootstrap 95% interval; failures remain in denominators')
    fig.tight_layout();save(fig,report,'Figure_B')
    write_csv(report/'core_summary.csv',summary)
    attainment=[]
    for seed in sorted({r['system_seed'] for r in endpoints}):
        for method in ('dense','known_rank','adaptive'):
            rows=[r for r in endpoints if r['system_seed']==seed and r['method']==method]
            if not rows:continue
            successful=[r for r in rows if r['success']]
            attainment.append(dict(system_seed=seed,method=method,
                sampled_budget=min(r['planned_transitions'] for r in successful) if successful else max(r['planned_transitions'] for r in rows),
                right_censored=not bool(successful),left_grid_censored=bool(successful and min(r['blocks'] for r in successful)==budgets[0]),
                instability_events=sum(r['status']=='controller_instability' for r in rows),
                numerical_failures=sum(r['status']=='numerical_failure' for r in rows),
                definition='minimum tested budget with fixed final g<=.1; no interpolation or online stopping'))
    write_csv(report/'sample_to_accuracy.csv',attainment)
    if attainment:
        fig,ax=plt.subplots(figsize=(8,4.8));seeds=sorted({r['system_seed'] for r in attainment})
        for index,method in enumerate(('dense','known_rank','adaptive')):
            selected=[r for r in attainment if r['method']==method]
            for row in selected:
                ax.scatter(row['sampled_budget']/1e6,seeds.index(row['system_seed'])+(index-1)*.16,
                    marker='>' if row['right_censored'] else 'o',s=48,
                    facecolors='none' if row['right_censored'] else COLORS[method],edgecolors=COLORS[method])
            ax.plot([],[],marker='o',ls='',color=COLORS[method],label=LABELS[method])
        ax.plot([],[],marker='>',ls='',markerfacecolor='none',color='black',label='Maximum budget not attained')
        ax.set(yticks=range(len(seeds)),yticklabels=seeds,ylabel='Independent system seed',
            xlabel='Minimum tested budget (million primitive transitions)',
            title='Sample to g <= 0.1 from fixed final policies\nOpen triangles mark right-censored grid outcomes')
        ax.legend(fontsize=8,loc='best');ax.grid(axis='x',alpha=.2);fig.tight_layout();save(fig,report,'Sample_to_accuracy')
    fig,axes=plt.subplots(1,3,figsize=(14,3.8))
    for ax,dimension in zip(axes[:2],('rank','dimension')):
        candidates=[r for r in actual if r['blocks']==131072 and r['tau']==0 and
                    (r['n']==50 if dimension=='rank' else r['r']==4)]
        for method in COLORS:
            rows=[r for r in candidates if r['method']==method]
            xs=sorted({r['r' if dimension=='rank' else 'n'] for r in rows})
            if not xs:continue
            means=[np.mean([r['G_error_fro2']+r['Z_error_fro2'] for r in rows if r['r' if dimension=='rank' else 'n']==x]) for x in xs]
            if dimension=='rank':
                pairs=[(x,y) for x,y in zip(xs,means) if x<50]
                if pairs:ax.loglog(*zip(*pairs),'o-',label=LABELS[method],color=COLORS[method])
                control=[(x,y) for x,y in zip(xs,means) if x==50]
                if control:ax.loglog(*zip(*control),'s',label=LABELS[method] if not pairs else None,color=COLORS[method])
            else:ax.loglog(xs,means,'o-',label=LABELS[method],color=COLORS[method])
        ax.set(xlabel='System rank' if dimension=='rank' else 'State and action dimension',ylabel='Joint squared error',title=dimension.capitalize()+' sensitivity');ax.grid(alpha=.2)
    for method in ('dense','known_rank','adaptive'):
        rows=[r for r in actual if r['blocks']==131072 and r['n']==50 and r['r']==4 and r['method']==method]
        xs=sorted({r['tau'] for r in rows});ys=[np.mean([r['G_error_fro2']+r['Z_error_fro2'] for r in rows if r['tau']==x]) for x in xs]
        axes[2].plot(xs,ys,'o-',label=LABELS[method],color=COLORS[method])
    axes[2].set(xlabel='Total tail Frobenius norm tau',ylabel='Joint squared error',title='Approximate rank robustness');axes[0].legend(fontsize=7)
    fig.suptitle('C  Fixed-policy estimator dependence, 131,072 blocks, two independent systems\nRank-50 squares: distinct control family; nonzero tails: rank 4 denotes head order')
    fig.tight_layout();save(fig,report,'Figure_C')
    npg=out/'npg-audit';initial=load_csv(npg/'initial_diagnostics.csv');ratios=load_csv(npg/'budget_ratios.csv')
    noisy=load_csv(npg/'initial_noise.csv');curves=load_csv(npg/'normalized_curves.csv');exact=load_csv(npg/'exact_critic.csv')
    fig,axes=plt.subplots(2,2,figsize=(11,8));ranks=sorted({int(r['rank']) for r in initial})
    for key,label in [('initial_gap','Initial absolute gap'),('Z0_fro','Initial residual norm')]:
        axes[0,0].plot(ranks,[np.mean([float(r[key]) for r in initial if int(r['rank'])==rank]) for rank in ranks],'o-',label=label)
    axes[0,0].set(xlabel='System rank',title='Control difficulty changes with rank');axes[0,0].legend(fontsize=8)
    for method,color in [('raw',COLORS['dense']),('truncated',COLORS['known_rank'])]:
        means=[]
        for rank in ranks:
            rows=[r for r in noisy if int(r['rank'])==rank and r['method']==method and int(r['blocks'])==32768]
            means.append(np.mean([float(r['noise_fro2']) for r in rows]))
        axes[0,1].semilogy(ranks,means,'o-',label=method,color=color)
    axes[0,1].set(xlabel='System rank',ylabel='Initial critic error squared',title='Same 32,768 blocks at the initial policy');axes[0,1].legend()
    for rank in (1,4,16,50):
        for method,style in [('raw','-'),('truncated','--')]:
            rows=[r for r in curves if int(r['rank'])==rank and r['method']==method and r['schedule']=='min-32768-final-2097152' and r['g']]
            stages=sorted({int(r['stage']) for r in rows});x=[];y=[]
            for stage in stages:
                values=[r for r in rows if int(r['stage'])==stage]
                x.append(int(values[0]['transitions']));y.append(np.mean([float(r['g']) for r in values]))
            axes[1,0].semilogy(x,y,style,label=f'r={rank} {method}')
    axes[1,0].axhline(.1,color='black',ls=':',lw=1);axes[1,0].set(xlabel='Primitive transitions',ylabel='Mean normalized gap',title='Existing largest-budget stable profile');axes[1,0].legend(fontsize=6,ncol=2)
    axes[1,1].plot(ranks,[float(r['ratio']) for r in ratios],'o-',color='#0072B2')
    axes[1,1].set(xlabel='System rank',ylabel='Dense / truncated budget',title='Fixed final g <= 0.1 on all four systems');axes[1,1].axhline(1,color='gray',ls=':')
    fig.suptitle('D  Archived Stein NPG reanalysis under a common relative precision target')
    fig.tight_layout();save(fig,report,'Figure_D')
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    exact_cross=[]
    for rank in ranks:
        rows=[r for r in exact if int(r['rank'])==rank and r['g']];stages=sorted({int(r['stage']) for r in rows})
        axes[0].semilogy(stages,[np.mean([float(r['g']) for r in rows if int(r['stage'])==stage]) for stage in stages],label=f'r={rank}')
        for seed in range(4):
            seq=[r for r in rows if int(r['system_seed'])==seed and float(r['g'])<=.1]
            exact_cross.append(dict(rank=rank,system_seed=seed,first_iteration=min(int(r['stage']) for r in seq) if seq else None))
    axes[0].axhline(.1,color='black',ls=':');axes[0].set(xlabel='Exact critic iterations',ylabel='Mean normalized gap',title='Oracle optimization diagnostic, zero samples');axes[0].legend(fontsize=7)
    for key,label in [('spectral_margin','Spectral stability margin'),('operator_margin','Operator norm margin')]:
        axes[1].plot(ranks,[np.mean([float(r[key]) for r in initial if int(r['rank'])==rank]) for rank in ranks],'o-',label=label)
    axes[1].set(xlabel='Rank',title='Initial stability margins');axes[1].legend(fontsize=8);fig.tight_layout();save(fig,report,'NPG_exact_diagnostic')
    write_csv(report/'npg_exact_target_iterations.csv',exact_cross)
    rank8=[]
    for path in (out/'rank8').glob('n*.json'):
        data=json.loads(path.read_text());rank8.extend(dict(data['meta'],**row) for row in data['rows'])
    if rank8:
        write_csv(report/'rank8_learning.csv',rank8)
        fig,ax=plt.subplots(figsize=(6,4))
        for method in ('dense','known_rank','adaptive'):
            selected=[r for r in rank8 if r['method']==method]
            xs=[];ys=[]
            for stage in range(9):
                values=[]
                for seed in sorted({r['system_seed'] for r in selected}):
                    rows=[r for r in selected if r['stage']==stage and r['system_seed']==seed]
                    values.append(rows[0]['normalized_gap'] if rows and rows[0]['normalized_gap'] is not None else np.inf)
                if not values:continue
                xs.append(stage*(512+131073*16));ys.append(np.mean(values))
            ax.semilogy(xs,ys,'o-',label=LABELS[method],color=COLORS[method])
        ax.axhline(.1,ls='--',color='black',lw=1);ax.set(xlabel='Primitive transitions',ylabel='Normalized gap g',
            title='Rank 8 actor confirmation: two systems, fixed step and budget\nFailed paths remain nonattainments in the mean')
        ax.legend(fontsize=8);fig.tight_layout();save(fig,report,'Rank8_confirmation')
    atomic_json(report/'summary.json',dict(core=summary,attainment=attainment,
        fixed_estimate_records=len(actual),core_trajectories=len(endpoints),
        status='COMPLETE' if len(endpoints)==72 else 'INCOMPLETE',
        failure_policy='All failures retained; unmet maximum-budget targets right censored',
        uncertainty='System bootstrap for core medians; n=2 scaling is descriptive'))
    print(json.dumps(dict(report=str(report),core_trajectories=len(endpoints),fixed_records=len(actual))),flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
