"""Measured precision thresholds and uncertainty over independent systems, on Grace."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dense_scaling import require_compute, atomic_json

COLORS = {'raw':'#b43b39', 'truncated':'#1769aa'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csv_write(path, rows):
    if not rows:
        return
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def finite(value):
    return float(value) if np.isfinite(value) else None


def short(value):
    for scale, suffix in ((1e9,'B'), (1e6,'M'), (1e3,'k')):
        if value >= scale:
            return f'{value/scale:.3g}{suffix}'
    return str(int(value))


def wilson(success, total):
    z = 1.959963984540054
    p, den = success/total, 1+z*z/total
    center = (p+z*z/(2*total))/den
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return max(0.,center-half), min(1.,center+half)


def fit(rows):
    interior = [r for r in rows if r['status']=='attained' and r['r']/r['n']<=.2]
    result = dict(interior_cells=len(interior), total_cells=len(rows), censored_excluded=True)
    if len({r['n'] for r in interior})>=3 and len({r['r'] for r in interior})>=3:
        x = np.array([[1.,np.log(r['n']),np.log(r['r'])] for r in interior])
        if np.linalg.matrix_rank(x)==3:
            coef = np.linalg.lstsq(x,np.log([r['budget'] for r in interior]),rcond=None)[0]
            result.update(C=float(np.exp(coef[0])), alpha_n=float(coef[1]), beta_r=float(coef[2]))
    return result


def main(manifest, root, algorithms=None, allow_partial=False):
    manifest, root = Path(manifest), Path(root)
    cfg = json.loads(manifest.read_text())
    release = manifest.parent.parent
    algorithms = algorithms or ['CE','LSPI','NPG']
    out = root / ('report' if len(algorithms)==3 else 'report-'+algorithms[0].lower())
    out.mkdir(parents=True, exist_ok=True)
    assert json.loads((root/'verification.json').read_text())['status']=='PASS'
    assert json.loads((root/'resume-audit/resume_audit.json').read_text())['status']=='PASS'
    expected = dict(manifest_sha256=sha(manifest), source_sha256=sha(release/'scripts/rank_multiseed_run.py'),
        system_sha256=sha(release/'scripts/approx_tail_system.py'), lstd_sha256=sha(release/'scripts/full_lstd.py'),
        collector_sha256=sha(release/'scripts/npg_batched_collector.py'))
    expected['engine_sha256'] = json.loads((root/'verification.json').read_text())['engine_sha256']
    endpoints, missing, full_rank, used_profiles = [], [], [], []
    model_diagnostics = {}
    for profile, setting in cfg['profiles'].items():
        algorithm = setting['algorithm']
        if algorithm not in algorithms:
            continue
        paths = [root/profile/'raw'/f"task-{task['id']:03d}.json" for task in cfg['tasks']]
        if allow_partial and any(not path.exists() for path in paths):
            continue
        used_profiles.append(profile)
        for task, path in zip(cfg['tasks'],paths):
            if not path.exists():
                missing.append(dict(profile=profile, task_id=task['id']))
                continue
            payload = json.loads(path.read_text())
            assert payload['task']==task
            for key, value in expected.items():
                assert payload[key]==value, (path,key)
            diag = payload['diagnostics']
            if task['id'] in model_diagnostics:
                assert model_diagnostics[task['id']]==diag
            model_diagnostics[task['id']] = diag
            schedule = setting.get('schedule', [])
            planned = sum(cfg['burn']+count if algorithm=='LSPI' else cfg['burn']+(count+1)*cfg['horizon']
                          for count in schedule)
            arms = {}
            for method in COLORS:
                rows = [row for row in payload['records'] if row['method']==method]
                assert rows
                solver_ok = all(row.get('solver',{}).get('converged',True) for row in rows)
                for row in rows:
                    if algorithm=='CE':
                        assert row['transitions']==row['N']+512
                    else:
                        prefix = schedule[:row['stage']]
                        budget = sum(cfg['burn']+count if algorithm=='LSPI' else cfg['burn']+(count+1)*cfg['horizon']
                                     for count in prefix)
                        assert row['transitions']==budget
                    if row.get('solver',{}).get('converged'):
                        assert row['solver']['relative_residual']<=2*cfg['solver_rtol']
                arms[method] = rows
                for row in (rows if algorithm=='CE' else rows[-1:]):
                    complete = algorithm=='CE' or row['stage']==len(schedule)
                    endpoints.append(dict(algorithm=algorithm, profile=profile, method=method, cell=task['cell'],
                        n=task['n'], r=task['r'], seed=task['system_seed'], tail_mode=task['tail_mode'],
                        level=task['level'], samples=row['N']+512 if algorithm=='CE' else planned,
                        actual_samples=row['transitions'], gap=row.get('gap'), stable=row['stable'],
                        complete=complete, solver_ok=solver_ok, eligible=bool(complete and row['stable'] and solver_ok),
                        tail_energy=diag['tail_energy']))
            if task['r']==task['n']:
                assert len(arms['raw'])==len(arms['truncated'])
                differences=[]
                for raw, tr in zip(arms['raw'],arms['truncated']):
                    assert raw['stable']==tr['stable'] and raw['transitions']==tr['transitions']
                    if raw.get('gap') is not None and tr.get('gap') is not None:
                        delta=abs(raw['gap']-tr['gap'])
                        assert delta<=2e-6*max(1.,abs(raw['gap']),abs(tr['gap']))
                        differences.append(delta)
                full_rank.append(dict(profile=profile, task_id=task['id'], max_gap_difference=max(differences,default=0.)))
    atomic_json(out/'coverage.json',dict(missing=missing,used_profiles=used_profiles,
        planned_profiles=[p for p,s in cfg['profiles'].items() if s['algorithm'] in algorithms],
        algorithms=algorithms, partial=allow_partial, endpoints=len(endpoints)))
    assert not missing, 'Missing outputs cannot be treated as observations'
    assert endpoints and set(algorithms)=={e['algorithm'] for e in endpoints}
    for task in cfg['tasks']:
        assert task['id'] in model_diagnostics
    reference_completion=[]
    if len(algorithms)==3 and not allow_partial:
        for task in cfg['tasks']:
            ref=json.loads((root/'reference'/f"task-{task['id']:03d}.json").read_text())
            assert ref['task']==task and ref['manifest_sha256']==sha(manifest)
            assert ref['source_sha256']==sha(release/'scripts/approx_tail_run.py')
            for key in ('system_sha256','lstd_sha256','collector_sha256','engine_sha256'):
                assert ref[key]==expected[key]
            assert ref['diagnostics']==model_diagnostics[task['id']]
            for record in ref['completion']:
                reference_completion.append(dict(cell=task['cell'],seed=task['system_seed'],**record))
    shared = {}
    for task in cfg['tasks']:
        hashes = {k:v for k,v in model_diagnostics[task['id']]['matrix_sha256'].items() if k!='B'}
        key = task['n'],task['system_seed']
        if key in shared:
            assert shared[key]==hashes
        shared[key]=hashes
    seeds = cfg['system_seeds']
    rng = np.random.default_rng(202610091)
    resamples = rng.integers(0,len(seeds),size=(cfg['bootstrap_replicates'],len(seeds)))
    grouped = {}
    for e in endpoints:
        grouped.setdefault((e['algorithm'],e['method'],e['cell']),[]).append(e)
    per_seed, thresholds, probabilities, budget_rows, boot_values = [], [], [], [], {}
    for (algorithm,method,cell), rows in sorted(grouped.items()):
        budgets = sorted({e['samples'] for e in rows})
        lookup = {(e['seed'],e['samples']):e for e in rows}
        assert len(lookup)==len(rows)==len(seeds)*len(budgets)
        for seed in seeds:
            assert all((seed,b) in lookup for b in budgets)
        common = {k:rows[0][k] for k in ('n','r','tail_mode','level')}
        for budget in budgets:
            batch = [lookup[(seed,budget)] for seed in seeds]
            gaps = np.array([e['gap'] if e['eligible'] else np.inf for e in batch])
            quantiles = np.quantile(gaps,[.25,.5,.75],method='inverted_cdf')
            budget_rows.append(dict(algorithm=algorithm,method=method,cell=cell,**common,samples=budget,
                eligible_systems=sum(e['eligible'] for e in batch), total_systems=len(seeds),
                gap_q25=finite(quantiles[0]),gap_median=finite(quantiles[1]),gap_q75=finite(quantiles[2]),
                failed_as_infinite=True))
        for epsilon in cfg['tolerances']:
            success = np.array([[lookup[(seed,b)]['eligible'] and lookup[(seed,b)]['gap']<=epsilon
                                 for b in budgets] for seed in seeds], dtype=bool)
            sustained = np.logical_and.accumulate(success[:,::-1],axis=1)[:,::-1]
            values=[]
            for j,seed in enumerate(seeds):
                idx = next((i for i in range(len(budgets)) if sustained[j,i]),None)
                value = np.inf if idx is None else budgets[idx]
                values.append(value)
                per_seed.append(dict(algorithm=algorithm,method=method,cell=cell,**common,seed=seed,epsilon=epsilon,
                    budget=finite(value), status='right_censored' if idx is None else 'left_censored' if idx==0 else 'attained',
                    lower_budget=budgets[-1] if idx is None else 0 if idx==0 else budgets[idx-1]))
            for i,budget in enumerate(budgets):
                good = int(success[:,i].sum())
                lo,hi = wilson(good,len(seeds))
                probabilities.append(dict(algorithm=algorithm,method=method,cell=cell,**common,epsilon=epsilon,
                    samples=budget,successes=good,systems=len(seeds),success_fraction=good/len(seeds),
                    wilson95_lower=lo,wilson95_upper=hi,sustained_successes=int(sustained[:,i].sum())))
            values=np.array(values)
            for fraction in cfg['success_fractions']:
                required=math.ceil(fraction*len(seeds)-1e-12)
                value=np.sort(values)[required-1]
                idx=None if not np.isfinite(value) else budgets.index(int(value))
                sampled=np.sort(values[resamples],axis=1)[:,required-1]
                interval=np.quantile(sampled,[.025,.975],method='inverted_cdf')
                record=dict(algorithm=algorithm,method=method,cell=cell,**common,epsilon=epsilon,
                    success_fraction=fraction,required_systems=required,systems=len(seeds),budget=finite(value),
                    status='right_censored' if idx is None else 'left_censored' if idx==0 else 'attained',
                    lower_budget=budgets[-1] if idx is None else 0 if idx==0 else budgets[idx-1],
                    largest_tested_budget=budgets[-1], bootstrap95_lower=finite(interval[0]),
                    bootstrap95_upper=finite(interval[1]),bootstrap_upper_censored=not np.isfinite(interval[1]))
                thresholds.append(record)
                if fraction==cfg['primary_success_fraction']:
                    boot_values[(algorithm,method,cell,epsilon)]=(sampled,budgets)
    fits=[]
    for algorithm in algorithms:
        for method in COLORS:
            for epsilon in cfg['primary_tolerances']:
                rows=[t for t in thresholds if t['algorithm']==algorithm and t['method']==method and
                      t['epsilon']==epsilon and t['tail_mode']=='exact' and t['success_fraction']==cfg['primary_success_fraction']]
                result=fit(rows)
                boots=[]
                for rep in range(cfg['bootstrap_replicates']):
                    draw=[]
                    for t in rows:
                        sampled,budgets=boot_values[(algorithm,method,t['cell'],epsilon)]
                        value=sampled[rep]
                        draw.append(dict(t,budget=finite(value),status='right_censored' if not np.isfinite(value)
                                         else 'left_censored' if value==budgets[0] else 'attained'))
                    estimate=fit(draw)
                    if 'alpha_n' in estimate:
                        boots.append([estimate['alpha_n'],estimate['beta_r']])
                result.update(algorithm=algorithm,method=method,epsilon=epsilon,bootstrap_fittable=len(boots),
                              bootstrap_replicates=cfg['bootstrap_replicates'])
                if boots:
                    interval=np.quantile(boots,[.025,.975],axis=0)
                    result.update(alpha_n_bootstrap95=interval[:,0].tolist(),beta_r_bootstrap95=interval[:,1].tolist())
                fits.append(result)
    for algorithm in algorithms:
        for mode,level,label in (('exact',0.,'exact'),('frobenius',cfg['tail_frobenius'],'small-tail')):
            fig,axes=plt.subplots(3,2,figsize=(12.8,12.6),squeeze=False)
            for row,epsilon in enumerate(cfg['primary_tolerances']):
                for col,n in enumerate((50,100)):
                    ax=axes[row,col]
                    selected=[t for t in thresholds if t['algorithm']==algorithm and t['n']==n and
                        t['r'] in cfg['ranks'] and t['tail_mode']==mode and t['level']==level and
                        t['epsilon']==epsilon and t['success_fraction']==cfg['primary_success_fraction']]
                    assert len(selected)==2*len(cfg['ranks'])
                    limits=[]
                    for method,color in COLORS.items():
                        series=sorted([t for t in selected if t['method']==method],key=lambda t:t['r'])
                        yy=[t['budget'] if t['budget'] is not None else np.nan for t in series]
                        ax.plot([t['r'] for t in series],yy,color=color,label=method,linewidth=2)
                        for t in series:
                            val=t['budget'] or t['largest_tested_budget']
                            limits.append(val)
                            marker='^' if t['status']=='right_censored' else 'v' if t['status']=='left_censored' else 'o'
                            xx=t['r']*(.98 if method=='raw' else 1.02)
                            ax.scatter(xx,val,color=color,marker=marker,s=40)
                            text=('>' if marker=='^' else '<=' if marker=='v' else '')+short(val)
                            ax.annotate(text,(xx,val),xytext=(0,10 if method=='raw' else -19),
                                textcoords='offset points',ha='center',fontsize=8,color=color)
                            if t['budget'] is not None and t['bootstrap95_lower'] is not None:
                                upper=t['bootstrap95_upper'] or t['largest_tested_budget']
                                ax.vlines(xx,t['bootstrap95_lower'],upper,color=color,alpha=.3,linewidth=4)
                        interior=[t for t in series if t['status']=='attained']
                        if method=='truncated' and interior:
                            anchor=interior[len(interior)//2]
                            xx=np.array(cfg['ranks'])
                            ax.plot(xx,anchor['budget']*xx/anchor['r'],color=color,linestyle=':',alpha=.5,label='linear r guide')
                    ax.set(xscale='log',yscale='log',xlabel='Rank r',ylabel='Primitive transitions M',
                           title=f'{algorithm}, n={n}, cost gap <= {epsilon:g}')
                    ax.set_xticks(cfg['ranks'],labels=cfg['ranks'])
                    ax.set_xlim(.8,20)
                    ax.set_ylim(min(limits)*.32,max(limits)*3.2)
                    ax.grid(alpha=.2)
                    ax.legend(fontsize=8)
            title='Exact-rank B' if mode=='exact' else f'Small tail: ||B-B_r||_F = {level:g} (fixed across n and r)'
            fig.suptitle(f'{title}: samples to the SAME precision across rank',fontsize=15)
            fig.subplots_adjust(top=.92,bottom=.11,hspace=.48,wspace=.28)
            fig.text(.5,.025,f'{len(seeds)} independent systems/cell; empirical 8/10 sustained success threshold. '
                'Vertical bars: system-bootstrap 95% intervals.\n'
                'Triangles: right/left censored; an unbounded bootstrap upper limit is clipped to the largest budget.\n'
                'Failed runs count as failure; budgets are measured on a discrete grid. Dotted lines are proportional-r guides.',ha='center',fontsize=9)
            name=f'{algorithm.lower()}_{label}_samples_by_rank'
            fig.savefig(out/(name+'.png'),dpi=160)
            fig.savefig(out/(name+'.pdf'))
            plt.close(fig)
    # Fixed-rank dimension controls isolate the n dependence, with exact B.
    fig,axes=plt.subplots(len(algorithms),3,figsize=(13,3.8*len(algorithms)),squeeze=False)
    for row,algorithm in enumerate(algorithms):
        for col,epsilon in enumerate(cfg['primary_tolerances']):
            ax=axes[row,col]
            for method,color in COLORS.items():
                series=sorted([t for t in thresholds if t['algorithm']==algorithm and t['method']==method and
                    t['r']==4 and t['tail_mode']=='exact' and t['epsilon']==epsilon and
                    t['success_fraction']==cfg['primary_success_fraction']],key=lambda t:t['n'])
                ax.plot([t['n'] for t in series],[t['budget'] or np.nan for t in series],color=color,label=method)
                for t in series:
                    val=t['budget'] or t['largest_tested_budget']
                    marker='^' if t['status']=='right_censored' else 'v' if t['status']=='left_censored' else 'o'
                    ax.scatter(t['n'],val,color=color,marker=marker)
                    ax.annotate(('>' if marker=='^' else '<=' if marker=='v' else '')+short(val),(t['n'],val),
                        xytext=(0,8 if method=='raw' else -16),textcoords='offset points',ha='center',fontsize=8,color=color)
            ax.set(xscale='log',yscale='log',xlabel='State dimension n',ylabel='Primitive transitions M',
                   title=f'{algorithm}, r=4, gap <= {epsilon:g}')
            ax.set_xticks([25,50,75,100],labels=[25,50,75,100])
            ax.set_xlim(20,125)
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
    fig.suptitle('Fixed rank: measured samples to the same precision (exact B)',fontsize=14)
    fig.tight_layout(rect=(0,0,1,.95))
    fig.savefig(out/'fixed_rank_dimension.png',dpi=160)
    fig.savefig(out/'fixed_rank_dimension.pdf')
    plt.close(fig)
    csv_write(out/'endpoints.csv',endpoints)
    csv_write(out/'per_seed_samples_to_precision.csv',per_seed)
    csv_write(out/'samples_to_precision.csv',thresholds)
    csv_write(out/'success_by_budget.csv',probabilities)
    csv_write(out/'same_budget.csv',budget_rows)
    atomic_json(out/'numerical_audit.json',dict(status='PASS',coverage='complete_profiles' if allow_partial else 'complete',
        source_sha256=expected,shared_matrices_bitwise_identical=True,full_rank_equivalence=full_rank,
        paired_systems=len(cfg['tasks']),used_profiles=used_profiles,missing=missing,
        oracle_stability_termination_disclosed=True))
    atomic_json(out/'summary.json',dict(status='snapshot_complete' if allow_partial else 'complete',
        algorithms=algorithms,used_profiles=used_profiles,system_seeds=seeds,systems_per_cell=len(seeds),
        complete_paired_configurations=len(cfg['tasks'])*len(used_profiles),
        primary_tolerances=cfg['primary_tolerances'],primary_success_fraction=cfg['primary_success_fraction'],
        thresholds=thresholds,fits=fits,bootstrap_replicates=cfg['bootstrap_replicates'],
        population_reference_completion=reference_completion,
        caveats=['Empirical success over 10 systems is not a population guarantee.',
                 'Finite-range slopes exclude censored thresholds and are not asymptotic proofs.',
                 'True-model stability is used only to terminate failed LSPI/NPG trajectories.',
                 'Algorithms retain different exploration protocols; compare paired truncation arms within each algorithm.',
                 'Bootstrap resamples system seeds jointly across rank/dimension; censored systems are never discarded.'],
        slurm_job_id=os.environ['SLURM_JOB_ID'],report_sha256=sha(__file__),manifest_sha256=sha(manifest)))
    print(json.dumps(dict(status='PASS',algorithms=algorithms,profiles=len(used_profiles),thresholds=len(thresholds))),flush=True)


if __name__=='__main__':
    require_compute()
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--algorithm',choices=['CE','LSPI','NPG'])
    parser.add_argument('--allow-partial',action='store_true')
    args=parser.parse_args()
    main(args.manifest,args.output,None if args.algorithm is None else [args.algorithm],args.allow_partial)
