"""Fixed-output batch-sweep reporting and plots, on Grace compute nodes."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dense_scaling import require_compute, atomic_json


def main(release, output):
    release, output = Path(release), Path(output)
    index = json.loads((release/'configs/cross_rank_index.json').read_text())
    endpoints, missing = [], []
    for profile in index['profiles']:
        manifest = release/f'configs/cross_rank_{profile}.json'
        cfg = json.loads(manifest.read_text()); digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        for tid, task in enumerate(cfg['tasks']):
            path = output/profile/'raw'/f'task-{tid:03d}.json'
            if not path.exists():
                missing.append(dict(profile=profile, task_id=tid)); continue
            payload = json.loads(path.read_text())
            assert payload['task'] == task and payload['manifest_sha256'] == digest
            algo = 'NPG' if profile.startswith('npg-') else cfg['algorithm']
            for method in ('raw','truncated'):
                rows = [r for r in payload['records'] if r['method'] == method]
                if algo == 'CE':
                    selected = rows
                else:
                    selected = [rows[-1]]
                for row in selected:
                    if algo == 'CE':
                        planned = row['N']+512
                    elif algo == 'NPG':
                        planned = cfg['stages'] * (cfg['burn'] + (cfg['batch_schedule'][0]+1)*cfg['horizon'])
                    else:
                        planned = cfg['stages'] * (cfg['burn'] + cfg['batch_schedule'][0])
                    complete = algo == 'CE' or row['stage'] == cfg['stages']
                    solver_ok = all(r.get('solver',{}).get('converged',True) for r in rows)
                    endpoints.append(dict(algorithm=algo, profile=profile, method=method,
                        n=task['n'], r=task['r'], seed=task['system_seed'], tail=task['tail'],
                        N=row['N'], transitions=row['transitions'], planned_transitions=planned,
                        gap=row['gap'], stable=row['stable'], complete=complete, solver_ok=solver_ok,
                        failure=row.get('failure',''), eligible=bool(complete and row['stable'] and solver_ok)))
    report = output/'report'; report.mkdir(parents=True, exist_ok=True)
    with (report/'endpoints.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(endpoints[0]) if endpoints else [])
        writer.writeheader(); writer.writerows(endpoints)
    atomic_json(report/'coverage.json',dict(missing=missing, endpoints=len(endpoints),
        slurm_job_id=os.environ['SLURM_JOB_ID']))
    if missing: raise RuntimeError(f'{len(missing)} planned runs missing: no complete scaling claim')
    thresholds=[]
    keys=sorted(set((e['algorithm'],e['method'],e['n'],e['r'],e['tail']) for e in endpoints))
    for algo,method,n,r,tail in keys:
        rows=[e for e in endpoints if (e['algorithm'],e['method'],e['n'],e['r'],e['tail'])==(algo,method,n,r,tail)]
        budgets=sorted(set(e['planned_transitions'] for e in rows))
        for eps in (5.,2.,1.,.5,.1):
            success=[]
            for budget in budgets:
                group=[e for e in rows if e['planned_transitions']==budget]
                assert len(group)==2 and len(set(e['seed'] for e in group))==2
                success.append(all(e['eligible'] and e['gap']<=eps for e in group))
            at=next((i for i in range(len(budgets)) if all(success[i:])),None)
            status='right_censored' if at is None else ('left_censored' if at==0 else 'attained')
            thresholds.append(dict(algorithm=algo,method=method,n=n,r=r,tail=tail,epsilon=eps,
                status=status,budget=None if at is None else budgets[at],
                lower_budget=budgets[-1] if at is None else (0 if at==0 else budgets[at-1]),
                tested_budgets=budgets,success_by_budget=success))
    fits=[]
    for algo in sorted(set(e['algorithm'] for e in endpoints)):
        for method in ('raw','truncated'):
            for eps in (5.,2.,1.,.5,.1):
                eligible=[t for t in thresholds if t['algorithm']==algo and t['method']==method
                    and t['epsilon']==eps and t['tail']==0 and t['r']/t['n']<=.2]
                rows=[t for t in eligible if t['status']=='attained']
                fit=dict(algorithm=algo,method=method,epsilon=eps,eligible_cells=len(eligible),
                    fitted_cells=len(rows),cells=[[t['n'],t['r']] for t in rows],
                    limitation='Two systems; coarse grid; conditional fit excludes censored cells')
                if len(set(t['n'] for t in rows))>=3 and len(set(t['r'] for t in rows))>=3:
                    x=np.array([[1,np.log(t['n']),np.log(t['r'])] for t in rows]); y=np.log([t['budget'] for t in rows])
                    if np.linalg.matrix_rank(x)==3:
                        coef=np.linalg.lstsq(x,y,rcond=None)[0]
                        fit.update(C=float(np.exp(coef[0])),alpha_n=float(coef[1]),beta_r=float(coef[2]))
                fits.append(fit)
    atomic_json(report/'summary.json',dict(complete=True,thresholds=thresholds,fits=fits,
        failures=[e for e in endpoints if not e['eligible']],slurm_job_id=os.environ['SLURM_JOB_ID'],
        interpretation='All fixed outputs; minimum tested budget requires success at every higher tested budget. Censored budgets are not exact sample requirements.'))
    colors={'raw':'#c44e52','truncated':'#4c72b0'}
    for algo in sorted(set(e['algorithm'] for e in endpoints)):
        fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
        for ax,n in zip(axes[:,0],(50,100)):
            for method in colors:
                for r in (1,4,16):
                    rows=[e for e in endpoints if e['algorithm']==algo and e['method']==method and e['n']==n and e['r']==r and e['tail']==0]
                    budgets=sorted(set(e['planned_transitions'] for e in rows)); xs=[];ys=[]
                    for budget in budgets:
                        group=[e for e in rows if e['planned_transitions']==budget]
                        if all(e['eligible'] for e in group):
                            xs.append(budget);ys.append(max(1e-10,float(np.mean([e['gap'] for e in group]))))
                        else: ax.scatter([budget],[1e2],color=colors[method],marker='x',alpha=.5)
                    ax.plot(xs,ys,marker='o',color=colors[method],linestyle={1:'-',4:'--',16:':'}[r],label=f'{method}, r={r}')
            ax.set(xscale='log',yscale='log',xlabel='Primitive transitions (fixed output)',ylabel='Mean absolute gap (2 systems)',title=f'{algo}: n={n}; crosses = failed fixed outputs')
            ax.grid(alpha=.2);ax.legend(fontsize=8,ncol=2)
        for ax,n in zip(axes[:,1],(50,100)):
            for method in colors:
                rows=sorted([t for t in thresholds if t['algorithm']==algo and t['method']==method and t['n']==n and t['tail']==0 and t['epsilon']==1],key=lambda t:t['r'])
                for t in rows:
                    value=t['budget'] if t['budget'] else t['lower_budget']
                    marker={'attained':'o','left_censored':'v','right_censored':'^'}[t['status']]
                    ax.scatter(t['r'],value,color=colors[method],marker=marker)
                points=[t for t in rows if t['budget']]
                ax.plot([t['r'] for t in points],[t['budget'] for t in points],color=colors[method],label=method)
            ax.set(xscale='log',yscale='log',xlabel='Rank r',ylabel='Minimum tested transitions',title=f'n={n}, gap <= 1; down/up = left/right censored')
            ax.grid(alpha=.2);ax.legend()
        fig.savefig(report/f'{algo.lower().replace("-","_")}_batch_rank.png',dpi=180)
        fig.savefig(report/f'{algo.lower().replace("-","_")}_batch_rank.pdf');plt.close(fig)
    # Approximate-tail profiles at the largest common tested budget.
    fig,axes=plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
    for ax,algo in zip(axes,('CE','PI-LSTD','NPG')):
        for n in (50,100):
            for method in colors:
                rows=[e for e in endpoints if e['algorithm']==algo and e['n']==n and e['r']==4 and e['method']==method]
                if not rows: continue
                maxbudget=max(e['planned_transitions'] for e in rows)
                xx=[]; yy=[]
                for tail in (0.,.01,.1,.3):
                    group=[e for e in rows if e['tail']==tail and e['planned_transitions']==maxbudget]
                    if len(group)==2 and all(e['eligible'] for e in group):
                        xx.append(tail);yy.append(max(1e-10,float(np.mean([e['gap'] for e in group]))))
                ax.plot(xx,yy,color=colors[method],linestyle='-' if n==50 else '--',marker='o',label=f'{method} n={n}')
        ax.set(xscale='symlog',yscale='log',xlabel='Frobenius tail of B',ylabel='Mean final gap',title=f'{algo}, r=4, largest fixed budget')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(report/'approximate_tail_comparison.png',dpi=180)
    fig.savefig(report/'approximate_tail_comparison.pdf');plt.close(fig)


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();main(a.release,a.output)
