"""Same-accuracy sample ratios and rank-normalized complexity, after audit."""
import math
from pathlib import Path

import numpy as np


def report_scaling(cfg,ident,e,write_csv,phase):
    out=Path(cfg['output']);dest=out/('report-'+phase);summary=e.read(dest/'summary.json')
    rows=[];gains=[];dimension=2*cfg['n'];grid=[n+cfg['burn'] for n in cfg['budgets']]
    for r in summary['requirements']:
        upper=r['sustained_N90'];j=grid.index(upper) if upper is not None else None
        lower=grid[j-1] if j is not None and j else 0
        rows.append(dict(r,sample_count=upper,epsilon_N_over_r_d=(r['absolute_target']*upper/(r['rank']*dimension)) if upper else None,
            grid_lower=lower if upper else grid[-1],grid_upper=upper,
            censoring='right' if upper is None else ('left' if j==0 else 'interval'),
            target_achieved=upper is not None))
    for rank in cfg['ranks']:
        for target in cfg['absolute_targets']:
            d,t=[next(r for r in rows if r['rank']==rank and r['absolute_target']==target and r['method']==m) for m in ('dense','truncated')]
            nd,nt=d['sample_count'],t['sample_count']
            gains.append(dict(rank=rank,absolute_target=target,seeds=len(summary['seeds']),
                dense_samples=nd,truncated_samples=nt,sample_gain=nd/nt if nd and nt else None,
                gain_lower_bound=grid[-1]/nt if nd is None and nt else None,
                dense_censoring=d['censoring'],truncated_censoring=t['censoring']))
    write_csv(dest/'rank_normalized_sample_complexity.csv',rows)
    write_csv(dest/'same_accuracy_sample_gain.csv',gains)
    summary.update(identity=ident,supplied_common_bounds=cfg['supplied_common_bounds'],
        shared_matrices=['A','Q','R','W','K0','F0','P0'],
        primary_absolute_target=cfg['primary_absolute_target'],normalized_sample_complexity=rows,same_accuracy_gains=gains,
        source_verification_sha256=cfg['construction_verification_sha256'])
    e.atomic_json(dest/'summary.json',summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(15,4.2),layout='constrained');target=cfg['primary_absolute_target']
    selected=[r for r in rows if r['absolute_target']==target]
    for method,color in [('dense','#aa4538'),('truncated','#1974a3')]:
        rr=[r for r in selected if r['method']==method and r['sample_count'] is not None]
        axes[0].plot([r['rank'] for r in rr],[r['sample_count'] for r in rr],'-o',color=color,label=method)
    rr=[r for r in selected if r['method']=='truncated' and r['sample_count'] is not None]
    axes[1].plot([r['rank'] for r in rr],[r['epsilon_N_over_r_d'] for r in rr],'-o',color='#1974a3')
    gg=[r for r in gains if r['absolute_target']==target and r['sample_gain'] is not None]
    axes[2].plot([r['rank'] for r in gg],[r['sample_gain'] for r in gg],'-o',color='#177c66')
    axes[0].set(yscale='log',ylim=(grid[0]/2,grid[-1]*2),ylabel='Primitive transitions',title='Samples to common accuracy')
    scaled=[r['epsilon_N_over_r_d'] for r in rr]
    axes[1].set(yscale='log',ylim=(min(scaled)/2,max(scaled)*2) if scaled else (1e-4,1e3),
        ylabel='epsilon N / [r (n+m)]',title='Truncated CE: rank-normalized samples')
    values=[g['sample_gain'] for g in gg]
    axes[2].set(yscale='log',ylim=(min(values)/2,max(values)*2) if values else (.5,1e3),
        ylabel='Dense samples / truncated samples',title='Same-accuracy sample gain')
    for ax in axes:ax.set(xscale='log',xlim=(min(cfg['ranks'])/1.4,max(cfg['ranks'])*1.4),xlabel='Rank r');ax.grid(alpha=.2)
    axes[0].legend();fig.suptitle(f'Common system bounds | p0=47 | absolute gap={target:g} | {len(summary["seeds"])} seeds')
    for ext in ('png','svg'):fig.savefig(dest/('same_accuracy_rank_scaling.'+ext),dpi=170)
    plt.close(fig)
    print({'status':'complete','phase':phase,'primary_same_accuracy_gains':[r for r in gains if r['absolute_target']==target]},flush=True)
