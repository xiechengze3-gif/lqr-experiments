"""Incremental 50d reporting with pending outcomes distinct from failures."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np


def csv_write(path,rows):
    if not rows:return
    keys=sorted(set().union(*(r.keys() for r in rows)))
    with path.open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(rows)


def report(cfg,out):
    dest=out/'report';dest.mkdir(parents=True,exist_ok=True)
    rows,completed=[],{}
    expected_identity=json.loads((out/'verification.json').read_text())['identity']
    for algorithm in cfg['algorithms']:
        completed[algorithm]=0
        for task in cfg['tasks']:
            path=out/algorithm/'raw'/f"task-{task['id']:03d}.json"
            if not path.exists():continue
            payload=json.loads(path.read_text())
            assert payload['task']==task and payload['algorithm']==algorithm
            assert payload['identity']==expected_identity
            schedule=cfg['schedules'][algorithm]
            assert len(payload['records'])==len(cfg['methods'])*(len(schedule)+1)
            completed[algorithm]+=1
            for row in payload['records']:
                if row.get('threshold') is not None:
                    assert row['retained_rank']==sum(x>row['threshold'] for x in row['singular_values'])
                rows.append(dict(task,**{k:v for k,v in row.items() if not isinstance(v,(dict,list))}))
    csv_write(dest/'all_records.csv',rows)
    endpoints,thresholds=[],[]
    for algorithm in cfg['algorithms']:
        for spectrum in sorted({t['spectrum'] for t in cfg['tasks']}):
            for policy in sorted({t['policy_seed'] for t in cfg['tasks']}):
                planned=[t for t in cfg['tasks'] if t['spectrum']==spectrum and t['policy_seed']==policy]
                for method in cfg['methods']:
                    final=[r for r in rows if r['algorithm']==algorithm and r['spectrum']==spectrum
                        and r['policy_seed']==policy and r['method']==method and r['stage']==len(cfg['schedules'][algorithm])]
                    values=[r['gap'] if r['stable'] else np.inf for r in final]
                    median=float(np.median(values)) if values else None
                    endpoints.append(dict(algorithm=algorithm,spectrum=spectrum,policy_seed=policy,
                        initial_strength=planned[0]['initial_strength'],method=method,planned=len(planned),
                        complete=len(final),pending=len(planned)-len(final),stable=sum(r['stable'] for r in final),
                        median_gap_including_failures=None if median is None or not np.isfinite(median) else median,
                        median_infinite=median is not None and not np.isfinite(median),
                        median_rank=float(np.median([r['retained_rank'] for r in final if 'retained_rank' in r]))
                                    if any('retained_rank' in r for r in final) else None))
                    for task in planned:
                        trajectory=sorted([r for r in rows if r['id']==task['id'] and r['algorithm']==algorithm
                            and r['method']==method and r['stage']>0],key=lambda r:r['stage'])
                        for eps in cfg['targets']:
                            complete=len(trajectory)==len(cfg['schedules'][algorithm])
                            hit=next((r for i,r in enumerate(trajectory) if all(x['stable'] and x['gap']<=eps for x in trajectory[i:])),None) if complete else None
                            thresholds.append(dict(task_id=task['id'],algorithm=algorithm,method=method,
                                spectrum=spectrum,policy_seed=policy,system_seed=task['system_seed'],
                                trial_seed=task['trial_seed'],epsilon=eps,transitions=hit['transitions'] if hit else None,
                                status='attained' if hit else ('censored' if complete else 'pending')))
    csv_write(dest/'endpoints.csv',endpoints);csv_write(dest/'sustained_thresholds.csv',thresholds)
    summary=dict(status='COMPLETE' if all(n==len(cfg['tasks']) for n in completed.values()) else 'RUNNING',
        completed=completed,planned_each=len(cfg['tasks']),dimension=50,threshold='empirical_split_disagreement',
        initial_outside_fraction=.92,pending_distinct_from_failure=True)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    if rows:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        spectra=sorted({t['spectrum'] for t in cfg['tasks']})
        colors=dict(zip(cfg['methods'],['#555555','#167a39','#56b4e9','#0072b2','#d55e00']))
        fig,axes=plt.subplots(len(spectra),len(cfg['algorithms']),figsize=(18,11),squeeze=False)
        for i,spectrum in enumerate(spectra):
            for j,algorithm in enumerate(cfg['algorithms']):
                ax=axes[i,j]
                for method in cfg['methods']:
                    points=[]
                    for stage in range(1,len(cfg['schedules'][algorithm])+1):
                        group=[r for r in rows if r['spectrum']==spectrum and r['algorithm']==algorithm
                            and r['method']==method and r['stage']==stage]
                        if not group:continue
                        value=float(np.median([r['gap'] if r['stable'] else np.inf for r in group]))
                        if np.isfinite(value):points.append((group[0]['transitions'],max(value,1e-12)))
                    if points:ax.plot(*zip(*points),label=method,color=colors[method])
                if not ax.lines:
                    ax.set_xlim(1,1e9);ax.set_ylim(1e-4,1e3)
                    cell_rows=[r for r in rows if r['spectrum']==spectrum and r['algorithm']==algorithm]
                    ax.text(.5,.5,'No finite median' if cell_rows else 'Pending',transform=ax.transAxes,ha='center')
                ax.set_xscale('log');ax.set_yscale('log');ax.grid(alpha=.2)
                ax.set_title(f'{algorithm} / {spectrum}');ax.set_xlabel('Scheduled transitions');ax.set_ylabel('Absolute gap')
        handles,labels=next((ax.get_legend_handles_labels() for ax in axes.ravel() if ax.lines),([],[]))
        fig.legend(handles,labels,loc='upper center',ncol=5)
        total_complete=sum(completed.values());total_planned=len(cfg['tasks'])*len(cfg['algorithms'])
        fig.suptitle(f'50d, initial policies outside subspace; {total_complete}/{total_planned} configurations complete; failures included',y=.95)
        fig.tight_layout(rect=(0,0,1,.92));fig.savefig(dest/'learning.png',dpi=160);plt.close(fig)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(report(json.loads(a.manifest.read_text()),a.output)))
