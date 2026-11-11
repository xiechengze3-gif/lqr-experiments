"""Separate exact/approximate value curves, rank choices and all failures."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();cfg=json.loads(a.manifest.read_text());dest=a.output/'report';dest.mkdir(parents=True,exist_ok=True)
    ident=json.loads((a.output/'verification.json').read_text())['identity'];rows=[];endpoints=[];done=0;partial=0
    for case in cfg['tasks']:
        baseline=json.loads((a.output/'baselines'/f"case-{case['id']:03d}.json").read_text())
        assert baseline['reuse_provenance']['new_identity']==ident
        combined=list(baseline['records']);raw=a.output/'adaptive/raw'/f"case-{case['id']:03d}.json"
        ckpt=a.output/'adaptive/checkpoints'/f"case-{case['id']:03d}.npz"
        if raw.exists():
            data=json.loads(raw.read_text());assert data['identity']==ident;combined+=data['records'];done+=1
        elif ckpt.exists():
            with np.load(ckpt,allow_pickle=False) as archive:
                assert json.loads(str(archive['identity']))==ident;combined+=json.loads(str(archive['records']))
            partial+=1
        t=case['original_task'];used=sum(case['burn']+(n+1)*case['horizon'] for n in case['schedule'])
        for r in combined:
            rows.append(dict(case_id=case['id'],benchmark=case['benchmark'],rank=t['r'],seed=t['system_seed'],
                tail=t.get('level',0.),origin='new_adaptive' if r['method']=='adaptive_1' else 'historical_baseline',
                **{k:v for k,v in r.items() if not isinstance(v,(list,dict))}))
        for method in cfg['methods']:
            records=[r for r in combined if r['method']==method]
            last=records[-1] if records else {}
            first_failure=next((r for r in records if r.get('observed',True) and not r['stable']),None)
            endpoints.append(dict(case_id=case['id'],benchmark=case['benchmark'],rank=t['r'],seed=t['system_seed'],
                tail=t.get('level',0.),method=method,stage=last.get('stage'),planned_stages=len(case['schedule']),
                complete=last.get('stage')==len(case['schedule']),assigned_budget=used,cost=last.get('cost'),gap=last.get('gap'),
                retained_rank=last.get('retained_rank'),failure=first_failure.get('failure','historical_failure') if first_failure else None))
    for name,values in [('records.csv',rows),('endpoints.csv',endpoints)]:
        fields=sorted(set().union(*(r.keys() for r in values)))
        with (dest/name).open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(values)
    summary=dict(status='COMPLETE' if done==len(cfg['tasks']) else 'RUNNING',planned_adaptive=len(cfg['tasks']),
                 completed_adaptive=done,partial_adaptive=partial,historical_baseline_trajectories=2*len(cfg['tasks']),
                 baseline_provenance='Original sources and per-case first stochastic updates numerically verified; historical curves retained.',identity=ident)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'raw':'#666666','truncated':'#219146','adaptive_1':'#0072b2'}
    labels={'raw':'Dense (historical)','truncated':'Fixed-r (historical)','adaptive_1':'Adaptive c=1 (new)'}
    for benchmark,values in [('rank80',[1,2,4,8,16]),('tail256',[0.,.01,.03,.1])]:
        for metric,ylabel in [('cost','True average cost J(K)'),('gap','Absolute optimality gap'),('retained_rank','Adaptive retained rank')]:
            fig,axes=plt.subplots(2,len(values),figsize=(3.8*len(values),7),squeeze=False)
            for i,seed in enumerate([0,1]):
                for j,value in enumerate(values):
                    ax=axes[i,j]
                    cohort=[r for r in rows if r['benchmark']==benchmark and r['seed']==seed
                            and (r['rank']==value if benchmark=='rank80' else r['tail']==value)]
                    if not any(r['method']=='adaptive_1' and r['stage']>0 for r in cohort):
                        ax.text(.03,.04,'Adaptive: pending',transform=ax.transAxes,color=colors['adaptive_1'],fontsize=8)
                    for method in cfg['methods']:
                        points=[r for r in cohort if r['method']==method and r.get('observed',True)
                                and r['stable'] and r.get(metric) is not None]
                        ax.plot([r.get('actual_transitions',r['transitions'])/1e6 for r in points],
                                [max(r[metric],1e-12) if metric=='gap' else r[metric] for r in points],
                                color=colors[method],label=labels[method],lw=1.5)
                        failure=next((r for r in cohort if r['method']==method and r.get('observed',True) and not r['stable']),None)
                        if failure:
                            ax.plot([failure.get('actual_transitions',failure['transitions'])/1e6],[.96],marker='x',
                                    color=colors[method],transform=ax.get_xaxis_transform())
                    if metric=='gap':ax.set_yscale('log')
                    ax.grid(alpha=.2);ax.set_xlabel('Actual transitions (millions)');ax.set_ylabel(ylabel)
                    ax.set_title(f"{'Exact r='+str(value) if benchmark=='rank80' else 'Head r=4; tail='+str(value)} | seed {seed}",fontsize=10)
            fig.suptitle(f'100d historical setup: {benchmark} | original step and growing batches\nHistorical baselines; adaptive curves may be partial; x marks failed update')
            fig.legend(*axes[0,0].get_legend_handles_labels(),loc='lower center',ncol=3,frameon=False)
            fig.tight_layout(rect=(0,.05,1,.9));fig.savefig(dest/f'{benchmark}_{metric}.png',dpi=150);plt.close(fig)
    print(json.dumps(summary))


if __name__=='__main__':main()
