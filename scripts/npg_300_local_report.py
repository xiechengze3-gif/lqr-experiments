"""Report finished local calibration tasks, preserving failures and censoring."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import beta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def cluster_interval(values):
    """Resample independent systems, then trajectories within each system."""
    rng=np.random.default_rng(3001009);groups=list(values.values());samples=[]
    for _ in range(2000):
        drawn=[]
        for index in rng.integers(0,len(groups),len(groups)):
            group=np.array(groups[index]);drawn.append(np.mean(rng.choice(group,len(group),replace=True)))
        samples.append(np.mean(drawn))
    return float(np.mean([np.mean(g) for g in groups])),np.quantile(samples,[.025,.975]).tolist()


def report(out):
    out=Path(out);critics=defaultdict(lambda:defaultdict(list));actors=defaultdict(lambda:defaultdict(list))
    completed={'critic':0,'actor':0}
    for phase in completed:
        for path in (out/phase).glob('task-*/result.json'):
            data=json.loads(path.read_text());task=data['task'];completed[phase]+=1
            if phase=='critic':
                for row in data['records']:
                    for method in row['methods']:
                        critics[(task['r'],row['N'],method['method'])][task['system_seed']].append(method['critic_error_fro2'])
            else:
                for method in ('raw','truncated'):
                    row=[r for r in data['records'] if r['method']==method][-1]
                    for eps in (.5,.25,.125):
                        success=bool(row['stable'] and row['gap']<=eps)
                        actors[(task['r'],task['profile'],method,eps,data['planned_total_transitions'])][task['system_seed']].append(success)
    critic_rows=[]
    for (rank,count,method),values in sorted(critics.items()):
        mean,ci=cluster_interval(values)
        critic_rows.append(dict(rank=rank,N=count,method=method,mean_fro2=mean,ci95_hierarchical_bootstrap=ci,
                                systems=len(values),trajectories=sum(map(len,values.values()))))
    actor_rows=[]
    for (rank,profile,method,eps,budget),values in sorted(actors.items()):
        successes=sum(sum(v) for v in values.values());trials=sum(map(len,values.values()))
        # Independent systems, with every sampled trajectory passing, gives a
        # conservative system-level interval distinct from per-trajectory rate.
        allpass=sum(all(v) for v in values.values());nsys=len(values)
        ci=[float(beta.ppf(.025,allpass,nsys-allpass+1)) if allpass else 0.,
            float(beta.ppf(.975,allpass+1,nsys-allpass)) if allpass<nsys else 1.]
        actor_rows.append(dict(rank=rank,profile=profile,method=method,epsilon=eps,
            planned_budget=budget,observed_success_rate=successes/trials,systems=nsys,trajectories=trials,
            all_trajectories_pass_system_rate=allpass/nsys,ci95_system_binomial=ci))
    cfg=json.loads((out/'config.json').read_text())
    scope_path=out/'active_scope.json'
    active=json.loads(scope_path.read_text()) if scope_path.exists() else None
    summary=dict(scope='Exploratory 300d calibration, not a research-scale replication or proof of budget exponent.',
        designed_full_grid_tasks=len(cfg['tasks']),planned_tasks=len(active['task_ids']) if active else len(cfg['tasks']),
        active_scope=active,completed=completed,critic=critic_rows,actor=actor_rows,
        warnings=['Incomplete tasks excluded from finished-output rates and counted separately as pending.',
                  'Unstable completed actor arms count as failures. No true-cost stopping.',
                  'Bootstrap with five systems can be imprecise; boundary success rates use a separate conservative system interval.',
                  'If no tested budget reaches a precision, the budget is right-censored; do not extrapolate a rank or epsilon slope.'])
    tmp=out/'summary.tmp';tmp.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8');tmp.replace(out/'summary.json')
    if critic_rows:
        fig,ax=plt.subplots(figsize=(7.5,4.8))
        for count in sorted({r['N'] for r in critic_rows}):
            for method in ('raw','truncated'):
                rows=[r for r in critic_rows if r['N']==count and r['method']==method]
                if not rows:continue
                xs=np.array([r['rank'] for r in rows]);ys=np.array([r['mean_fro2'] for r in rows])
                ax.plot(xs,ys,'o--' if method=='raw' else 's-',label=f'{method}, N={count:,}')
                ax.fill_between(xs,[r['ci95_hierarchical_bootstrap'][0] for r in rows],
                                [r['ci95_hierarchical_bootstrap'][1] for r in rows],alpha=.12)
        ax.set(xscale='log',yscale='log',xlabel='rank r',ylabel='critic squared Frobenius error',
               title='Dense n=m=300, fixed initial policy (calibration)')
        ax.grid(True,which='both',alpha=.2);ax.legend(fontsize=8)
        fig.tight_layout();fig.savefig(out/'critic_rank_loglog.png',dpi=180);plt.close(fig)
    if actor_rows:
        fig,ax=plt.subplots(figsize=(7.5,4.8))
        for rank in sorted({r['rank'] for r in actor_rows}):
            for method in ('raw','truncated'):
                rows=sorted([r for r in actor_rows if r['rank']==rank and r['method']==method and r['epsilon']==.25],key=lambda r:r['planned_budget'])
                ax.plot([r['planned_budget'] for r in rows],[r['observed_success_rate'] for r in rows],
                        'o--' if method=='raw' else 's-',label=f'r={rank}, {method}')
        ax.set(xscale='log',ylim=(-.03,1.03),xlabel='planned primitive transitions per arm',
               ylabel='observed success rate at epsilon=0.25',title='Dense 300d paired NPG calibration; completed tasks only')
        ax.grid(True,alpha=.2);ax.legend(fontsize=7,ncol=2)
        fig.tight_layout();fig.savefig(out/'actor_budget_success.png',dpi=180);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();report(args.output)
