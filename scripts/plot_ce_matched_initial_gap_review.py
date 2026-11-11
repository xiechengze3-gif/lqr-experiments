"""Read audited CSV values and improve the direct-comparison legend/ticks."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    source=a.source/'report-confirm/fixed_budget_gaps.csv'
    with source.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    ranks=[2,8,32,64,100];assert len(rows)==105
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    fig.subplots_adjust(left=.08,right=.98,bottom=.26,top=.79,wspace=.26)
    colors=plt.get_cmap('tab10').colors
    for i,rank in enumerate(ranks):
        data=[q for q in rows if int(q['rank'])==rank]
        assert len(data)==21
        x=[int(q['transitions']) for q in data]
        axes[0].plot(x,[float(q['full_dense_over_low_trunc_gap_ratio']) for q in data],'-o',markersize=3,color=colors[i],label=f'rank {rank} + truncation')
        axes[0].fill_between(x,[float(q['cross_rank_gap_ci95_low']) for q in data],[float(q['cross_rank_gap_ci95_high']) for q in data],color=colors[i],alpha=.12)
    end=sorted([q for q in rows if int(q['transitions'])==131328],key=lambda q:int(q['rank']))
    y=[float(q['full_dense_over_low_trunc_gap_ratio']) for q in end]
    axes[1].plot(ranks,y,'-o',color='#1476a3')
    for rank,value in zip(ranks,y):
        axes[1].annotate(f'{value:.2f}x',(rank,value),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
    for ax in axes:
        ax.axhline(1,color='.4',ls=':',lw=1)
        ax.set(yscale='log',ylim=(.65,7),ylabel='Gap ratio: full dense / low truncated')
        ax.set_yticks([.75,1,2,3,4,5,6],labels=['0.75','1','2','3','4','5','6'])
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.grid(alpha=.2)
    axes[0].set(xscale='log',xlabel='Common transition budget',title='Same budget | 95% paired-seed bootstrap CI')
    axes[1].set(xlabel='Rank of truncated CE',xticks=ranks,xlim=(-4,108),title='Common endpoint budget 131,328')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,ncol=3,loc='lower center',bbox_to_anchor=(.5,.015),frameon=False,fontsize=9)
    fig.suptitle('Matched initial gap 1 | low-rank truncated CE versus full-rank dense CE\nRatio > 1 favors low rank + truncation',fontsize=12,y=.98)
    name='low_rank_truncated_vs_full_rank_dense'
    fig.savefig(a.output/(name+'.png'),dpi=180,facecolor='white')
    fig.savefig(a.output/(name+'.svg'),facecolor='white');plt.close(fig)
    (a.output/'source.json').write_text(json.dumps(dict(input_csv=str(source),input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        data_modified=False,changes=['Move legend below plots','Label log-axis ticks explicitly','Annotate endpoint ratios'],new_learning_transitions=0),indent=2)+'\n',encoding='utf-8')
    print('Revised direct comparison saved:',a.output)


if __name__=='__main__':main()
