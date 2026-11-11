"""Render only saved CE oracle sensitivity data; no model solves or simulation."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
source=Path('E:/ChatGPT/Results/LQR_experiments/matched-gap-npg-pi-v2-20261019/ce-common-error-diagnostic-v2/all_directions.csv')
rows=list(csv.DictReader(source.open(encoding='utf-8-sig')))
out=ROOT/'analysis/ce-common-error-20261019';out.mkdir(parents=True,exist_ok=True)
ranks=[2,8,32,64,100];idx=np.random.default_rng(2026101905).integers(0,30,size=(2000,30))


def vector(rank,variant,field,scale=.01):
    rr=sorted([r for r in rows if int(r['rank'])==rank and r['variant']==variant and float(r['raw_error_scale'])==scale],key=lambda r:int(r['seed']))
    assert len(rr)==30
    return np.asarray([float(r[field]) for r in rr])


stats=[]
for rank in ranks:
    fgap=vector(100,'B_dense_only','control_gap');lgap=vector(rank,'B_truncated_only','control_gap')
    fe=vector(100,'B_dense_only','postprocessing_model_error_fro2');le=vector(rank,'B_truncated_only','postprocessing_model_error_fro2')
    bg=np.median(fgap[idx],axis=1)/np.median(lgap[idx],axis=1)
    be=np.median(fe[idx],axis=1)/np.median(le[idx],axis=1)
    stats.append(dict(rank=rank,model_error_gain=float(np.median(fe)/np.median(le)),
        model_error_gain_ci95=np.quantile(be,[.025,.975]).tolist(),control_gap_gain=float(np.median(fgap)/np.median(lgap)),
        control_gap_gain_ci95=np.quantile(bg,[.025,.975]).tolist()))
plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.18})
fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
for variant,label,color in [('B_dense_only','Dense B perturbation','#b94835'),('B_truncated_only','Same perturbation, then truncate B','#176da0')]:
    values=[vector(r,variant,'gap_per_raw_error_fro2') for r in ranks]
    axes[0].plot(ranks,[np.median(v) for v in values],'-o',color=color,label=label)
    axes[0].fill_between(ranks,[np.quantile(v,.25) for v in values],[np.quantile(v,.75) for v in values],color=color,alpha=.13)
axes[0].set(yscale='log',xticks=ranks,xlabel='Actuation rank',ylabel='True gap / squared raw perturbation norm',title='Control response to identical model errors (median/IQR)');axes[0].legend(fontsize=8)
for field,label,color in [('model_error_gain','B squared Frobenius error gain','#b07b20'),('control_gap_gain','True control-gap gain','#176da0')]:
    axes[1].plot(ranks,[q[field] for q in stats],'-o',color=color,label=label)
    axes[1].fill_between(ranks,[q[field+'_ci95'][0] for q in stats],[q[field+'_ci95'][1] for q in stats],color=color,alpha=.13)
axes[1].axhline(1,ls=':',color='.4');axes[1].set(yscale='log',xticks=ranks,xlabel='Rank of truncated system',ylabel='Full-rank dense / rank-r truncated',title='Model improvement differs from control improvement');axes[1].legend(fontsize=8)
fig.suptitle('Oracle sensitivity diagnostic | true A | same isotropic B errors across ranks | 30 directions\nPaired bootstrap 95% bands on gain ratios; diagnostic only, not sample complexity',fontsize=11)
for ext in ('png','svg'):fig.savefig(out/('CE_common_error_sensitivity.'+ext),dpi=180,facecolor='white')
plt.close(fig)
(out/'paired_sensitivity_statistics.json').write_text(json.dumps(dict(source=str(source),bootstrap_seed=2026101905,bootstrap_replicates=2000,
    scope='Saved-result local plotting and paired resampling only; zero new learning transitions and zero new Riccati solves',comparisons=stats),indent=2)+'\n',encoding='utf-8')
print(json.dumps(stats))
