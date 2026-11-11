"""Approximate-rank complete CE/PI subsets and zero-sample floor references."""
import argparse,json,os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dense_scaling import require_compute,system,evaluate,targets,pi_gain,dare,trunc,atomic_json


def main(release,root):
    release,root=Path(release),Path(root);records=[];refs=[]
    tasks=json.loads((release/'configs/cross_rank_ce.json').read_text())['tasks']
    for tid,task in enumerate(tasks):
        if task['n'] not in (50,100) or task['r']!=4:continue
        s=system(task)
        for algorithm,profile in (('CE','ce'),('PI-LSTD','pi-524288')):
            payload=json.loads((root/profile/'raw'/f'task-{tid:03d}.json').read_text())
            assert payload['task']==task
            for method in ('raw','truncated'):
                row=[r for r in payload['records'] if r['method']==method][-1]
                records.append(dict(algorithm=algorithm,n=task['n'],seed=task['system_seed'],tail=task['tail'],method=method,**row))
            if algorithm=='CE':
                k,_=dare(s['A'],trunc(s['B'],4),s['Q'],s['R'])
            else:
                k=s['K0'].copy()
                for stage in range(6):
                    t=targets(s,k,16);k,_,_=pi_gain(s,t['G'],t['C'],4)
            quality,_=evaluate(s,k)
            refs.append(dict(algorithm=algorithm,n=task['n'],seed=task['system_seed'],tail=task['tail'],**quality))
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    for col,algorithm in enumerate(('CE','PI-LSTD')):
        for row,n in enumerate((50,100)):
            ax=axes[row,col]
            for method,color in (('raw','#c44e52'),('truncated','#4c72b0')):
                xx=[];yy=[]
                for i,tail in enumerate((0.,.01,.1,.3)):
                    group=[r for r in records if (r['algorithm'],r['n'],r['method'],r['tail'])==(algorithm,n,method,tail)]
                    assert len(group)==2
                    if all(r['stable'] for r in group):xx.append(i);yy.append(max(1e-12,float(np.mean([r['gap'] for r in group]))))
                ax.plot(xx,yy,marker='o',color=color,label=f'sampled {method}')
            vals=[]
            for tail in (.01,.1,.3):
                group=[r for r in refs if (r['algorithm'],r['n'],r['tail'])==(algorithm,n,tail)]
                assert len(group)==2 and all(r['stable'] for r in group)
                vals.append(max(1e-12,float(np.mean([r['gap'] for r in group]))))
            ax.plot([1,2,3],vals,color='#55a868',linestyle='--',marker='s',label='exact truncated reference (zero samples)')
            ax.set(yscale='log',xlabel='Frobenius tail of B (categorical positions)',ylabel='Mean absolute gap (2 systems)',title=f'{algorithm}, n={n}, r=4, largest tested budget')
            ax.set_xticks(range(4),['0','.01','.1','.3']);ax.grid(alpha=.2);ax.legend(fontsize=8)
    out=root/'preview';fig.savefig(out/'pi_ce_tail_complete.png',dpi=180);fig.savefig(out/'pi_ce_tail_complete.pdf');plt.close(fig)
    atomic_json(out/'pi_ce_tail_complete.json',dict(records=records,exact_truncated_references=refs,
        interpretation='CE 2097152 regression transitions +512 burn; PI six stages of 524288 transitions +1024 burn each. Green is a zero-sample model-truth reference only; two systems, exploratory. Exact-rank oracle points omitted from log plot because their gap is numerically zero.',slurm_job_id=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();main(a.release,a.output)
