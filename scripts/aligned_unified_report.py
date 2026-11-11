"""Merge saved historical outputs with the missing-cell run; plot fixed outputs."""
import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def number(value):
    return None if value in (None, '', 'None') else float(value)


def yes(value):
    return value is True or str(value).lower()=='true'


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--historical', type=Path, required=True)
    args=parser.parse_args()
    assert os.environ.get('SLURM_JOB_ID'), 'Run numerical reporting on a compute node'
    cfg=read(args.release/'manifest.json')
    dest=args.output/'unified_report';dest.mkdir(exist_ok=True)
    cohorts={'CE_prefix','NPG_constant80','NPG_growing80','PI_final8systems','NPG_adaptive100_rank80'}
    rows=[]
    with args.historical.open(encoding='utf-8-sig') as stream:
        for r in csv.DictReader(stream):
            if r['cohort'] not in cohorts or number(r['tail'])!=0.:
                continue
            rows.append(dict(cohort=r['cohort'], n=int(r['n']), r=int(r['r']), method=r['method'],
                             seed=int(r['system_seed']), budget=int(r['planned_budget']),
                             actual_budget=int(r['actual_budget']), g=number(r['g']), gap=number(r['gap']),
                             complete=yes(r['complete']), stable=yes(r['stable']), success=yes(r['success']),
                             failure=r['failure'] or None, origin='historical_saved_output', source=r['source']))
    for task in cfg['tasks']:
        directory=args.output/'tasks'/f"task-{task['id']:03d}"
        pi=task['algorithm']=='Direct_Stein_PI'
        paths=list((directory/'core').glob('n*.json')) if pi else [directory/'result.json']
        for path in paths:
            if not path.exists():
                continue
            data=read(path);records=data.get('records',data.get('rows',[]))
            for method in sorted({r.get('method',data.get('meta',{}).get('method')) for r in records}):
                values=[r for r in records if r.get('method',data.get('meta',{}).get('method'))==method]
                chosen=values if task['algorithm']=='CE' else [values[-1]]
                for r in chosen:
                    g=r.get('normalized_gap',r.get('relative_gap'))
                    failure=r.get('failure')
                    if pi:
                        budget=8*(512+(task['blocks']+1)*16);complete=r['stage']==8 or bool(failure)
                    elif task['algorithm']=='NPG':
                        budget=sum(1024+(b+1)*16 for b in cfg['npg']['batch_schedule'])
                        complete=r['stage']==80 or bool(failure)
                    else:
                        budget=r['transitions'];complete=True
                    rows.append(dict(cohort='PI_final8systems' if pi else 'NPG_growing80' if task['algorithm']=='NPG' else 'CE_prefix',
                                     n=task['n'],r=task['r'],method={'raw':'dense','truncated':'known_rank'}.get(method,method),
                                     seed=task['system_seed'],budget=budget,actual_budget=r['transitions'],g=g,gap=r.get('gap'),
                                     complete=complete,stable=bool(r.get('stable')),
                                     success=bool(complete and r.get('stable') and g is not None and g<=.1),
                                     failure=failure,origin='new_Grace',source=str(path)))
    keys=[(r['cohort'],r['n'],r['r'],r['method'],r['seed'],r['budget']) for r in rows]
    assert len(keys)==len(set(keys)), 'Duplicate historical/new endpoint observations'
    grouped=defaultdict(list)
    for r in rows:
        grouped[r['cohort'],r['n'],r['r'],r['method'],r['budget']].append(r)
    summaries=[]
    for (cohort,n,rank,method,budget),values in sorted(grouped.items()):
        expected=8 if cohort=='PI_final8systems' else 2
        gs=[r['g'] for r in values if r['complete'] and r['stable'] and r['g'] is not None]
        summaries.append(dict(cohort=cohort,n=n,r=rank,method=method,budget=budget,
                              systems=len(values),expected_systems=expected,
                              successes=sum(r['success'] for r in values),
                              instabilities=sum(r['failure']=='controller_instability' for r in values),
                              failures=sum(not r['stable'] for r in values),
                              median_g_stable_only=statistics.median(gs) if gs else None,
                              all_succeed=len(values)==expected and all(r['success'] for r in values)))
    attainment=[]
    cells=defaultdict(list)
    for r in summaries:
        cells[r['cohort'],r['n'],r['r'],r['method']].append(r)
    for (cohort,n,rank,method),values in sorted(cells.items()):
        met=[r['budget'] for r in values if r['all_succeed']]
        attainment.append(dict(cohort=cohort,n=n,r=rank,method=method,
                               minimum_tested_budget=min(met) if met else None,
                               maximum_tested_budget=max(r['budget'] for r in values),
                               right_censored=not bool(met),
                               left_grid_censored=bool(met and min(met)==min(r['budget'] for r in values))))
    missing=[]
    for cohort,methods in [('CE_prefix',['dense','known_rank']),('NPG_growing80',['dense','known_rank']),
                           ('PI_final8systems',['dense','known_rank','adaptive'])]:
        for n in (50,100):
            for rank in cfg['ranks']:
                for method in methods:
                    values=[r for r in summaries if (r['cohort'],r['n'],r['r'],r['method'])==(cohort,n,rank,method)]
                    expected_budgets=3 if cohort=='PI_final8systems' else 7 if cohort=='CE_prefix' else 1
                    if len(values)!=expected_budgets or any(r['systems']!=r['expected_systems'] for r in values):
                        missing.append(dict(cohort=cohort,n=n,r=rank,method=method,present_budget_cells=len(values)))
    for name,values in [('endpoints',rows),('success_by_budget',summaries),('sample_to_accuracy',attainment)]:
        write_csv(dest/f'{name}.csv',values)
    # CE's seven fitted outputs and two postprocessors share one data stream.
    # PI/NPG arms collect different physical trajectories after policies diverge.
    physical={}
    for r in rows:
        arm='shared_model_data' if r['cohort']=='CE_prefix' else r['method']
        key=r['source'],arm
        previous=physical.get(key)
        if previous is None or r['actual_budget']>previous['executed_transitions']:
            physical[key]=dict(origin=r['origin'],cohort=r['cohort'],n=r['n'],r=r['r'],seed=r['seed'],
                               arm=arm,executed_transitions=r['actual_budget'],source=r['source'])
    ledger=list(physical.values())
    write_csv(dest/'transition_ledger.csv',ledger)
    executed_new=sum(r['executed_transitions'] for r in ledger if r['origin']=='new_Grace')
    assert executed_new<=cfg['planned_new_transitions']
    # Independently reevaluate the final NPG controllers from saved checkpoints.
    sys.path.insert(0,str(args.release));sys.path.insert(0,str(args.release/'scripts'))
    import numpy as np
    from dense_scaling import evaluate,system
    npg_checks=[]
    for task in cfg['tasks']:
        if task['algorithm']!='NPG':continue
        folder=args.output/'tasks'/f"task-{task['id']:03d}"
        if not (folder/'result.json').exists():continue
        data=read(folder/'result.json')
        s=system(dict(n=task['n'],m=task['n'],r=task['r'],system_seed=task['system_seed'],
                      family='coupled_unstable',stabilizer='isotropic',tail=0.,tail_shape='energy'))
        total=0
        for method in ('dense','known_rank'):
            last=next(r for r in reversed(data['records']) if r['method']==method)
            with np.load(folder/f'{method}.npz',allow_pickle=False) as saved:
                assert int(saved['total'])==last['transitions']
                q,_=evaluate(s,saved['K']);total+=int(saved['total'])
            if last.get('stable') is not None:
                assert q['stable']==last['stable']
                if q['stable']:np.testing.assert_allclose(q['gap'],last['gap'],rtol=1e-8,atol=1e-7)
            npg_checks.append(dict(task_id=task['id'],method=method,status='PASS'))
        assert total==data['actual_transitions']
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'dense':'#6b7280','known_rank':'#059669','adaptive':'#2563eb'}
    labels={'dense':'Dense','known_rank':'Known rank','adaptive':'Adaptive'}
    # Separate panels and legends preserve algorithm schedules and denominators.
    fig,axes=plt.subplots(3,2,figsize=(12,11),squeeze=False)
    panels=[('CE_prefix',8704,'CE | prefix 8,192 + burn 512\n2 systems per complete cell'),
            ('NPG_growing80',656491776,'NPG | update 80; 656.49M transitions\n2 systems per complete cell'),
            ('PI_final8systems',16781440,'Direct-Stein PI | update 8; 16.78M transitions\n8 systems per complete cell')]
    for i,(cohort,budget,title) in enumerate(panels):
        for j,n in enumerate((50,100)):
            ax=axes[i,j]
            panel_g=[.1]
            for method in ('dense','known_rank','adaptive'):
                vals=sorted([r for r in summaries if r['cohort']==cohort and r['n']==n and r['budget']==budget and r['method']==method],key=lambda r:r['r'])
                if not vals:
                    continue
                points=[r for r in vals if r['median_g_stable_only'] is not None]
                panel_g.extend(max(r['median_g_stable_only'],1e-7) for r in points)
                ax.plot([r['r'] for r in points],[max(r['median_g_stable_only'],1e-7) for r in points],
                        '-o',color=colors[method],label=labels[method],ms=4)
                for r in vals:
                    if r['failures']:
                        ax.plot(r['r'],.96,marker='x',color=colors[method],transform=ax.get_xaxis_transform())
            ax.axhline(.1,color='#dc2626',ls='--',lw=1)
            # Explicit positive domains keep completely missing/all-failed
            # panels renderable rather than crashing LogLocator in tight_layout.
            ax.set_xlim(.8,40)
            ax.set_ylim(max(1e-8,min(panel_g)*.5),max(1.,max(panel_g)*2))
            ax.set(xscale='log',yscale='log',xlabel='Rank',ylabel='Median g among stable outputs')
            ax.set_title(f'n={n} | {title}',fontsize=10)
            ax.set_xticks(cfg['ranks'],labels=list(map(str,cfg['ranks'])))
            ax.grid(alpha=.2)
            if ax.get_legend_handles_labels()[0]:ax.legend(fontsize=8)
    figure_state='PARTIAL SNAPSHOT' if missing else 'COMPLETE GRID'
    fig.suptitle(figure_state+' | Common target g <= 0.1; separate algorithm budgets\nCrosses at panel top indicate failures; full success denominators in CSV',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.94),h_pad=2.)
    for ext in ('png','svg'):
        fig.savefig(dest/f'fixed_output_rank_comparison.{ext}',dpi=160)
    plt.close(fig)
    # PI's complete three-budget sweep, including failed and missing cells.
    fig,axes=plt.subplots(2,6,figsize=(19,7),squeeze=False)
    for i,n in enumerate((50,100)):
        for j,rank in enumerate(cfg['ranks']):
            ax=axes[i,j]
            panel_g=[.1]
            for method in ('dense','known_rank','adaptive'):
                vals=sorted([r for r in summaries if r['cohort']=='PI_final8systems' and r['n']==n and r['r']==rank and r['method']==method],key=lambda r:r['budget'])
                panel_g.extend(max(r['median_g_stable_only'],1e-7) for r in vals if r['median_g_stable_only'] is not None)
                ax.plot([r['budget'] for r in vals],[max(r['median_g_stable_only'],1e-7) if r['median_g_stable_only'] is not None else math.nan for r in vals],
                        '-o',color=colors[method],label=labels[method],ms=3)
                for r in vals:
                    if r['failures']:
                        ax.plot(r['budget'],.96,'x',color=colors[method],transform=ax.get_xaxis_transform())
            ax.axhline(.1,color='#dc2626',ls='--',lw=1)
            ax.set_xlim(4198528*.8,67113088*1.2)
            ax.set_ylim(max(1e-8,min(panel_g)*.5),max(1.,max(panel_g)*2))
            ax.set(xscale='log',yscale='log',xlabel='Primitive transitions',title=f'n={n}, r={rank}')
            ax.grid(alpha=.2)
            if j==0:ax.set_ylabel('Median g among stable outputs')
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='lower center',ncol=3,frameon=False)
    fig.suptitle(figure_state+' | Direct-Stein PI: 8 systems per complete cell; fixed stage 8; eta=0.25\nDashed line: g=0.1; top crosses: failures; incomplete cells remain unfilled',fontsize=12)
    fig.tight_layout(rect=(0,.05,1,.91))
    for ext in ('png','svg'):
        fig.savefig(dest/f'PI_rank_dimension_budget_grid.{ext}',dpi=160)
    plt.close(fig)
    original=read(args.output/'report/summary.json')
    status='COMPLETE' if original['status']=='COMPLETE' and not missing else 'INCOMPLETE'
    summary=dict(status=status,primary_target=.1,endpoint_outputs=len(rows),missing_main_grid=missing,
                 planned_new_physical_transitions=cfg['planned_new_transitions'],
                 executed_new_physical_transitions=executed_new,npg_final_policy_checks=npg_checks,
                 historical_endpoints_sha256=hashlib.sha256(args.historical.read_bytes()).hexdigest(),
                 script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 slurm_job_id=os.environ['SLURM_JOB_ID'],
                 caveats=['PI 8 systems versus CE/NPG 2; no paired cross-algorithm claim.',
                          'NPG constant80 r32 budget sweep absent: r32 belongs to growing80 fixed-budget comparison.',
                          'Adaptive NPG n100 r1..16 is supplementary; CE adaptive and NPG n50 adaptive absent.',
                          'Stable-only median curves do not replace failure-inclusive success rates.',
                          'Generator A varies with rank; no universal linear-rank law is inferred.'])
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    text=['# Unified rank/dimension results','',f'Status: {status}. Primary criterion: g <= 0.1 at the fixed declared output.','',
          'PI: 8 systems; CE/NPG: 2 systems. Methods retain their frozen schedules and seeds.','',
          '![Fixed-output rank comparison](fixed_output_rank_comparison.png)','',
          '![PI budget/rank/dimension grid](PI_rank_dimension_budget_grid.png)','',
          '| Cohort | n | rank | method | Smallest tested budget: all systems attain |',
          '| --- | ---: | ---: | --- | ---: |']
    for r in attainment:
        if r['n'] not in (50,100):continue
        value=f"> {r['maximum_tested_budget']:,} (unattained)" if r['right_censored'] else f"{r['minimum_tested_budget']:,}"
        text.append(f"| {r['cohort']} | {r['n']} | {r['r']} | {r['method']} | {value} |")
    text+=['','Detailed failure-inclusive counts: success_by_budget.csv. Endpoint provenance: endpoints.csv.','']+summary['caveats']
    (dest/'findings.md').write_text('\n'.join(text)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    main()
