"""A clearly labelled one-system preview from finished Grace simulations."""
import argparse
import json
from pathlib import Path
import numpy as np
from dense_scaling import require_compute


def main(root):
    root=Path(root)
    reference=json.loads((root/'reference.json').read_text())['records']
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    colors={1:'#2b6cb0',2:'#15977d',4:'#d8961f',8:'#b34578',16:'#684da4'}
    fig,axes=plt.subplots(1,2,figsize=(13,4.8))
    endpoint={'raw':[],'truncated':[],'exact':[]}
    for tid,r in enumerate([1,2,4,8,16]):
        payload=json.loads((root/'raw'/f'task-{tid:03d}.json').read_text())
        assert payload['task']['n']==50 and payload['task']['r']==r and payload['task']['system_seed']==0
        for method,style in [('raw','--'),('truncated','-')]:
            rows=sorted([x for x in payload['records'] if x['method']==method],key=lambda x:x['stage'])
            assert len(rows)==81
            plotted=rows[1:]
            axes[0].loglog([x['transitions'] for x in plotted],
                [x['gap'] if x['stable'] else np.nan for x in plotted],style,color=colors[r],linewidth=1.8)
            endpoint[method].append(rows[-1]['gap'] if rows[-1]['stable'] else np.nan)
        endpoint['exact'].append(next(x['gap'] for x in reference if x['n']==50 and x['r']==r and x['system_seed']==0
            and x['stage']==80 and not x['finite_horizon']))
    axes[0].set_title('Learning curves at paired sample budgets')
    axes[0].set_xlabel('Cumulative primitive transitions');axes[0].set_ylabel('Absolute cost gap')
    handles=[Line2D([],[],color=colors[r],label=f'r={r}') for r in colors]
    handles += [Line2D([],[],color='black',linestyle='--',label='raw'),Line2D([],[],color='black',label='truncated')]
    axes[0].legend(handles=handles,ncol=2,fontsize=8)
    for method,color,style in [('raw','#777','--'),('truncated','#12699c','-'),('exact','#269b62',':')]:
        axes[1].semilogx(list(colors),endpoint[method],'o'+style,color=color,label=method+' critic' if method=='exact' else method)
    axes[1].set_title('Final gap after 80 updates / identical total budget')
    axes[1].set_xlabel('Rank of B');axes[1].set_ylabel('Absolute cost gap')
    axes[1].set_xticks(list(colors),labels=list(colors));axes[1].legend(fontsize=9)
    for ax in axes:ax.grid(alpha=.22)
    fig.suptitle('PRELIMINARY: n=m=50, system seed 0 only\nDense unstable LQR; identical K0, step size and batch schedule; full two-system/dimension study still running',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.88))
    fig.savefig(root/'report/preview_50d_seed0.png',dpi=180,bbox_inches='tight')
    plt.close(fig)
    (root/'report/preview_50d_seed0.json').write_text(json.dumps(dict(n=50,system_seed=0,stages=80,endpoint=endpoint,
        inference='One-system preliminary visualization. No dimension/rank complexity fit or population claim.'),indent=2)+'\n')
    print(json.dumps(endpoint),flush=True)


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();main(a.output)
