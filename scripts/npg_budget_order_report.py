"""Audited total-budget rank/precision comparisons; Slurm compute only."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from dense_scaling import require_compute, atomic_json


def csv_write(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def fit(rows,xkey,ykey,metadata):
    valid=[row for row in rows if row[ykey] is not None and row[ykey]>0
           and not row['left_censored'] and not row['right_censored']]
    if len(valid)<3:
        return dict(**metadata,identified=False,points=len(valid),reason='fewer than three uncensored grid points')
    x=np.log([row[xkey] for row in valid]);y=np.log([row[ykey] for row in valid])
    slope,intercept=np.polyfit(x,y,1);residual=y-(intercept+slope*x)
    spread=float(np.sum((y-np.mean(y))**2))
    return dict(**metadata,identified=True,points=len(valid),slope=float(slope),
        r_squared=1.-float(np.sum(residual**2))/spread if spread>0 else None,
        interpretation='Descriptive log-log fit of measured grid upper endpoints only; no asymptotic or population claim.')


def main(manifest,output,partial=False):
    manifest=Path(manifest);root=Path(output);out=root/'report';out.mkdir(parents=True,exist_ok=True)
    config=json.loads(manifest.read_text());manifest_hash=hashlib.sha256(manifest.read_bytes()).hexdigest()
    release=manifest.parent.parent
    hashes={name:hashlib.sha256((release/'scripts'/name).read_bytes()).hexdigest()
            for name in ('npg_budget_order.py','npg_budget_system.py','npg_batched_collector.py')}
    endpoints,records,missing=[],[],[]
    for tid,task in enumerate(config['tasks']):
        path=root/'raw'/f'task-{tid:03d}.json'
        if not path.exists():missing.append(tid);continue
        payload=json.loads(path.read_text())
        assert payload['task']==task and payload['manifest_sha256']==manifest_hash
        assert payload['source_sha256']==hashes['npg_budget_order.py']
        assert payload['system_sha256']==hashes['npg_budget_system.py']
        assert payload['collector_sha256']==hashes['npg_batched_collector.py']
        schedule=config['schedules'][task['schedule_id']]
        planned=sum(config['burn']+(n+1)*config['horizon'] for n in schedule)
        assert payload['planned_total_transitions']==planned
        for method in config['methods']:
            rows=sorted((row for row in payload['records'] if row['method']==method),key=lambda row:row['stage'])
            assert [row['stage'] for row in rows]==list(range(config['stages']+1))
            total=0;failed=False
            for stage,row in enumerate(rows):
                if stage:
                    assert row['N']==schedule[stage-1]
                    if failed:assert not row['observed'] and not row['stable']
                    if row['observed']:total+=config['burn']+(row['N']+1)*config['horizon']
                assert row['transitions']==total
                failed=failed or not row['stable']
            last=rows[-1]
            if last['stable']:assert last['observed'] and total==planned
            endpoints.append(dict(task_id=tid,**task,method=method,gap=last['gap'],stable=last['stable'],
                actual_transitions=total,planned_transitions=planned))
            records.extend(dict(task_id=tid,**task,**row) for row in rows)
    if missing and not partial:raise RuntimeError(f'Missing tasks: {missing}')
    verification=json.loads((root/'verification.json').read_text())
    assert verification['status']=='PASS' and verification['manifest_sha256']==manifest_hash
    reference=json.loads((root/'reference.json').read_text())
    assert reference['manifest_sha256']==manifest_hash
    # Audit invariant matrices, uniform bounds and full-rank equivalence separately.
    common={}
    for s in reference['systems']:
        key=s['system_seed'];a={k:s['hashes'][k] for k in ('A','Q','R','K0')}
        if key in common:assert common[key]==a
        else:common[key]=a
    grouped=defaultdict(list)
    for row in endpoints:grouped[row['r'],row['schedule_id'],row['method']].append(row)
    aggregate=[]
    for (rank,name,method),rows in sorted(grouped.items()):
        complete=len(rows)==len(config['system_seeds'])
        all_stable=complete and all(row['stable'] for row in rows)
        gaps=[row['gap'] for row in rows if row['stable']]
        aggregate.append(dict(r=rank,schedule_id=name,final_batch=rows[0]['final_batch'],
            minimum_batch=rows[0]['minimum_batch'],method=method,completed_systems=len(rows),
            complete_group=complete,stable_systems=len(gaps),planned_transitions=rows[0]['planned_transitions'],
            gap_mean=float(np.mean(gaps)) if all_stable else None,
            gap_min=min(gaps) if all_stable else None,gap_max=max(gaps) if all_stable else None,
            successes={str(eps):sum(row['stable'] and row['gap'] is not None and row['gap']<=eps for row in rows)
                       for eps in config['tolerances']}))
    minima=[];individual=[];comparisons=[]
    all_budgets=[sum(config['burn']+(n+1)*config['horizon'] for n in schedule)
                 for schedule in config['schedules'].values()]
    for rank in config['ranks']:
        for method in config['methods']:
            candidates=sorted((row for row in aggregate if row['r']==rank and row['method']==method),
                              key=lambda row:row['planned_transitions'])
            grid_complete=len(candidates)==len(config['schedules']) and all(row['complete_group'] for row in candidates)
            for eps in config['tolerances']:
                good=[row for row in candidates if row['complete_group']
                      and row['successes'][str(eps)]==len(config['system_seeds'])]
                first=good[0] if good else None
                upper=first['planned_transitions'] if first else None
                lower=max((row['planned_transitions'] for row in candidates
                           if row['complete_group'] and (upper is None or row['planned_transitions']<upper)),default=0)
                minima.append(dict(r=rank,method=method,epsilon=eps,inverse_epsilon=1./eps,
                    minimum_budget=upper,lower_tested_budget=lower,grid_complete=grid_complete,
                    attaining_schedule_ids=[row['schedule_id'] for row in good if row['planned_transitions']==upper],
                    left_censored=upper==min(all_budgets) if upper is not None else False,
                    right_censored=upper is None and grid_complete,
                    nonmonotone_above_first=bool(first and any(row['complete_group']
                        and row['planned_transitions']>upper and row['successes'][str(eps)]<len(config['system_seeds'])
                        for row in candidates)),
                    rule='all four independent systems pass at fixed final stage; posthoc budget-grid diagnostic'))
                for seed in config['system_seeds']:
                    tested=sorted((row for row in endpoints if row['r']==rank and row['method']==method
                                   and row['system_seed']==seed),key=lambda row:row['planned_transitions'])
                    successful=[row for row in tested if row['stable'] and row['gap'] is not None and row['gap']<=eps]
                    budget=successful[0]['planned_transitions'] if successful else None
                    individual.append(dict(r=rank,method=method,system_seed=seed,epsilon=eps,minimum_budget=budget,
                        left_censored=budget==min(all_budgets) if budget is not None else False,
                        right_censored=budget is None and len(tested)==len(config['schedules'])))
    lookup={(row['r'],row['method'],row['epsilon']):row for row in minima}
    for rank in config['ranks']:
        for eps in config['tolerances']:
            raw=lookup[rank,'raw',eps];low=lookup[rank,'truncated',eps]
            a,b=raw['minimum_budget'],low['minimum_budget']
            comparisons.append(dict(r=rank,epsilon=eps,raw_budget=a,truncated_budget=b,
                grid_ratio=a/b if a and b else None,raw_left_censored=raw['left_censored'],
                truncated_left_censored=low['left_censored'],raw_right_censored=raw['right_censored'],
                truncated_right_censored=low['right_censored']))
    fits=[]
    if not missing:
        for method in config['methods']:
            for rank in config['ranks']:
                fits.append(fit([row for row in minima if row['method']==method and row['r']==rank],
                    'inverse_epsilon','minimum_budget',dict(axis='inverse_precision',method=method,r=rank)))
            for eps in config['tolerances']:
                fits.append(fit([row for row in minima if row['method']==method and row['epsilon']==eps
                                 and row['r']<=config['rank_fit_max']],
                    'r','minimum_budget',dict(axis='rank',method=method,epsilon=eps)))
    for name,rows in [('endpoints_per_run',endpoints),('records',records),('aggregate',aggregate),
                      ('minimum_budget_grid',minima),('individual_grid',individual),
                      ('raw_vs_truncated',comparisons),('descriptive_fits',fits)]:
        csv_write(out/f'{name}.csv',rows)
    status='partial' if missing else 'complete'
    summary=dict(status=status,configurations=len(config['tasks']),complete_tasks=len(endpoints)//2,
        missing_tasks=missing,stable_methods=sum(row['stable'] for row in endpoints),sampled_methods=len(endpoints),
        ranks=config['ranks'],tolerances=config['tolerances'],stages=config['stages'],horizon=config['horizon'],
        schedule_profiles=config['profiles'],
        aggregate=aggregate,minimum_budgets=minima,comparisons=comparisons,descriptive_fits=fits,
        exact_reference_endpoints=[row for row in reference['records'] if row['stage']==config['stages']],
        manifest_sha256=manifest_hash,
        caveats=['Predetermined growing schedule, fixed output stage; no true-cost learner stopping or grid tuning.',
            'Four independent systems, one collector trajectory each per arm; success counts are descriptive.',
            'Missing results are incomplete, not failures; complete unstable runs are retained as failures.',
            'Measured minima are grid upper endpoints, not optimal sample complexities; censoring is explicit.',
            'A,Q,R,K0 and nonzero B singular values fixed across rank; Jstar and state/control difficulty still change.',
            'Fixed horizon/actor stage count cannot establish an asymptotic epsilon exponent.',
            'Fits exclude censored points, use ranks <=16 for rank slopes, and are descriptive only.'])
    atomic_json(out/'summary.json',summary)
    atomic_json(out/'numerical_audit.json',dict(status='PASS',coverage=status,manifest_sha256=manifest_hash,
        tests=['source/config provenance','all present stages and actual sample counts',
               'same budget for both methods','common dense matrices across rank','verified reference margin'],
        complete_tasks=len(endpoints)//2,missing_tasks=missing))
    plots(config,aggregate,minima,out)
    print(json.dumps(dict(status=status,complete_tasks=len(endpoints)//2,missing_tasks=missing)),flush=True)


def plots(config,aggregate,minima,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'raw':'#777777','truncated':'#12699c'}
    fig,axes=plt.subplots(1,3,figsize=(13,4.5),sharey=True)
    for ax,eps in zip(axes,(1.,.5,.25)):
        for method in config['methods']:
            rows=sorted((row for row in minima if row['method']==method and row['epsilon']==eps),key=lambda r:r['r'])
            good=[row for row in rows if row['minimum_budget'] is not None]
            ax.plot([row['r'] for row in good],[row['minimum_budget']/1e6 for row in good],
                    'o-',color=colors[method],label=method)
            for row in rows:
                if row['left_censored']:
                    ax.plot(row['r'],row['minimum_budget']/1e6,'v',color=colors[method],markersize=9)
                elif row['right_censored']:
                    ax.plot(row['r'],row['lower_tested_budget']/1e6,'^',color=colors[method],markersize=9)
        ax.set_xscale('log',base=2);ax.set_yscale('log');ax.set_xticks(config['ranks'],labels=config['ranks'])
        ax.set_title(f'Final gap <= {eps:g}');ax.set_xlabel('Rank of B');ax.grid(alpha=.2)
    axes[0].set_ylabel('Grid minimum transitions (millions)');axes[-1].legend()
    fig.suptitle('Equal precision: raw versus truncated NPG, n=m=50\nAll 4 systems must pass; v lowest tier already passes, ^ above tested maximum')
    fig.tight_layout(rect=(0,0,1,.86));save(fig,out,'budget_vs_rank',plt)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),sharey=True)
    for ax,method in zip(axes,config['methods']):
        for rank in config['ranks']:
            good=sorted((row for row in minima if row['method']==method and row['r']==rank
                         and row['minimum_budget'] is not None),key=lambda r:r['inverse_epsilon'])
            ax.loglog([row['inverse_epsilon'] for row in good],[row['minimum_budget']/1e6 for row in good],
                      'o-',label=f'r={rank}')
        ax.set_title(method);ax.set_xlabel('1 / target absolute gap');ax.grid(alpha=.2);ax.legend(fontsize=8,ncol=2)
    axes[0].set_ylabel('Grid minimum transitions (millions)')
    fig.suptitle('Total sample budget versus precision\nMeasured grid upper endpoints; see CSV for censoring and missing groups')
    fig.tight_layout(rect=(0,0,1,.87));save(fig,out,'budget_vs_precision',plt)
    fig,axes=plt.subplots(2,4,figsize=(14,7),sharex=True,sharey=True)
    for ax,rank in zip(axes.flat,config['ranks']):
        for method in config['methods']:
            for minimum in config['minimum_batches']:
                good=sorted((row for row in aggregate if row['r']==rank and row['method']==method
                             and row['minimum_batch']==minimum and row['gap_mean'] is not None),
                            key=lambda r:r['planned_transitions'])
                xs=[row['planned_transitions']/1e6 for row in good]
                style='o--' if minimum==min(config['minimum_batches']) else 's-'
                ax.loglog(xs,[row['gap_mean'] for row in good],style,color=colors[method],
                          label=f'{method}; early N={minimum:,}')
                if good:ax.fill_between(xs,[row['gap_min'] for row in good],[row['gap_max'] for row in good],color=colors[method],alpha=.1)
        ax.set_title(f'r={rank}');ax.grid(alpha=.2)
    axes.flat[-1].axis('off');axes.flat[0].legend(fontsize=7)
    fig.supxlabel('Total primitive transitions (millions)');fig.supylabel('Final absolute cost gap')
    fig.suptitle('Fixed 256-update output: matched total budgets\nMean and range of 4 independent systems; failed/incomplete groups not averaged')
    fig.tight_layout(rect=(.025,.025,1,.88));save(fig,out,'endpoint_budget_sweep',plt)


def save(fig,out,name,plt):
    for ext in ('png','pdf'):fig.savefig(out/f'{name}.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser();p.add_argument('--manifest',required=True)
    p.add_argument('--output',required=True);p.add_argument('--partial',action='store_true');a=p.parse_args()
    main(a.manifest,a.output,a.partial)
