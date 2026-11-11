"""Plot the sealed nine-rung paired ratios and arm stability counts."""
import csv
import math
import os
from pathlib import Path


R=Path(__file__).resolve().parent
cache=R/'plot-cache-v1'
cache.mkdir()
os.environ['MPLCONFIGDIR']=str(cache)
os.environ['TMP']=os.environ['TEMP']=str(cache)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np


def main():
    with (R/'X9_summary_merged_nine_rungs.csv').open(newline='',encoding='utf-8-sig') as f:
        by={(r['algorithm'],float(r['alpha']),round(-math.log2(float(r['rung'])))):r
            for r in csv.DictReader(f) if r['ratio_kind']=='both_stable'}
    alphas=sorted({k[1] for k in by})
    colors=['#282828','#1b8197','#448942','#a76813','#a44473','#694ca3']
    ticks=list(range(8,-1,-1))
    labels=[f'1/{2**j}' if j else '1' for j in ticks]
    fig,axes=plt.subplots(2,2,figsize=(11.5,6.5),layout='constrained',height_ratios=(2,1))
    for col,alg in enumerate(('NPG','PI')):
        ax,stable=axes[:,col]
        ax.axhline(1,color='.55',linestyle='--',linewidth=1)
        counts=[]
        for alpha,color in zip(alphas,colors):
            rows=[by[alg,alpha,j] for j in ticks]
            y,lo,hi=([float(r[k]) if r[k] else np.nan for r in rows]
                     for k in ('paired_ratio_median','ci_low','ci_high'))
            ax.plot(range(9),y,label=f'{alpha:g}',color=color,marker='o',ms=4)
            ax.fill_between(range(9),lo,hi,color=color,alpha=.15)
            counts.append([int(r['both_stable']) for r in rows])
            for i,r in enumerate(rows):
                text_color='white' if counts[-1][i]<12 else '#1d2430'
                stable.text(i,len(counts)-1,f"{r['dense_stable']}/{r['truncated_stable']}",
                            ha='center',va='center',fontsize=8,color=text_color)
        stable.imshow(counts,aspect='auto',cmap='Blues_r',norm=Normalize(0,32),interpolation='none')
        stable.set_xticks(range(9),labels)
        stable.set_yticks(range(len(alphas)),[f'{alpha:g}' for alpha in alphas])
        stable.set_xlabel('Fraction of calibrated budget')
        ax.set_xlim(-.5,8.5)
        ax.set_xticks([])
        ax.set_yscale('log')
        ax.set_title(alg)
        ax.grid(axis='y',alpha=.16)
        if col==0:
            ax.set_ylabel('Paired gap ratio (dense / truncated)')
            stable.set_ylabel('Tail α')
        ax.legend(title='Tail α',ncol=2,fontsize=8,loc='best')
    fig.suptitle('Paired ratios among stable runs and dense / truncated stable counts out of 32')
    for suffix in ('png','svg'):
        path=R/f'X14_nine_rung_preview.{suffix}'
        with path.open('xb') as f:
            fig.savefig(f,format=suffix,dpi=180)
    plt.close(fig)


if __name__=='__main__':
    main()
