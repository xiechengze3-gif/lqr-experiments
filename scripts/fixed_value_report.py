"""Value/gap curves and paired fixed-budget endpoints, with explicit failures."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np


def write_csv(path,rows):
    if not rows:return
    fields=sorted(set().union(*(r.keys() for r in rows)))
    with path.open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def report(cfg,out,scenario=None):
    dest=out/'report';dest.mkdir(parents=True,exist_ok=True)
    ident=json.loads((out/'verification.json').read_text())['identity']
    rows=[];done={a:0 for a in cfg['algorithms']};payloads={}
    for algorithm in cfg['algorithms']:
        for task in cfg['tasks']:
            path=out/algorithm/'raw'/f"task-{task['id']:03d}.json"
            if not path.exists():continue
            p=json.loads(path.read_text());assert p['identity']==ident and p['task']==task
            methods=cfg['sensitivity_methods'] if task['scenario'] in cfg['sensitivity_scenarios'] else cfg['methods']
            stages=cfg['profiles'][task['profile']][algorithm]['stages']
            assert len(p['records'])==len(methods)*(stages+1)
            done[algorithm]+=1;payloads[(algorithm,task['id'])]=p
            for r in p['records']:
                assert r['actual_transitions']<=r['transitions']
                if r.get('threshold') is not None:
                    assert r['retained_rank']==sum(x>r['threshold'] for x in r['singular_values'])
                rows.append(dict(task,**{k:v for k,v in r.items() if not isinstance(v,(dict,list))}))
    write_csv(dest/'all_records.csv',rows)
    endpoints=[];paired=[]
    for case in sorted({t['scenario'] for t in cfg['tasks']}):
        for profile in sorted({t['profile'] for t in cfg['tasks'] if t['scenario']==case}):
            tasks=[t for t in cfg['tasks'] if t['scenario']==case and t['profile']==profile]
            methods=cfg['sensitivity_methods'] if case in cfg['sensitivity_scenarios'] else cfg['methods']
            for algorithm in cfg['algorithms']:
                stages=cfg['profiles'][profile][algorithm]['stages']
                for method in methods:
                    final=[r for r in rows if r['scenario']==case and r['profile']==profile and
                           r['algorithm']==algorithm and r['method']==method and r['stage']==stages]
                    types=[]
                    for task in tasks:
                        p=payloads.get((algorithm,task['id']))
                        if p:
                            first=next((r for r in p['records'] if r['method']==method and r.get('failure_kind')),None)
                            if first:types.append(first['failure_kind'])
                    medians={}
                    for metric in ('gap','value'):
                        values=[r[metric] if r['stable'] else np.inf for r in final]
                        med=float(np.median(values)) if values else None
                        medians[metric+'_median']=med if med is not None and np.isfinite(med) else None
                        medians[metric+'_median_infinite']=med is not None and not np.isfinite(med)
                    ranks=[r['retained_rank'] for r in final if r.get('retained_rank') is not None]
                    endpoints.append(dict(scenario=case,profile=profile,algorithm=algorithm,method=method,
                        planned=len(tasks),complete=len(final),pending=len(tasks)-len(final),stable=sum(r['stable'] for r in final),
                        numerical_failures=types.count('numerical_solver'),instability=types.count('controller_instability'),
                        update_failures=types.count('update_failure'),median_retained_rank=float(np.median(ranks)) if ranks else None,
                        assigned_total_budget=final[0]['assigned_total_budget'] if final else None,**medians))
                for task in tasks:
                    p=payloads.get((algorithm,task['id']))
                    if not p:continue
                    finals={r['method']:r for r in p['records'] if r['stage']==stages}
                    a,b=finals['dense'],finals['adaptive_1']
                    assert a['transitions']==b['transitions']
                    valid=a['stable'] and b['stable']
                    paired.append(dict(task,algorithm=algorithm,assigned_budget=p['assigned_total_budget'],
                        paired_finite=valid,dense_stable=a['stable'],adaptive_stable=b['stable'],
                        dense_gap=a.get('gap'),adaptive_gap=b.get('gap'),
                        adaptive_minus_dense_gap=b['gap']-a['gap'] if valid else None,
                        dense_over_adaptive_gap=a['gap']/b['gap'] if valid and b['gap']>0 else None))
    write_csv(dest/'endpoints.csv',endpoints);write_csv(dest/'paired_endpoints.csv',paired)
    summary=dict(status='COMPLETE' if all(n==len(cfg['tasks']) for n in done.values()) else 'RUNNING',
        completed=done,planned_each=len(cfg['tasks']),scenarios=len({t['scenario'] for t in cfg['tasks']}),
        primary='fixed-budget value/gap curves and endpoints',numerical_failure_separate_from_instability=True,
        samples='primitive transitions, including burn-in and pulse baseline',identity=ident)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    if rows:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        colors={'dense':'#555555','known_rank':'#167a39','adaptive_0.5':'#56b4e9','adaptive_1':'#0072b2','adaptive_2':'#d55e00'}
        selected=[scenario] if scenario else sorted({r['scenario'] for r in rows})
        for case in selected:
            profiles=sorted({t['profile'] for t in cfg['tasks'] if t['scenario']==case},key=lambda p:('low','standard','high').index(p))
            for metric,label in (('value','True average cost J(K)'),('gap','Absolute optimality gap'),('retained_rank','Retained rank (available estimates)')):
                fig,axes=plt.subplots(len(profiles),len(cfg['algorithms']),figsize=(16,4*len(profiles)),squeeze=False)
                for i,profile in enumerate(profiles):
                    for j,algorithm in enumerate(cfg['algorithms']):
                        ax=axes[i,j]
                        methods=cfg['sensitivity_methods'] if case in cfg['sensitivity_scenarios'] else cfg['methods']
                        stages=cfg['profiles'][profile][algorithm]['stages']
                        for method in methods:
                            xs,ys=[],[]
                            for stage in range(1,stages+1):
                                group=[r for r in rows if r['scenario']==case and r['profile']==profile and
                                       r['algorithm']==algorithm and r['method']==method and r['stage']==stage]
                                if not group:continue
                                vals=[r.get(metric) if (metric=='retained_rank' or r['stable']) else np.inf for r in group]
                                vals=[v for v in vals if v is not None]
                                if not vals:continue
                                med=float(np.median(vals))
                                if np.isfinite(med):xs.append(group[0]['transitions']);ys.append(max(med,1e-12) if metric!='retained_rank' else med)
                                if metric!='retained_rank' and any(not r['stable'] for r in group):
                                    ax.plot([group[0]['transitions']],[.98-.025*methods.index(method)],'x',
                                        color=colors[method],transform=ax.get_xaxis_transform())
                            if xs:ax.plot(xs,ys,label='fixed-r' if method=='known_rank' else method,color=colors[method],lw=1.4)
                        if not any(line.get_transform()==ax.transData for line in ax.lines):
                            ax.set_xlim(1,1e9);ax.set_ylim(1e-3,1e3)
                            available=any(r['scenario']==case and r['profile']==profile and r['algorithm']==algorithm for r in rows)
                            ax.text(.5,.5,'No finite median' if available else 'Pending',ha='center',transform=ax.transAxes)
                        ax.set_xscale('log')
                        if metric!='retained_rank':ax.set_yscale('log')
                        ax.grid(alpha=.2);ax.set_title(f'{algorithm} / {profile}');ax.set_xlabel('Scheduled primitive transitions');ax.set_ylabel(label)
                handles,labels=next((a.get_legend_handles_labels() for a in axes.ravel() if a.get_legend_handles_labels()[0]),([],[]))
                fig.legend(handles,labels,loc='upper center',ncol=5)
                fig.suptitle(f'{case}: predeclared budget and updates; medians include run failures; x = at least one failure',y=.95)
                fig.tight_layout(rect=(0,0,1,.92));fig.savefig(dest/f'{case}_{metric}.png',dpi=160);plt.close(fig)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--scenario')
    a=p.parse_args();print(json.dumps(report(json.loads(a.manifest.read_text()),a.output,a.scenario)))
