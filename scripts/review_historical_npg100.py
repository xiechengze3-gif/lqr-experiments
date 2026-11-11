"""Rebuild the 100d historical NPG comparison from completed task files."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rank-root',type=Path,required=True)
    parser.add_argument('--tail-root',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    manifest=args.rank_root/'source'/'manifest.json'
    cfg=json.loads(manifest.read_text())
    groups={};sources=[]
    for path in (args.rank_root/'raw').glob('task-*.json'):
        data=json.loads(path.read_text());task=data['task']
        if task['n']!=100:continue
        assert data['manifest_sha256']==sha(manifest)
        groups.setdefault(('rank',task['r']),[]).append(data)
        sources.append(dict(path=str(path),sha256=sha(path)))
    levels=[0.,.01,.03,.1]
    for path in (args.tail_root/'npg-524288'/'raw').glob('task-*.json'):
        data=json.loads(path.read_text());task=data['task']
        if task['n']!=100 or task['r']!=4:continue
        if task['tail_mode']=='exact':level=0.
        elif task['tail_mode']=='singular' and task['level'] in levels:level=task['level']
        else:continue
        groups.setdefault(('tail',level),[]).append(data)
        sources.append(dict(path=str(path),sha256=sha(path)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,5,figsize=(18,8))
    summaries=[]
    panels=[('rank',rank) for rank in [1,2,4,8,16]]+[('tail',level) for level in levels]
    for key in panels:
        cohort=groups[key];assert len(cohort)==2
        assert {p['task']['system_seed'] for p in cohort}=={0,1}
        stages=80 if key[0]=='rank' else 256
        col=[1,2,4,8,16].index(key[1]) if key[0]=='rank' else levels.index(key[1])
        ax=axes[0 if key[0]=='rank' else 1,col]
        endpoint=[]
        for method,color,label in [('raw','#666666','Dense'),('truncated','#0072b2','Fixed-r SVD')]:
            records=[[r for r in p['records'] if r['method']==method and r['stage']>0] for p in cohort]
            assert all(len(rows)==stages for rows in records)
            assert all(r['stable'] and r['observed'] for rows in records for r in rows)
            xs=[r['transitions'] for r in records[0]]
            assert xs==[r['transitions'] for r in records[1]]
            vals=np.array([[r['gap'] for r in rows] for rows in records])
            x=np.array(xs)/1e6
            ax.plot(x,np.mean(vals,axis=0),color=color,label=label,lw=1.8)
            ax.fill_between(x,np.min(vals,axis=0),np.max(vals,axis=0),color=color,alpha=.12)
            for p,rows in zip(cohort,records):
                endpoint.append(dict(method=method,seed=p['task']['system_seed'],gap=rows[-1]['gap'],
                                     cost=rows[-1]['cost'],transitions=rows[-1]['transitions']))
        means={m:float(np.mean([r['gap'] for r in endpoint if r['method']==m])) for m in ('raw','truncated')}
        summaries.append(dict(group=key[0],rank=key[1] if key[0]=='rank' else 4,
                              tail_singular=0. if key[0]=='rank' else key[1],
                              stages=stages,endpoints=endpoint,mean_gap=means,
                              dense_over_truncated_gap=means['raw']/means['truncated']))
        title=f'Exact rank {key[1]} | 80 updates' if key[0]=='rank' else f'Rank-4 head; tail={key[1]:g} | 256 updates'
        ax.set_title(title,fontsize=10);ax.set_xscale('log');ax.set_yscale('log')
        ax.set_xlabel('Actual transitions (millions)');ax.set_ylabel('Absolute optimality gap')
        ax.grid(alpha=.2)
    axes[1,4].axis('off')
    axes[1,4].text(.02,.8,'Historical NPG, n=m=100\n\nRank supplied to SVD truncation\nTwo independent systems\nBand = min/max of two systems\n\nTop: growing batches, 80 updates\nBudget: 656,491,776 transitions\n\nBottom: growing batches, 256 updates\nBudget: 671,354,880 transitions\n\nThese runs do not use adaptive rank\nselection.',transform=axes[1,4].transAxes,fontsize=10,va='top')
    fig.suptitle('Previously completed 100d NPG | Rebuilt from original raw task records\n'
                 'Same budget for dense/truncated within each experiment; fixed-r truncation',fontsize=13)
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='lower center',ncol=2,frameon=False)
    fig.tight_layout(rect=(0,.04,1,.92))
    args.destination.mkdir(parents=True,exist_ok=True)
    fig.savefig(args.destination/'npg100_historical_curves.png',dpi=160);plt.close(fig)
    result=dict(known_rank_truncation=True,independent_systems=2,
                rank_manifest_sha256=sha(manifest),rank_schedule=cfg['batch_schedule'],
                summaries=summaries,sources=sources)
    (args.destination/'raw_review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
