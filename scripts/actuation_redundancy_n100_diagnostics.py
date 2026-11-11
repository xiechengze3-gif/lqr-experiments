"""Descriptive failure timing for n100; never optimizer inputs or attainment."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main(out):
    out=Path(out);cfg=json.loads((out/'resolved_config.json').read_text())
    assert cfg['n']==100
    events=[]
    for path in sorted((out/'raw').glob('*.json')):
        data=json.loads(path.read_text());assert data['identity']==cfg['identity']
        for method in cfg['methods']:
            rows=[r for r in data['records'] if r['method']==method]
            failures=[r for r in rows if r.get('failure') in ('controller_instability','numerical_failure')]
            first=failures[0] if failures else None
            events.append(dict(m=data['m'],seed=data['seed'],method=method,
                               event=first['failure'] if first else 'right_censored',
                               failure_stage=first['stage'] if first else None,
                               failure_transitions=first['actual_transitions'] if first else None,
                               failure_rho=first.get('rho') if first else None,
                               assigned_budget=rows[-1]['transitions'],
                               actual_used_transitions=rows[-1]['actual_transitions']))
    assert len(events)==200
    summary=[]
    for m in cfg['action_dimensions']:
        for method in cfg['methods']:
            group=[r for r in events if r['m']==m and r['method']==method]
            assert len(group)==20
            row=dict(m=m,method=method,seeds=20,
                     instability_count=sum(r['event']=='controller_instability' for r in group),
                     numerical_failure_count=sum(r['event']=='numerical_failure' for r in group),
                     right_censored_count=sum(r['event']=='right_censored' for r in group))
            for key in ('failure_stage','failure_transitions'):
                values=[r[key] for r in group if r[key] is not None]
                for metric,q in [('median',.5),('q25',.25),('q75',.75)]:
                    row[key+'_'+metric]=float(np.quantile(values,q)) if values else None
            summary.append(row)
    report=out/'report';write_csv(report/'failure_events.csv',events);write_csv(report/'failure_timing.csv',summary)
    colors={'dense':'#b84a39','truncated':'#2168a1'}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.grid':True,'grid.alpha':.2,'savefig.dpi':180})
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
    for method in cfg['methods']:
        group=[r for r in summary if r['method']==method];x=[r['m'] for r in group]
        for ax,key in zip(axes,('failure_stage','failure_transitions')):
            mid=np.array([r[key+'_median'] if r[key+'_median'] is not None else np.nan for r in group])
            lo=np.array([r[key+'_q25'] if r[key+'_q25'] is not None else np.nan for r in group])
            hi=np.array([r[key+'_q75'] if r[key+'_q75'] is not None else np.nan for r in group])
            ax.errorbar(x,mid,yerr=np.array([mid-lo,hi-mid]),color=colors[method],marker='o',capsize=4,label=method)
            ax.set_xscale('log',base=2);ax.set_xticks(cfg['action_dimensions'],[str(m) for m in cfg['action_dimensions']])
            ax.set_xlabel('Action dimension m');ax.legend()
    axes[0].set_ylabel('Update producing first unstable controller')
    axes[1].set_ylabel('Primitive transitions at first instability')
    fig.suptitle('n=100: failure timing, median and IQR across sampling seeds\nDescriptive only: later instability is not precision attainment')
    for ext in ('png','pdf'):fig.savefig(report/('failure_timing.'+ext))
    plt.close(fig)
    all_failed=all(r['right_censored_count']==0 for r in summary)
    if all_failed:
        for stem,title in [('fixed_budget_excess','Fixed-budget absolute excess cost'),
                           ('loss_decomposition','Offline loss decomposition at the final budget')]:
            fig,ax=plt.subplots(figsize=(11,4),constrained_layout=True);ax.axis('off')
            ax.text(.5,.75,title,ha='center',fontsize=17)
            ax.text(.5,.43,'All 20/20 seeds failed in every method / action-dimension cell.\nNo stable final output: infinite-horizon final costs and components are undefined.',
                    ha='center',va='center',fontsize=12,linespacing=1.7)
            ax.text(.5,.12,'Stable pre-failure costs and loss components remain in all_checkpoints.csv.\nFailures remain in all success-rate denominators; no zero-cost imputation.',ha='center',fontsize=10)
            for ext in ('png','pdf'):fig.savefig(report/(stem+'.'+ext))
            plt.close(fig)
    note=dict(n=100,events=events,summary=summary,all_cells_failed=all_failed,
              interpretation='Failure timing is descriptive, not attainment or proof of successful learning.',
              source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),identity=cfg['identity'])
    (report/'n100_diagnostics.json').write_text(json.dumps(note,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(diagnostics='PASS',all_cells_failed=all_failed,summary=summary)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
