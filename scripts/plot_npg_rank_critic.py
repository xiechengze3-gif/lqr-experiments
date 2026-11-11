"""Show measured critic error and end-to-end budgets side by side on Grace."""
import json
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, ScalarFormatter, NullFormatter


if not os.environ.get('SLURM_JOB_ID'):
    raise RuntimeError('Requires a real Slurm compute allocation')
root = Path('/scratch/user/changze/lqr_experiments/results/npg-budget-loglog-e93b7ffa7fca793e')
diagnostics = json.loads((root/'loglog_diagnostics.json').read_text())
summary = json.loads(Path('/scratch/user/changze/lqr_experiments/results/'
    'npg-budget-e93b7ffa7fca793e/report/summary.json').read_text())
assert diagnostics['status']=='PASS' and summary['status']=='complete'
ranks = summary['ranks']
colors = {'raw':'#777777','truncated':'#12699c'}
plt.rcParams.update({'font.size':11,'axes.titlesize':12,'legend.fontsize':9})
fig, axes = plt.subplots(1,2,figsize=(12.2,5.3))
for method in ('raw','truncated'):
    selected = [r for r in diagnostics['same_allocation_last_epoch'] if r['method']==method]
    mean = [r['critic_error_fro2']['mean'] for r in selected]
    low = [r['critic_error_fro2']['minimum'] for r in selected]
    high = [r['critic_error_fro2']['maximum'] for r in selected]
    axes[0].plot(ranks,mean,'o-',color=colors[method],label=method,linewidth=2,zorder=4)
    axes[0].fill_between(ranks,low,high,color=colors[method],alpha=.12)
    selected = [r for r in summary['minimum_budgets'] if r['method']==method and r['epsilon']==.25]
    assert all(r['minimum_budget'] is not None for r in selected)
    axes[1].plot([r['r'] for r in selected],[r['minimum_budget']/1e6 for r in selected],
                 'o-',color=colors[method],label=method,linewidth=2,zorder=4)
x = np.geomspace(1,16,100)
for i, axis_name in enumerate(('same_allocation_last_epoch_critic_fro2_rank','budget_rank')):
    fit = next(r for r in diagnostics['fits'] if r['axis']==axis_name and r.get('method')=='truncated'
               and (i==0 or r['epsilon']==.25))
    unit = 1 if i==0 else 1e6
    axes[i].plot(x,np.exp(fit['intercept'])*x**fit['slope']/unit,'--',
                  color=colors['truncated'],label=f"fit r<=16: slope {fit['slope']:.2f}",linewidth=1.5)
    if i==0:
        anchor = next(r['critic_error_fro2']['mean'] for r in diagnostics['same_allocation_last_epoch']
                      if r['r']==1 and r['method']=='truncated')
    else:
        anchor = next(r['minimum_budget']/1e6 for r in summary['minimum_budgets']
                      if r['r']==1 and r['method']=='truncated' and r['epsilon']==.25)
    axes[i].plot(x,anchor*x,'k:',label='slope 1 guide (anchored at r=1)',linewidth=1.5)
    axes[i].set_xscale('log',base=2);axes[i].set_yscale('log')
    axes[i].set_xticks(ranks,labels=ranks);axes[i].set_xlim(.9,55)
    axes[i].axvspan(16,55,color='#eeeeee',alpha=.6,zorder=0)
    axes[i].grid(which='major',alpha=.22);axes[i].set_xlabel('Rank r (log scale)')
    axes[i].yaxis.set_major_formatter(ScalarFormatter());axes[i].yaxis.set_minor_formatter(NullFormatter())
    axes[i].legend(loc='lower right' if i==0 else 'upper left',fontsize=8)
axes[0].yaxis.set_major_locator(FixedLocator([.25,.5,1,2,4,8]))
axes[0].set_ylim(.2,9)
axes[0].set_title('Critic squared error at the same large allocation\n'
                  'Last 16 updates: average within each of 4 systems')
axes[0].set_ylabel('Measured squared Frobenius error (log scale)')
axes[1].yaxis.set_major_locator(FixedLocator([100,200,500,1000,2000]))
axes[1].set_ylim(100,2800)
axes[1].set_title('End-to-end budget at absolute gap <= 0.25\n'
                  'Minimum tested schedule where all 4 systems pass')
axes[1].set_ylabel('Total transitions / run (millions, log scale)')
fig.suptitle('Rank dependence differs between critic error and actor attainment budget; n=m=50',fontsize=13)
fig.tight_layout(rect=(0,0,1,.91))
for extension in ('png','pdf'):
    fig.savefig(root/f'critic_vs_budget_rank_loglog.{extension}',dpi=190,bbox_inches='tight')
plt.close(fig)
print(json.dumps(dict(status='PASS',job_id=os.environ['SLURM_JOB_ID'],
    critic_input='loglog_diagnostics.json',policies='Method/rank trajectories differ; not a same-policy critic experiment.')))
