"""Saved-result diagnostics: initial-gap decomposition and CE intervention plots."""
import argparse
import csv
import json
from pathlib import Path
import os
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from threadpoolctl import threadpool_limits
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import rank_sweep100 as e
from matched_gap_npg_pi import load
from rank_sweep100_report import csv_write


def run(cfg):
    out=Path(cfg['output']);dest=out/'supplement';dest.mkdir(exist_ok=True)
    oracle=e.read(out/'oracle.json')['records'];initial=[];iterations=[]
    for rank in cfg['ranks']:
        s,_=load(cfg,rank);f=s['A']-s['B']@s['K0'];cov=solve_discrete_lyapunov(f,s['W'])
        _,_,vh=np.linalg.svd(s['B']);basis=vh[:rank].T;proj=basis@basis.T
        delta=s['K0']-s['Kstar'];kn=(np.eye(100)-proj)@delta;ke=proj@delta
        weight=s['R']+s['B'].T@s['Pstar']@s['B']
        null=float(np.trace(kn@cov@kn.T));effective=float(np.trace(weight@ke@cov@ke.T))
        assert abs(null+effective-1)<1e-10
        initial.append(dict(rank=rank,initial_gap=1.,unactuated_gain_component_gap=null,
            actuated_gain_component_gap=effective,unactuated_fraction=null/(null+effective),
            decomposition='Truth-only performance-difference identity at the frozen initial policy; never used by learners.'))
        for kind in ('exact_npg','finite_H_npg','exact_pi'):
            rr=[q for q in oracle if q['rank']==rank and q['kind']==kind]
            iterations.append(dict(rank=rank,kind=kind,iterations_to_01=next(q['stage'] for q in rr if q['gap']<=.1),
                iterations_to_005=next(q['stage'] for q in rr if q['gap']<=.05),
                gap_at_learning_iteration_cap=next(q['gap'] for q in rr if q['stage']==(44 if 'npg' in kind else 4))))
    csv_write(dest/'initial_gap_decomposition.csv',initial);csv_write(dest/'oracle_iterations.csv',iterations)
    e.atomic_json(dest/'optimization_diagnostics.json',dict(initial_gap_decomposition=initial,oracle_iterations=iterations,
        caveat='Initial gap matching does not equalize curvature or the fraction of initial error in unactuated gain directions.'))
    plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.17})
    def save(fig,name):
        for ext in ('png','svg'):fig.savefig(dest/(name+'.'+ext),dpi=180,facecolor='white')
        plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.3),layout='constrained')
    for rank in cfg['ranks']:
        rr=[q for q in oracle if q['rank']==rank and q['kind']=='exact_npg']
        axes[0].plot([q['stage'] for q in rr],[max(q['gap'],1e-12) for q in rr],label=f'rank{rank}')
    for eps in cfg['relative_targets']:axes[0].axhline(eps,color='.4',ls=':')
    axes[0].set(yscale='log',xlabel='Exact NPG updates',ylabel='Absolute = relative gap',title='Same eta=.05; optimization alone varies by rank');axes[0].legend(fontsize=8)
    xx=np.arange(5);axes[1].bar(xx,[q['unactuated_fraction'] for q in initial],color='#ae5d3c',label='Unactuated gain directions')
    axes[1].bar(xx,[1-q['unactuated_fraction'] for q in initial],bottom=[q['unactuated_fraction'] for q in initial],color='#257da6',label='Actuated gain directions')
    axes[1].set(xticks=xx,xticklabels=cfg['ranks'],ylim=(0,1),xlabel='Actuation rank',ylabel='Fraction of common initial gap1',title='Private initial-policy diagnostic');axes[1].legend(fontsize=8)
    save(fig,'oracle_optimization_and_initial_gap')
    audit=e.read(Path(cfg['ce_audit_output'])/'audit.json');csv_write(dest/'CE_intervention_summary.csv',audit['summary'])
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),sharey=True,layout='constrained')
    variants=[('dense','Dense CE','#b94835','-'),('truncated','Truncated CE','#176da0','-'),
        ('known_A_truncated_B','Known A + truncated B','#278a50','--'),
        ('estimated_A_known_B','Estimated A + known B','#986eb3','--'),
        ('recomposed_A_truncated_B','Recomposed A + truncated B','#ab861f',':')]
    for ax,rank in zip(axes,(2,100)):
        for variant,label,color,style in variants:
            rr=sorted([q for q in audit['summary'] if q['rank']==rank and q['variant']==variant],key=lambda q:q['transitions'])
            ax.plot([q['transitions'] for q in rr],[q['gap_median'] for q in rr],style+'o',markersize=3,color=color,label=label)
        for eps in cfg['relative_targets']:ax.axhline(eps,color='.5',ls=':')
        ax.set(xscale='log',yscale='log',xlabel='Transitions',title=f'CE | rank {rank}')
    axes[0].set_ylabel('True optimality gap (median,30 seeds)');axes[1].legend(fontsize=8)
    fig.suptitle('Offline CE diagnostics: oracle parameters and a different recomposed-A variant\nPrimary CE always uses unchanged joint-OLS Ahat; diagnostic curves are not replacement sample-complexity results',fontsize=11)
    save(fig,'CE_known_parameter_diagnostics')
    print('Saved-result supplement complete',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    with threadpool_limits(1):run(e.read(a.manifest))
