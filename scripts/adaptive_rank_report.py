"""Report ALL planned outcomes, including failures and unavailable tasks."""
import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path
import numpy as np


def write_csv(path, rows):
    keys = sorted(set().union(*(r.keys() for r in rows)))
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--reference', type=Path)
    args = p.parse_args()
    cfg = json.loads(args.manifest.read_text())
    report = args.output/'report'; report.mkdir(parents=True, exist_ok=True)
    rows, completed, identity = [], [], None
    for task in cfg['tasks']:
        path = args.output/'raw'/f"task-{task['id']:03d}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        assert payload['task']==task
        if identity is None: identity=payload['identity']
        assert payload['identity']==identity, 'Mixed scientific source/config identities'
        assert len(payload['records'])==len(cfg['algorithms'])*len(cfg['methods'])*(2*len(cfg['fixed_budgets'])+len(cfg['schedule'])+1)
        for record in payload['records']:
            if record.get('threshold') is not None:
                expected=sum(x>record['threshold'] for x in record['singular_values'])
                assert record['retained_rank']==expected
            if record['phase']=='learning' and record['stage']>0:
                schedule=cfg['schedule'][:record['stage']]
                expected=sum(cfg['burn']+(x+1)*cfg['horizon'] for x in schedule) if record['algorithm'] in ('DIRECT_PI','NPG') else sum(cfg['burn']+x for x in schedule)
                assert record['transitions']==expected
                assert record['actual_transitions']<=expected
        completed.append(task['id'])
        for record in payload['records']:
            rows.append(dict(task, **record))
    assert rows, 'No outputs'
    reference=[]
    if args.reference:
        ref=json.loads(args.reference.read_text())
        expected_identity=identity.get('components',{}).get('npg',{}).get('identity',identity)
        assert ref['identity']==expected_identity and ref['diagnostic_only']
        reference=ref['records']
    flat = [{k:v for k,v in row.items() if not isinstance(v,(dict,list))} for row in rows]
    write_csv(report/'all_records.csv', flat)
    endpoints, thresholds = [], []
    for algorithm in cfg['algorithms']:
        for spectrum in ('exact','gap','decay','flat'):
            tasks = [t for t in cfg['tasks'] if t['spectrum']==spectrum]
            for method in cfg['methods']:
                final = [r for r in rows if r['phase']=='learning' and r['algorithm']==algorithm
                    and r['spectrum']==spectrum and r['method']==method and r['stage']==len(cfg['schedule'])]
                gaps = [r['gap'] if r['stable'] and r.get('gap') is not None else np.inf for r in final]
                gaps += [np.inf]*(len(tasks)-len(final))
                median = float(np.median(gaps))
                ranks = [r['retained_rank'] for r in final if r.get('retained_rank') is not None]
                first_failures = []
                for task in tasks:
                    failure = next((r.get('failure','unknown') for r in rows if r['id']==task['id']
                        and r['phase']=='learning' and r['algorithm']==algorithm and r['method']==method
                        and r.get('failure') and r['failure']!='prior_failure'),None)
                    if failure: first_failures.append(failure)
                endpoints.append(dict(algorithm=algorithm,spectrum=spectrum,method=method,
                    planned=len(tasks),observed_tasks=len(final),stable=sum(r['stable'] for r in final),
                    median_gap=None if not np.isfinite(median) else median,
                    median_gap_infinite=not np.isfinite(median),
                    median_retained_rank=float(np.median(ranks)) if ranks else None,
                    failures={kind:first_failures.count(kind) for kind in sorted(set(first_failures))}))
                for task in tasks:
                    trajectory = sorted([r for r in rows if r['id']==task['id'] and r['phase']=='learning'
                        and r['algorithm']==algorithm and r['method']==method and r['stage']>0],key=lambda r:r['stage'])
                    for eps in cfg['targets']:
                        attained = next((r for i,r in enumerate(trajectory) if len(trajectory)==len(cfg['schedule'])
                            and all(x['stable'] and x['gap'] is not None and x['gap']<=eps for x in trajectory[i:])),None)
                        thresholds.append(dict(task_id=task['id'],system_seed=task['system_seed'],
                            trial_seed=task['trial_seed'],algorithm=algorithm,spectrum=spectrum,
                            method=method,epsilon=eps,transitions=attained['transitions'] if attained else None,
                            censored=attained is None))
    write_csv(report/'endpoints.csv', [{k:v for k,v in r.items() if k!='failures'} for r in endpoints])
    write_csv(report/'sustained_thresholds.csv', thresholds)
    fixed = []
    for algorithm in cfg['algorithms']:
        for spectrum in ('exact','gap','decay','flat'):
            for location in ('K0','Kstar'):
                for count in cfg['fixed_budgets']:
                    for method in cfg['methods']:
                        group=[r for r in rows if r['phase']=='fixed' and r['algorithm']==algorithm
                            and r['spectrum']==spectrum and r['location']==location and r['N']==count
                            and r['method']==method]
                        entry=dict(algorithm=algorithm,spectrum=spectrum,location=location,N=count,method=method,
                                   available=len(group),stable=sum(r['stable'] for r in group))
                        for metric in ('threshold','noise_proxy','retained_rank','estimation_error_fro2',
                                       'raw_redundant_noise_fro2','corrected_redundant_noise_fro2'):
                            values=[r[metric] for r in group if r.get(metric) is not None]
                            entry['median_'+metric]=float(np.median(values)) if values else None
                        fixed.append(entry)
    write_csv(report/'fixed_policy_summary.csv',fixed)
    actual_total=sum(r.get('actual_transitions',0) for r in rows if r['phase']=='learning'
                     and r['stage']==len(cfg['schedule']))
    fixed_total=sum(r['transitions'] for r in rows if r['phase']=='fixed' and r['method']=='dense')
    summary = dict(completed_tasks=len(completed),planned_tasks=len(cfg['tasks']),endpoints=endpoints,
        identity=identity,audit='PASS: record coverage, common identity, threshold ranks, primitive budgets',
        actual_learning_transitions=actual_total,actual_fixed_policy_transitions=fixed_total,
        algorithms=cfg['algorithms'],threshold_type=cfg['threshold'],
        limits=['Small controlled pilot, two systems and two trials.',
                'Empirical split disagreement is not a theoretical confidence radius.',
                f'The fixed {len(cfg["schedule"])}-update budget schedule does not identify sample-complexity exponents.',
                'A median marked infinite includes algorithm failures and unavailable tasks.'])
    if reference:
        summary['population_reference_path']=str(args.reference)
        summary['population_reference_endpoints']=[r for r in reference if r['stage']==len(cfg['schedule'])]
    (report/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = dict(zip(cfg['methods'], ('#555555','#167a39','#56b4e9','#0072b2','#d55e00')))
    def add_reference(ax, algorithm, spectrum):
        if algorithm!='NPG': return
        points=[]
        for stage in range(1,len(cfg['schedule'])+1):
            group=[r for r in reference if r['spectrum']==spectrum and r['stage']==stage
                and r['method']=='dense' and not r['finite_horizon']]
            if not group: continue
            values=[r['gap'] if r['stable'] else np.inf for r in group]
            median=float(np.median(values))
            if np.isfinite(median):
                budget=sum(cfg['burn']+(x+1)*cfg['horizon'] for x in cfg['schedule'][:stage])
                points.append((budget,max(median,1e-12)))
        if points: ax.plot(*zip(*points),color='black',ls='--',lw=1,label='exact critic (diagnostic)')
    spectra = ('exact','gap','decay','flat')
    fig, axes = plt.subplots(4,len(cfg['algorithms']),figsize=(15,14),squeeze=False)
    for i,spectrum in enumerate(spectra):
        for j,algorithm in enumerate(cfg['algorithms']):
            ax=axes[i,j]
            for method in cfg['methods']:
                subset=[r for r in rows if r['phase']=='learning' and r['algorithm']==algorithm
                        and r['spectrum']==spectrum and r['method']==method and r['stage']>0]
                points=[]
                for stage in range(1,len(cfg['schedule'])+1):
                    group=[r for r in subset if r['stage']==stage]
                    if not group: continue
                    values=[r['gap'] if r['stable'] and r['gap'] is not None else np.inf for r in group]
                    values += [np.inf]*(4-len(group))
                    values.sort()
                    # Arithmetic even-sample median including infinity (no inf interpolation).
                    y=(values[1]+values[2])/2
                    points.append((group[0]['transitions'],y,sum(r['stable'] for r in group)))
                finite=[(x,max(y,1e-12)) for x,y,_ in points if np.isfinite(y)]
                if finite:
                    ax.plot(*zip(*finite),label=method,color=colors[method],marker='.',lw=1.3)
                # Counts at fixed panel-relative height also show minority failures.
                failed=[(x,success) for x,_,success in points if success<4]
                if failed:
                    ax.plot([x for x,_ in failed],[.98-.045*cfg['methods'].index(method)]*len(failed),
                        'x',color=colors[method],transform=ax.get_xaxis_transform(),clip_on=False)
            add_reference(ax,algorithm,spectrum)
            if not ax.lines or not any(line.get_transform()==ax.transData for line in ax.lines):
                ax.set_xlim(1,1e7); ax.set_ylim(1e-5,10)
                ax.text(.5,.5,'No finite median',ha='center',transform=ax.transAxes)
            ax.set_xscale('log');ax.set_yscale('log');ax.grid(alpha=.2)
            ax.set_title(f'{algorithm} / {spectrum}')
            ax.set_xlabel('Scheduled primitive transitions');ax.set_ylabel('Absolute gap (median incl. failures)')
    handles,labels=axes[0,-1].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',ncol=5)
    fig.suptitle('Unknown-rank full learning; x near panel top = at least one failed run',y=.97)
    fig.tight_layout(rect=(0,0,1,.94));fig.savefig(report/'learning.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,len(cfg['algorithms']),figsize=(15,4),squeeze=False)
    for j,algorithm in enumerate(cfg['algorithms']):
        ax=axes[0,j]
        for method in cfg['methods']:
            points=[]
            for stage in range(1,len(cfg['schedule'])+1):
                group=[r for r in rows if r['phase']=='learning' and r['algorithm']==algorithm
                    and r['spectrum']=='exact' and r['method']==method and r['stage']==stage]
                if not group: continue
                values=sorted([r['gap'] if r['stable'] else np.inf for r in group]+[np.inf]*(4-len(group)))
                median=(values[1]+values[2])/2
                if np.isfinite(median): points.append((group[0]['transitions'],max(median,1e-12)))
            if points:
                ax.plot(*zip(*points),color=colors[method],marker='.',label=method)
            else:
                ax.plot([],[],color=colors[method],label=method+' (no finite median)')
        add_reference(ax,algorithm,'exact')
        ax.set_xscale('log');ax.set_yscale('log');ax.grid(alpha=.2)
        ax.set_title(algorithm);ax.set_xlabel('Primitive transitions');ax.set_ylabel('Absolute gap')
        ax.legend(fontsize=7)
    fig.suptitle('Exact low rank: n=m=8, rank(B)=2; medians include failed runs')
    fig.tight_layout();fig.savefig(report/'exact_learning.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(2,len(cfg['algorithms']),figsize=(15,8),squeeze=False)
    for j,algorithm in enumerate(cfg['algorithms']):
        for i,metric in enumerate(('retained_rank','gap')):
            ax=axes[i,j]
            for method in cfg['methods']:
                values=[]
                for spectrum in spectra:
                    subset=[r for r in rows if r['phase']=='fixed' and r['location']=='K0'
                        and r['N']==max(cfg['fixed_budgets']) and r['algorithm']==algorithm
                        and r['spectrum']==spectrum and r['method']==method]
                    v=[r.get(metric) if metric!='gap' or r['stable'] else np.inf for r in subset]
                    v=[np.inf if x is None else x for x in v]+[np.inf]*(4-len(v))
                    v.sort();med=(v[1]+v[2])/2
                    values.append(med if np.isfinite(med) else np.nan)
                ax.plot(spectra,values,marker='o',label=method,color=colors[method])
            ax.set_title(f'{algorithm}: K0, N={max(cfg["fixed_budgets"])}')
            ax.set_ylabel('Retained rank' if metric=='retained_rank' else 'One-update absolute gap')
            ax.grid(alpha=.2)
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='upper center',ncol=5)
    fig.tight_layout(rect=(0,0,1,.94));fig.savefig(report/'fixed_policy.png',dpi=170);plt.close(fig)
    lines=['# Adaptive rank pilot results','',
        f'Completed {len(completed)}/{len(cfg["tasks"])} tasks. n=m=8, two systems x two trials, {len(cfg["schedule"])} updates.',
        '', 'Threshold: empirical split disagreement; primary multiplier=1. No numerical theoretical constants available.',
        '', '| Route | Spectrum | Method | Stable / planned | Final median absolute gap (failures included) | Final median retained rank |',
        '|---|---|---|---:|---:|---:|']
    for row in endpoints:
        gap='infinity' if row['median_gap_infinite'] else f"{row['median_gap']:.5g}"
        lines.append(f"| {row['algorithm']} | {row['spectrum']} | {row['method']} | {row['stable']}/{row['planned']} | {gap} | {row['median_retained_rank']} |")
    lines += ['', 'All preset threshold multipliers are shown. No winner is chosen by test cost.',
              'Rank on a joint PI block is not automatically equal to rank(B) in the approximate-rank cases.',
              'Charts show failure marks even when the median remains finite. Fixed-policy missing markers mean no finite median.',
              'This pilot establishes implementability and finite-budget behavior; it does not establish dimension scaling or a theoretical guarantee.']
    (report/'findings.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(completed=len(completed),planned=len(cfg['tasks']),report=str(report))))


if __name__=='__main__':
    main()
