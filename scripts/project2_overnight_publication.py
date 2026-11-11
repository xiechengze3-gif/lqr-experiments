"""Publication figures from verified saved tables, with explicit stability panels."""
import csv
import json
import os
from pathlib import Path
import sys

BASE=Path('/scratch/user/changze/lqr_experiments')
ROOT=BASE/'releases/project2-overnight-20261020'
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import project2_overnight as science

OUT=BASE/'results/project2-overnight-20261020'


def read_csv(path):
    with path.open(newline='') as f:
        rows=list(csv.DictReader(f))
    for r in rows:
        for key in r:
            if key in ('n','m','r','H','N','seed','trial','value','repetitions'):r[key]=int(r[key])
            elif r[key] and key not in ('variable','method','policy','family'):
                try:r[key]=float(r[key])
                except ValueError:pass
    return rows


def save(fig,folder,name):
    for suffix in ('png','svg'):fig.savefig(folder/(name+'.'+suffix),dpi=180)
    plt.close(fig)


def main():
    science.require_compute();dest=OUT/'publication';dest.mkdir(exist_ok=True)
    main=json.loads((OUT/'report/summary.json').read_text())
    high=json.loads((OUT/'high-budget/report/summary.json').read_text())
    noise_summary=read_csv(OUT/'report/null_noise_summary.csv');noise=read_csv(OUT/'report/null_noise.csv')
    points=read_csv(OUT/'derived/fixed_policy_dimension_rank_points.csv')
    fits=json.loads((OUT/'derived/fixed_policy_fits.json').read_text())['fits']
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    colors={'dense':'#666666','known_rank':'#1676B5','adaptive':'#D77B16'}
    labels={'dense':'Dense','known_rank':'Rank-aware','adaptive':'Adaptive'}
    fig,axes=plt.subplots(1,2,figsize=(10.8,4.2),constrained_layout=True)
    for method in ('dense','known_rank','adaptive'):
        rr=sorted([r for r in main['actor_summary'] if r['method']==method],key=lambda r:r['transitions'])
        x=[r['transitions']/1e6 for r in rr]
        axes[0].plot(x,[r['g_median'] if r['g_median'] is not None else np.nan for r in rr],'o-',color=colors[method],label=labels[method])
        axes[1].plot(x,[r['success']/8 for r in rr],'o-',color=colors[method],label=labels[method])
    axes[0].annotate('8/8 unstable',xy=(12.58608,.97),xycoords=('data','axes fraction'),ha='left',va='top',color=colors['dense'])
    axes[0].axhline(.1,color='black',ls='--',lw=1,label='Target')
    axes[0].set(xscale='log',yscale='log',xlabel='Primitive transitions (million)',ylabel='Final relative gap',title='v4 PI: full greedy step, six updates')
    axes[1].set(xscale='log',xlabel='Primitive transitions (million)',ylabel='Successful systems / 8',ylim=(-.05,1.1),title='Stable path and final gap <= 0.1')
    axes[1].annotate('8/8',xy=(25.168992,1),xytext=(0,6),textcoords='offset points',ha='center',color=colors['known_rank'])
    axes[1].annotate('3/8',xy=(25.168992,3/8),xytext=(0,6),textcoords='offset points',ha='center',color=colors['adaptive'])
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=9)
    save(fig,dest,'Figure_1_v4_PI')
    center=lambda r:r['n']==50 and r['m']==50 and r['r']==4 and r['H']==16 and r['policy']=='Kstar'
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    for h in (4,8,16,32):
        rr=sorted([r for r in noise_summary if r['n']==50 and r['m']==50 and r['r']==4 and r['H']==h and r['policy']=='Kstar'],key=lambda r:r['N'])
        axes[0,0].plot([r['N'] for r in rr],[r['null_Z_fro2_median'] for r in rr],'o-',label='H='+str(h))
    axes[0,0].set(xscale='log',yscale='log',xlabel='Evaluation blocks N',ylabel='Null-space Z error squared',title='Batch and return horizon')
    axes[0,0].legend()
    rr=sorted([r for r in noise_summary if r['n']==r['m'] and r['r']==4 and r['H']==16 and r['policy']=='Kstar' and r['N']==131072],key=lambda r:r['n'])
    for field,style,label in [('null_normalized_median','o-','Empirical Gram'),('known_cov_null_normalized_median','s--','Exact pulse-design covariance')]:
        axes[0,1].plot([r['n'] for r in rr],[r[field] for r in rr],style,label=label)
    axes[0,1].set(xlabel='State dimension n',ylabel=r'$N\|U_0^T\widehat Z\|_F^2/[(m-r)Hn^2]$',ylim=(0,12),title='Dimension-normalized noise')
    axes[0,1].legend(fontsize=9)
    rr=sorted([r for r in noise_summary if r['n']==30 and r['policy']=='Kstar' and r['N']==131072],key=lambda r:r['m'])
    yy=[r['null_Z_fro2_median']/(r['m']-r['r']) for r in rr]
    axes[1,0].plot([r['m'] for r in rr],yy,'o-')
    axes[1,0].set(xlabel='Action dimension m (n=30, r=4)',ylabel='Null error / (m-r)',ylim=(0,1.2*max(yy)),title='Noise per redundant direction')
    for count in (8192,32768,131072):
        ratios=sorted(r['null_to_conditional_mean'] for r in noise if center(r) and r['N']==count)
        axes[1,1].step(ratios,np.arange(1,len(ratios)+1)/len(ratios),where='post',label='N='+str(count))
    axes[1,1].axvline(1,color='black',ls='--',lw=1)
    axes[1,1].set(xlabel='Observed null error / conditional mean',ylabel='Empirical CDF',title='160 one-stage repetitions')
    axes[1,1].legend(fontsize=9)
    for ax in axes.flat:ax.grid(alpha=.2)
    save(fig,dest,'Figure_2_null_noise')
    one=main['central_one_step']+high['one_step_summary']
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    for ax,algorithm in zip(axes[0],('NPG','v4_PI')):
        for method in ('dense','known_rank'):
            rr=sorted([r for r in one if r['algorithm']==algorithm and r['method']==method],key=lambda r:r['N'])
            xx=[r['N'] for r in rr]
            ax.plot(xx,[r['gap_median'] if r['gap_median'] is not None else np.nan for r in rr],'o-',color=colors[method],label=labels[method])
            ax.fill_between(xx,[r['gap_q10'] if r['gap_q10'] is not None else np.nan for r in rr],[r['gap_q90'] if r['gap_q90'] is not None else np.nan for r in rr],color=colors[method],alpha=.15)
        ax.set(xscale='log',yscale='log',xlabel='Evaluation blocks N',ylabel='One-step excess cost',title=algorithm.replace('_',' ')+r' at common $K^\star$')
        ax.legend()
    for method in ('dense','known_rank'):
        rr=sorted([r for r in one if r['algorithm']=='v4_PI' and r['method']==method],key=lambda r:r['N'])
        axes[1,0].plot([r['N'] for r in rr],[r['stable']/160 for r in rr],'o-',color=colors[method],label=labels[method])
    axes[1,0].set(xscale='log',xlabel='Evaluation blocks N',ylabel='Stable outputs / 160',ylim=(-.05,1.05),title='PI stability across all budgets')
    axes[1,0].legend()
    counts=[r['N'] for r in main['central_noise']]+[524288]
    for yy,style,label in [([r['null_normalized_median'] for r in main['central_noise']]+[high['null_noise_summary']['null_normalized']['median']],'o-','Empirical Gram'),([r['known_cov_null_normalized_median'] for r in main['central_noise']]+[high['null_noise_summary']['known_cov_null_normalized']['median']],'s--','Exact pulse-design covariance')]:
        axes[1,1].plot(counts,yy,style,label=label)
    axes[1,1].set(xscale='log',xlabel='Evaluation blocks N',ylabel=r'$N\|U_0^T\widehat Z\|_F^2/[(m-r)Hn^2]$',ylim=(0,10),title='Noise persists with known covariance')
    axes[1,1].legend(fontsize=9)
    for ax in axes.flat:ax.grid(alpha=.2)
    save(fig,dest,'Figure_3_shared_data')
    fig,axes=plt.subplots(1,2,figsize=(10.8,4.2),constrained_layout=True)
    for ax,variable in zip(axes,('n','r')):
        for method in ('dense','known_rank'):
            rr=sorted([r for r in points if r['variable']==variable and r['method']==method],key=lambda r:r['value'])
            slope=next(r['slope'] for r in fits if r['variable']==variable and r['method']==method and r['metric']=='Z_error_fro2_median')
            ax.plot([r['value'] for r in rr],[r['Z_error_fro2_median'] for r in rr],'o-',color=colors[method],label=labels[method]+f' (slope {slope:.2f})')
        ax.set(xscale='log',yscale='log',xlabel='State dimension n' if variable=='n' else 'Rank r',ylabel='Z error squared',title=('Fixed r=4' if variable=='n' else 'Fixed n=m=50')+', N=131072, H=16')
        ax.legend(fontsize=9);ax.grid(alpha=.2)
    save(fig,dest,'Figure_4_critic_scaling')
    science.atomic_json(dest/'figure_receipt.json',dict(status='complete',source=science.sha(__file__),
        figures=['Figure_1_v4_PI','Figure_2_null_noise','Figure_3_shared_data','Figure_4_critic_scaling'],
        input_hashes={str(p.relative_to(OUT)):science.sha(p) for p in [OUT/'report/summary.json',OUT/'high-budget/report/summary.json',OUT/'derived/fixed_policy_fits.json']},
        known_covariance_and_noise_per_direction_axes_start_at_zero=True,job=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':main()
