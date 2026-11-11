"""Presentation-only final plots; preserves frozen learner and statistical tables."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(output):
    out=Path(output); report=out/'report'
    cfg=json.loads((out/'resolved_config.json').read_text(encoding='utf-8'))
    with (report/'curve_statistics.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    with (report/'sample_requirements.csv').open(encoding='utf-8-sig',newline='') as f:thresholds=list(csv.DictReader(f))
    with (report/'summary.csv').open(encoding='utf-8-sig',newline='') as f:summaries=list(csv.DictReader(f))
    colors={'dense':'#b84a39','truncated':'#2168a1'}; labels={'dense':'Dense NPG','truncated':'Rank-4 truncated NPG'}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.grid':True,'grid.alpha':.2,'savefig.dpi':180})
    fig,axes=plt.subplots(2,3,figsize=(14,8),constrained_layout=True)
    total=len(cfg['trial_seeds'])
    for ax,m in zip(axes.flat,cfg['action_dimensions']):
        availability=[]
        for method in cfg['methods']:
            g=[r for r in rows if int(r['m'])==m and r['method']==method]
            x=np.array([int(r['transitions']) for r in g])
            def vector(key):return np.array([float(r[key]) if r[key] else np.nan for r in g])
            ax.plot(x,vector('relative_gap_median'),color=colors[method],label=labels[method])
            ax.fill_between(x,vector('relative_gap_q25'),vector('relative_gap_q75'),color=colors[method],alpha=.18)
            availability.append(f'{method} {g[-1]["stable"]}/{total}')
        ax.axhline(.1,color='black',ls='--',lw=.8)
        ax.set_xscale('symlog',linthresh=40000);ax.set_xlim(0,max(x)*1.05);ax.set_yscale('log')
        ax.set_xticks([0,1e5,1e6,1e7],["0",r"$10^5$",r"$10^6$",r"$10^7$"])
        ax.set_title(f'm={m}, m-r={m-cfg["rank"]}\nFinal stable: '+', '.join(availability),fontsize=10)
        ax.set_xlabel('Cumulative primitive transitions');ax.set_ylabel('Relative optimality gap')
    axes.flat[-1].axis('off');h,l=axes.flat[0].get_legend_handles_labels();axes.flat[-1].legend(h,l,loc='center')
    fig.suptitle('Fixed effective LQR: seed median and interquartile range\nPost-pulse first-order Stein; identical assigned transition budgets',fontsize=14)
    for extension in ('png','pdf'):fig.savefig(report/('relative_gap_curves.'+extension))
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    for index,method in enumerate(cfg['methods']):
        g=[r for r in summaries if r['method']==method]
        x=np.array([int(r['redundant_dimensions']) for r in g])
        for ax,key in zip(axes,('gap','relative_gap')):
            def vector(metric):return np.array([float(r[key+'_'+metric]) if r[key+'_'+metric] else np.nan for r in g])
            y=vector('median');lo=vector('q25');hi=vector('q75')
            ax.errorbar(x,y,yerr=np.array([y-lo,hi-y]),color=colors[method],marker='o',capsize=4,label=labels[method])
            for position,r in zip(x,g):
                if int(r['stable'])==0:
                    ax.text(position,.96-.13*index,f'{method}\n0/{total} stable',
                            ha='center',va='top',color=colors[method],fontsize=8,
                            transform=ax.get_xaxis_transform(),bbox=dict(facecolor='white',alpha=.8,edgecolor='none'))
                elif int(r['stable'])<total:
                    ax.annotate(f"{r['stable']}/{total} stable",(position,float(r[key+'_median'])),
                                xytext=(-8,-18),textcoords='offset points',ha='right',va='top',
                                color=colors[method],fontsize=8,
                                bbox=dict(facecolor='white',alpha=.85,edgecolor='none'))
            ax.set_xscale('log',base=2);ax.set_xticks(x,[str(v) for v in x]);ax.set_xlim(x[0]*.8,x[-1]*1.3)
            ax.set_yscale('log');ax.set_xlabel('Redundant action dimensions (m-r)')
            ax.set_ylabel('Absolute excess cost' if key=='gap' else 'Relative optimality gap')
    axes[0].legend(loc='lower right',fontsize=9)
    fig.suptitle(f'Fixed final budget: {int(rows[-1]["transitions"]):,} primitive transitions per trajectory\nStable-seed median / IQR; failed outputs have no finite cost point')
    for extension in ('png','pdf'):fig.savefig(report/('fixed_budget_excess.'+extension))
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    for ax,method in zip(axes,cfg['methods']):
        g=[r for r in summaries if r['method']==method];x=np.arange(len(g))
        red=np.array([float(r['redundant_loss_mean']) if r['redundant_loss_mean'] else np.nan for r in g])
        eff=np.array([float(r['effective_loss_mean']) if r['effective_loss_mean'] else np.nan for r in g])
        ax.plot(x,eff,'o-',color='#44887a',label='Effective-policy loss')
        ax.plot(x,red,'o-',color='#b68737',label='Redundant-action loss')
        ax.plot(x,red+eff,'s--',color='#555555',label='Total excess cost',lw=1.1,markersize=4)
        ax.set_yscale('log')
        ax.set_xticks(x,[f"{r['m']}\n({r['stable']}/{total})" for r in g])
        ax.set_xlabel('Action dimension m (stable seeds / total)');ax.set_ylabel('Mean absolute excess cost')
        ax.set_title(labels[method]);ax.legend(fontsize=9)
        for pos,r in zip(x,g):
            if int(r['stable'])==0:
                ax.text(pos,.05,'No stable\noutput',ha='center',va='bottom',fontsize=8,
                        transform=ax.get_xaxis_transform())
    fig.suptitle('Offline exact loss decomposition at the final budget\nConditional means on a log scale; redundant + effective = total')
    for extension in ('png','pdf'):fig.savefig(report/('loss_decomposition.'+extension))
    plt.close(fig)
    fig,axes=plt.subplots(1,len(cfg['relative_targets']),figsize=(14,4.8),constrained_layout=True)
    for ax,target in zip(axes,cfg['relative_targets']):
        for method_index,method in enumerate(cfg['methods']):
            g=[r for r in thresholds if r['method']==method and float(r['target'])==target]
            x=np.array([int(r['m']) for r in g]);maximum=np.array([int(r['max_budget']) for r in g])
            attained=np.array([bool(r['sustained_90pct_grid_transitions']) for r in g])
            y=np.array([int(r['sustained_90pct_grid_transitions']) if r['sustained_90pct_grid_transitions'] else int(r['max_budget']) for r in g])
            ax.plot(x,np.where(attained,y,np.nan),'-o',color=colors[method],label=labels[method])
            offset=.95 if method_index==0 else 1.05
            ax.scatter(x[~attained]*offset,maximum[~attained],marker='^',facecolors='none',edgecolors=colors[method],s=70)
        ax.set_title(f'Relative gap <= {target}');ax.set_xscale('log',base=2);ax.set_yscale('log')
        ax.set_xticks(cfg['action_dimensions'],[str(m) for m in cfg['action_dimensions']]);ax.set_xlabel('Action dimension m')
        ax.set_xlim(min(cfg['action_dimensions'])*.8,max(cfg['action_dimensions'])*1.2)
        ax.set_ylabel('Primitive transitions (90% sustained success)');ax.legend(fontsize=8)
    fig.suptitle('Observed sample requirements on the frozen schedule\nOpen triangles (horizontal offset): right-censored at the maximum budget; target not attained')
    for extension in ('png','pdf'):fig.savefig(report/('sample_requirements.'+extension))
    plt.close(fig)
    receipt=dict(source=str(Path(__file__).resolve()),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 purpose='Presentation-only: nonnegative transition axis, sample-requirement plot, explicit no-stable-output labels, stable counts in decomposition and undefined paired win rates as N/A.',
                 inputs={name:hashlib.sha256((report/name).read_bytes()).hexdigest() for name in ('curve_statistics.csv','sample_requirements.csv','summary.csv')},
                 frozen_learner_identity=cfg['identity'])
    findings=report/'findings.md'
    lines=findings.read_text(encoding='utf-8').splitlines()
    for i,line in enumerate(lines):
        cells=line.split('|')
        if len(cells)==7 and cells[2].strip()=='0' and cells[3].strip()=='censored' and cells[5].strip()=='0%':
            cells[5]=' N/A ';lines[i]='|'.join(cells)
    findings.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (report/'figure_provenance.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(figures='PASS',directory=str(report))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.output)
