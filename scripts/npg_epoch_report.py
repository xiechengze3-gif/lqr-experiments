"""Audit and plot the frozen equal-budget epoch pilot on Grace."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from dense_scaling import atomic_json, require_compute


def csv_write(path, rows):
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)


def thresholds(rows, eps, window):
    good=[row['observed'] and row['stable'] and row['gap'] is not None and row['gap']<=eps for row in rows]
    first=next((i for i in range(len(rows)) if good[i]),None)
    confirmed=next((i+window-1 for i in range(len(rows)-window+1) if all(good[i:i+window])),None)
    sustained=next((i+window-1 for i in range(len(rows)-window+1) if all(good[i:])),None)
    return dict(epsilon=eps,
        first_hit=rows[first]['transitions'] if first is not None else None,
        confirmed_window=rows[confirmed]['transitions'] if confirmed is not None else None,
        sustained=rows[sustained]['transitions'] if sustained is not None else None,
        final_attained=bool(good[-1]),failed=not all(row['stable'] for row in rows))


def main(manifest, output):
    manifest,root=Path(manifest),Path(output)
    config=json.loads(manifest.read_text())
    digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
    runner_hash=hashlib.sha256((manifest.parent.parent/'scripts/npg_epoch_budget.py').read_bytes()).hexdigest()
    records,endpoint,per_run=[],[],[]
    for tid,task in enumerate(config['tasks']):
        path=root/'raw'/f'task-{tid:03d}.json'
        if not path.exists():raise RuntimeError(f'Missing task {tid}')
        payload=json.loads(path.read_text())
        assert payload['task']==task and payload['manifest_sha256']==digest
        assert payload['source_sha256']==runner_hash
        schedule=config['schedules'][task['schedule_id']]
        expected=sum(config['burn']+(count+1)*config['horizon'] for count in schedule)
        assert payload['planned_total_transitions']==expected
        for method in config['methods']:
            rows=sorted((row for row in payload['records'] if row['method']==method),key=lambda row:row['stage'])
            assert [row['stage'] for row in rows]==list(range(config['stages']+1))
            total=0
            for stage,row in enumerate(rows):
                if stage:
                    assert row['N']==schedule[stage-1]
                    if row['observed']:total+=config['burn']+(row['N']+1)*config['horizon']
                assert row['transitions']==total
            last=rows[-1]
            if last['stable']:assert last['transitions']==expected and last['observed']
            endpoint.append(dict(task_id=tid,**task,method=method,stage=last['stage'],
                gap=last['gap'],stable=last['stable'],observed=last['observed'],
                actual_transitions=last['transitions'],planned_transitions=expected))
            for eps in config['tolerances']:
                per_run.append(dict(task_id=tid,**task,method=method,**thresholds(rows,eps,config['threshold_window'])))
        records.extend(dict(task_id=tid,**task,**row) for row in payload['records'])
    reference=json.loads((root/'reference.json').read_text())
    assert reference['manifest_sha256']==digest
    exact=[row for row in reference['records'] if row['stage']==config['stages'] and not row['finite_horizon']]
    assert len(exact)==4 and all(row['stable'] for row in exact)
    grouped=defaultdict(list)
    for row in endpoint:grouped[row['r'],row['final_batch_label'],row['schedule_kind'],row['method']].append(row)
    aggregate=[]
    for (rank,final,kind,method),rows in sorted(grouped.items()):
        assert len(rows)==2
        good=all(row['stable'] and row['observed'] and row['gap'] is not None for row in rows)
        gaps=[row['gap'] for row in rows] if good else []
        aggregate.append(dict(r=rank,final_batch_label=final,schedule_kind=kind,method=method,
            systems=len(rows),stable_systems=sum(row['stable'] for row in rows),
            planned_transitions=rows[0]['planned_transitions'],gap_mean=float(np.mean(gaps)) if good else None,
            gap_min=min(gaps) if good else None,gap_max=max(gaps) if good else None,
            successes={str(eps):sum(row['stable'] and row['gap'] is not None and row['gap']<=eps for row in rows)
                       for eps in config['tolerances']}))
    comparisons=[]
    lookup={(row['r'],row['final_batch_label'],row['schedule_kind'],row['method']):row for row in aggregate}
    for rank in (1,4):
        for final in config['final_batches']:
            for method in config['methods']:
                a,b=lookup[rank,final,'constant',method],lookup[rank,final,'geometric',method]
                assert a['planned_transitions']==b['planned_transitions']
                comparisons.append(dict(r=rank,final_batch_label=final,method=method,
                    planned_transitions=a['planned_transitions'],constant_gap=a['gap_mean'],geometric_gap=b['gap_mean'],
                    constant_over_geometric=a['gap_mean']/b['gap_mean'] if a['gap_mean'] is not None and b['gap_mean'] else None))
    grid_minimum=[]
    for rank in (1,4):
        for method in config['methods']:
            candidates=[row for row in aggregate if row['r']==rank and row['method']==method]
            for eps in config['tolerances']:
                successful=[row for row in candidates if row['successes'][str(eps)]==row['systems']]
                budget=min((row['planned_transitions'] for row in successful),default=None)
                grid_minimum.append(dict(r=rank,method=method,epsilon=eps,minimum_budget=budget,
                    attaining_schedules=[row['schedule_kind'] for row in successful if row['planned_transitions']==budget],
                    right_censored=budget is None,left_censored=budget is not None and budget==min(row['planned_transitions'] for row in candidates),
                    interpretation='Exploratory minimum on this two-budget/two-schedule grid; fixed output stage; not a learner stopping rule.'))
    out=root/'report';out.mkdir(parents=True,exist_ok=True)
    csv_write(out/'records.csv',records);csv_write(out/'endpoints_per_run.csv',endpoint)
    csv_write(out/'thresholds_per_run.csv',per_run);csv_write(out/'equal_budget_comparison.csv',comparisons)
    csv_write(out/'grid_minimum_budgets.csv',grid_minimum)
    summary=dict(status='complete',configurations=len(config['tasks']),sampled_methods=len(endpoint),
        stable_methods=sum(row['stable'] for row in endpoint),outer_stages=config['stages'],
        manifest_sha256=digest,runner_sha256=runner_hash,aggregate=aggregate,comparisons=comparisons,
        grid_minimum=grid_minimum,exact_final=exact,
        caveats=['Two independent systems and one trajectory each per arm: exploratory pilot.',
                 'Schedule is predetermined, not data-adaptive; constant/geometric have equal total budget.',
                 'Final-stage gaps and first/confirmed/sustained attainment are separate metrics.',
                 'No dimension, rank or accuracy exponent can be identified from this pilot.'])
    atomic_json(out/'summary.json',summary)
    atomic_json(out/'numerical_audit.json',dict(status='PASS',manifest_sha256=digest,
        tests=['frozen runner and manifest provenance','all planned configurations and stages present',
               'actual transitions counted; failure padding does not add uncollected samples',
               'constant and geometric total budgets exactly equal','exact references complete and stable'],
        configurations=len(config['tasks']),sampled_methods=len(endpoint),stable_methods=summary['stable_methods']))
    plots(config,records,aggregate,out)
    print(json.dumps(dict(status='complete',configurations=len(config['tasks']),stable_methods=summary['stable_methods'],
                          comparisons=comparisons,grid_minimum=grid_minimum)),flush=True)


def plots(config,records,aggregate,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    colors={'raw':'#777777','truncated':'#12699c'}
    styles={'constant':'--','geometric':'-'}
    labels=[Line2D([],[],color=colors[method],linestyle=styles[kind],label=f'{method}, {kind}')
            for method in config['methods'] for kind in ('constant','geometric')]
    fig,axes=plt.subplots(1,2,figsize=(11.5,4.8))
    for ax,rank in zip(axes,(1,4)):
        for method in config['methods']:
            for kind in ('constant','geometric'):
                rows=sorted((row for row in aggregate if row['r']==rank and row['method']==method and row['schedule_kind']==kind),
                            key=lambda row:row['planned_transitions'])
                good=[row for row in rows if row['gap_mean'] is not None]
                ax.plot([row['planned_transitions']/1e6 for row in good],[row['gap_mean'] for row in good],
                        ('s' if kind=='constant' else 'o')+styles[kind],color=colors[method],label=f'{method}, {kind}')
                for row in good:ax.vlines(row['planned_transitions']/1e6,row['gap_min'],row['gap_max'],color=colors[method],alpha=.5)
                for row in rows:
                    if row['gap_mean'] is None:ax.text(row['planned_transitions']/1e6,2.5,f'failed {method}/{kind}',rotation=70,fontsize=7)
        ax.set_yscale('log');ax.set_xscale('log')
        ax.set_title(f'n=50, rank={rank}');ax.set_xlabel('Total primitive transitions (millions)');ax.set_ylabel('Final absolute gap')
        for eps in (.25,.5,1.,2.):ax.axhline(eps,color='#999',linewidth=.6,alpha=.4)
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Equal total samples: constant versus epoch-growing NPG\n128 updates; mean and range of two independent systems')
    fig.tight_layout(rect=(0,0,1,.90))
    save(fig,out,'endpoint_equal_budget',plt)
    fig,axes=plt.subplots(2,2,figsize=(12,8),squeeze=False)
    for i,rank in enumerate((1,4)):
        for j,final in enumerate(config['final_batches']):
            ax=axes[i,j]
            for method in config['methods']:
                for kind in ('constant','geometric'):
                    groups=defaultdict(list)
                    for row in records:
                        if row['r']==rank and row['final_batch_label']==final and row['method']==method and row['schedule_kind']==kind:
                            groups[row['stage']].append(row)
                    xs=sorted(groups);ys=[]
                    for stage in xs:
                        rows=groups[stage]
                        ys.append(float(np.mean([row['gap'] for row in rows])) if all(row['stable'] and row['observed'] and row['gap'] is not None for row in rows) else np.nan)
                    ax.semilogy(xs,ys,styles[kind],color=colors[method])
            ax.set_title(f'rank={rank}; geometric final batch={final:,}')
            ax.set_xlabel('NPG updates');ax.set_ylabel('Absolute gap');ax.grid(alpha=.2)
    axes[0,0].legend(handles=labels,fontsize=8)
    fig.suptitle('Same update count and total budget within each panel\nDifferent within-run allocation; all failed runs retained in summaries')
    fig.tight_layout(rect=(0,0,1,.92));save(fig,out,'stage_convergence',plt)
    fig,ax=plt.subplots(figsize=(8,4))
    for final in config['final_batches']:
        for kind in ('constant','geometric'):
            ax.step(range(1,config['stages']+1),config['schedules'][f'{kind}-{final}'],where='post',
                    linestyle=styles[kind],label=f'{kind}; tier {final:,}')
    ax.set_yscale('log',base=2);ax.set_xlabel('NPG update');ax.set_ylabel('Pulse blocks per update')
    ax.set_title('Frozen allocation schedules (equal totals within each tier)');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.tight_layout();save(fig,out,'sampling_schedule',plt)


def save(fig,out,name,plt):
    for ext in ('png','pdf'):fig.savefig(out/f'{name}.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':
    require_compute();parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();main(args.manifest,args.output)
