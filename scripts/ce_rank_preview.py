"""Complete CE subset report; every CE system is required, other methods pending."""
import argparse,json,os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dense_scaling import require_compute,atomic_json


def main(release,root):
    root,release=Path(root),Path(release)
    cfg=json.loads((release/'configs/cross_rank_ce.json').read_text())
    rows=[]
    for tid,task in enumerate(cfg['tasks']):
        d=json.loads((root/'ce/raw'/f'task-{tid:03d}.json').read_text())
        assert d['task']==task
        rows += [dict(n=task['n'],r=task['r'],seed=task['system_seed'],tail=task['tail'],**row) for row in d['records']]
    fits=[]
    for method in ('raw','truncated'):
        candidates=[row for row in rows if row['method']==method and row['tail']==0 and row['r']/row['n']<=.2 and row['N']>=128*row['n']]
        good=[]
        for row in candidates:
            group=[rr for rr in candidates if (rr['n'],rr['r'],rr['N'])==(row['n'],row['r'],row['N'])]
            if all(rr['stable'] and rr['gap']>1e-12 for rr in group):good.append(row)
        x=np.array([[1,np.log(row['n']),np.log(row['r']),-np.log(row['N'])] for row in good])
        y=np.log([row['gap'] for row in good]);coef=np.linalg.lstsq(x,y,rcond=None)[0]
        fits.append(dict(method=method,C=float(np.exp(coef[0])),alpha_n=float(coef[1]),beta_r=float(coef[2]),gamma_N=float(coef[3]),observations=len(good),caveat='Two system seeds, conditional stable groups, descriptive fit only'))
    thresholds=[]
    for n,r in sorted(set((row['n'],row['r']) for row in rows if row['tail']==0)):
        for method in ('raw','truncated'):
            for eps in (1.,.1):
                selected=[row for row in rows if row['n']==n and row['r']==r and row['method']==method and row['tail']==0]
                budgets=cfg['budgets'];success=[all(row['stable'] and row['gap']<=eps for row in selected if row['N']==budget) for budget in budgets]
                at=next((i for i in range(len(budgets)) if all(success[i:])),None)
                thresholds.append(dict(n=n,r=r,method=method,epsilon=eps,transitions=budgets[at]+512 if at is not None else None,left_censored=at==0))
    fig,axes=plt.subplots(2,2,figsize=(10,8),constrained_layout=True)
    colors={'raw':'#c44e52','truncated':'#4c72b0'}
    for ax,n in zip(axes[0],(50,100)):
        for method in colors:
            group=sorted([t for t in thresholds if t['n']==n and t['method']==method and t['epsilon']==.1],key=lambda t:t['r'])
            ax.plot([t['r'] for t in group],[t['transitions'] for t in group],marker='o',color=colors[method],label=method)
        ax.set(xscale='log',yscale='log',xlabel='Rank r',ylabel='Minimum tested primitive transitions',title=f'CE: n={n}, absolute gap <= 0.1')
        ax.grid(alpha=.2);ax.legend()
    for ax,method in zip(axes[1],colors):
        for n in (25,50,75,100):
            group=[row for row in rows if row['method']==method and row['tail']==0 and row['r']==4 and row['n']==n]
            ns=cfg['budgets'];valid=[];gaps=[]
            for budget in ns:
                at=[row for row in group if row['N']==budget]
                if all(row['stable'] for row in at):valid.append(budget+512);gaps.append(float(np.mean([row['gap'] for row in at])))
            ax.plot(valid,gaps,marker='o',label=f'n={n}')
        ax.set(xscale='log',yscale='log',xlabel='Primitive transitions',ylabel='Mean absolute gap, 2 systems',title=f'CE {method}, r=4')
        ax.grid(alpha=.2);ax.legend()
    out=root/'preview';out.mkdir(exist_ok=True)
    fig.savefig(out/'ce_rank_complete.png',dpi=180);fig.savefig(out/'ce_rank_complete.pdf');plt.close(fig)
    atomic_json(out/'ce_rank_complete.json',dict(complete_CE=True,systems=36,fits=fits,thresholds=thresholds,slurm_job_id=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();main(a.release,a.output)
