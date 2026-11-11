"""Final presentation QA: common axes, exact budget ticks; no new simulations."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def main(root):
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Scientific figures require Slurm compute nodes')
    root=Path(root);out=root/'report'
    summary=json.loads((out/'summary.json').read_text())
    audit=json.loads((out/'numerical_audit.json').read_text())
    assert audit['status']=='PASS' and summary['stable_methods']==summary['sampled_methods']==32
    rows=summary['aggregate']
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import NullFormatter
    colors={'raw':'#777777','truncated':'#12699c'}
    styles={'constant':'--','geometric':'-'}
    labels=[Line2D([],[],color=colors[method],linestyle=styles[kind],
                   marker='s' if kind=='constant' else 'o',label=f'{method}, {kind}')
            for method in ('raw','truncated') for kind in ('constant','geometric')]
    fig,axes=plt.subplots(1,2,figsize=(11.5,4.9),sharey=True)
    ymin=min(row['gap_min'] for row in rows)*.8
    ymax=max(row['gap_max'] for row in rows)*1.15
    budgets=sorted({row['planned_transitions']/1e6 for row in rows})
    for ax,rank in zip(axes,(1,4)):
        for method in ('raw','truncated'):
            for kind in ('constant','geometric'):
                selected=sorted((row for row in rows if row['r']==rank and row['method']==method
                                 and row['schedule_kind']==kind),key=lambda row:row['planned_transitions'])
                assert len(selected)==2 and all(row['stable_systems']==row['systems']==2 for row in selected)
                ax.plot([row['planned_transitions']/1e6 for row in selected],[row['gap_mean'] for row in selected],
                        ('s' if kind=='constant' else 'o')+styles[kind],color=colors[method],linewidth=1.7)
                for row in selected:
                    ax.vlines(row['planned_transitions']/1e6,row['gap_min'],row['gap_max'],color=colors[method],alpha=.5)
        ax.set_yscale('log');ax.set_ylim(ymin,ymax);ax.set_xscale('log')
        ax.set_xticks(budgets,labels=[f'{budget:.2f}' for budget in budgets])
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_title(f'Rank r={rank}');ax.set_xlabel('Total primitive transitions (millions)')
        for eps in (.25,.5,1.,2.):ax.axhline(eps,color='#999999',linewidth=.6,alpha=.4)
        ax.grid(alpha=.2)
    axes[0].set_ylabel('Final absolute cost gap')
    fig.suptitle('NPG at 128 updates: equal total budget, different allocation\nMean and range of two independent systems; n=m=50',fontsize=12)
    fig.legend(handles=labels,loc='upper center',bbox_to_anchor=(.5,.88),ncol=4,fontsize=9)
    fig.tight_layout(rect=(0,0,1,.79))
    for ext in ('png','pdf'):fig.savefig(out/f'endpoint_equal_budget_review.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)
    stamp=dict(status='PASS',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               input_summary_sha256=hashlib.sha256((out/'summary.json').read_bytes()).hexdigest(),
               changes=['common y axis across ranks','exact full-budget x ticks','one shared legend'],
               simulation_unchanged=True,slurm_job_id=os.environ['SLURM_JOB_ID'])
    (out/'figure_review.json').write_text(json.dumps(stamp,indent=2)+'\n')
    print(json.dumps(stamp),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    args=parser.parse_args();main(args.root)
