"""Complete PI subset: fixed-output errors, rank/dimension/batch dependence."""
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dense_scaling import require_compute,atomic_json


def main(release,root):
    root,release=Path(root),Path(release);rows=[]
    for count in (32768,131072,524288):
        path=release/f'configs/cross_rank_pi-{count}.json';cfg=json.loads(path.read_text())
        for tid,task in enumerate(cfg['tasks']):
            d=json.loads((root/f'pi-{count}/raw'/f'task-{tid:03d}.json').read_text())
            assert d['task']==task and d['manifest_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
            for method in ('raw','truncated'):
                rr=[r for r in d['records'] if r['method']==method];last=rr[-1]
                rows.append(dict(n=task['n'],r=task['r'],seed=task['system_seed'],tail=task['tail'],method=method,
                    N=count,M=6*(count+1024),actual_transitions=last['transitions'],gap=last['gap'],
                    eligible=bool(last['stable'] and last['stage']==6),
                    solver_failure=any(not r.get('solver',{}).get('converged',True) for r in rr)))
    fits=[]
    for method in ('raw','truncated'):
        candidates=[r for r in rows if r['method']==method and r['tail']==0 and r['r']/r['n']<=.2 and r['N']>=128*r['n']]
        good=[r for r in candidates if all(rr['eligible'] and rr['gap']>1e-12 for rr in candidates if (rr['n'],rr['r'],rr['N'])==(r['n'],r['r'],r['N']))]
        x=np.array([[1,np.log(r['n']),np.log(r['r']),-np.log(r['M'])] for r in good]);y=np.log([r['gap'] for r in good]);coef=np.linalg.lstsq(x,y,rcond=None)[0]
        fits.append(dict(method=method,C=float(np.exp(coef[0])),alpha_n=float(coef[1]),beta_r=float(coef[2]),gamma_M=float(coef[3]),
            observations=len(good),log_R2=float(1-np.sum((y-x@coef)**2)/max(np.sum((y-y.mean())**2),1e-30)),
            caveat='Conditional stable paired outputs, two systems, finite 6-step cost, exploratory only; not a sample-complexity theorem'))
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    colors={'raw':'#c44e52','truncated':'#4c72b0'}
    for ax,n in zip(axes[0],(50,100)):
        for method in colors:
            xx=[];yy=[]
            for rank in (1,2,4,8,16):
                group=[r for r in rows if r['method']==method and r['n']==n and r['r']==rank and r['tail']==0 and r['N']==524288]
                if all(r['eligible'] for r in group):xx.append(rank);yy.append(float(np.mean([r['gap'] for r in group])))
                else:ax.scatter([rank],[.95],marker='x',color=colors[method],transform=ax.get_xaxis_transform())
            ax.plot(xx,yy,marker='o',color=colors[method],label=method)
        ax.set(xscale='log',yscale='log',xlabel='Rank r',ylabel='Mean absolute gap (2 systems)',title=f'Full LSTD-PI, n={n}, same 3,151,872 transitions')
        ax.grid(alpha=.2);ax.legend()
    for ax,method in zip(axes[1],colors):
        for n in (25,50,75,100):
            xx=[];yy=[]
            for count in (32768,131072,524288):
                group=[r for r in rows if r['method']==method and r['n']==n and r['r']==4 and r['tail']==0 and r['N']==count]
                if all(r['eligible'] for r in group):xx.append(6*(count+1024));yy.append(float(np.mean([r['gap'] for r in group])))
                else:ax.scatter([6*(count+1024)],[.95],marker='x',transform=ax.get_xaxis_transform())
            ax.plot(xx,yy,marker='o',label=f'n={n}')
        ax.set(xscale='log',yscale='log',xlabel='Planned primitive transitions (fixed 6 updates)',ylabel='Mean absolute gap',title=f'LSTD-PI {method}, r=4; crosses = failed outputs')
        ax.grid(alpha=.2);ax.legend()
    out=root/'preview';out.mkdir(exist_ok=True)
    fig.savefig(out/'pi_rank_complete.png',dpi=180);fig.savefig(out/'pi_rank_complete.pdf');plt.close(fig)
    atomic_json(out/'pi_rank_complete.json',dict(complete_PI=True,paired_tasks=108,fits=fits,endpoints=rows,
        solver_failures=sum(r['solver_failure'] for r in rows),slurm_job_id=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();main(a.release,a.output)
