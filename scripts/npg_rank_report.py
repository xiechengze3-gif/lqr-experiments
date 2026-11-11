"""Thresholds and figures for end-to-end NPG; no uncensored-only success claims."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from dense_scaling import require_compute, atomic_json


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def thresholds(rows, eps, window, maximum):
    rows = sorted(rows, key=lambda row: row['stage'])
    good = [bool(row.get('stable') and row.get('gap') is not None and row['gap'] <= eps) for row in rows]
    first = next((i for i, yes in enumerate(good) if yes), None)
    confirmed = next((i for i in range(len(rows) - window + 1)
        if all(good[i:i + window]) and rows[i + window - 1]['stage'] == rows[i]['stage'] + window - 1), None)
    sustained = next((i for i in range(len(rows) - window + 1)
        if all(good[i:]) and rows[-1]['stage'] == maximum), None)
    return dict(epsilon=eps, first_hit=rows[first]['transitions'] if first is not None else None,
        confirmed_window=rows[confirmed + window - 1]['transitions'] if confirmed is not None else None,
        sustained=rows[sustained + window - 1]['transitions'] if sustained is not None else None,
        sustained_start_stage=rows[sustained]['stage'] if sustained is not None else None,
        left_censored=bool(sustained is not None and rows[sustained]['stage'] <= 1),
        right_censored=sustained is None, measured_maximum=rows[-1]['transitions'] if rows else 0,
        last_stage=rows[-1]['stage'] if rows else 0,
        failed=any(not row.get('stable', False) for row in rows))


def main(manifest, output):
    config = json.loads(Path(manifest).read_text())
    digest = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    root, out = Path(output), Path(output) / 'report'
    out.mkdir(parents=True, exist_ok=True)
    all_rows, threshold_rows, missing = [], [], []
    for task_id, task in enumerate(config['tasks']):
        path = root / 'raw' / f'task-{task_id:03d}.json'
        if not path.exists():
            missing.append(task_id)
            continue
        payload = json.loads(path.read_text())
        if payload['task'] != task or payload['manifest_sha256'] != digest:
            raise RuntimeError('Run provenance mismatch')
        all_rows.extend(dict(task_id=task_id, **task, **row) for row in payload['records'])
        for method in ('raw', 'truncated'):
            rows = [row for row in payload['records'] if row['method'] == method]
            assert len(rows) == config['stages'] + 1
            for eps in config['tolerances']:
                threshold_rows.append(dict(task_id=task_id, **task, method=method,
                    **thresholds(rows, eps, config['threshold_window'], config['stages'])))
    if missing:
        raise RuntimeError(f'Missing tasks: {missing}')
    reference = json.loads((root / 'reference.json').read_text())
    if reference['manifest_sha256'] != digest:
        raise RuntimeError('Reference provenance mismatch')
    write_csv(out / 'records.csv', all_rows)
    write_csv(out / 'thresholds_per_run.csv', threshold_rows)
    write_csv(out / 'exact_references.csv', reference['records'])
    groups = defaultdict(list)
    for row in threshold_rows:
        groups[row['n'], row['r'], row['method'], row['epsilon']].append(row)
    aggregate = []
    for (n, r, method, eps), rows in sorted(groups.items()):
        complete = all(row['sustained'] is not None for row in rows)
        budget = float(np.median([row['sustained'] for row in rows])) if complete else None
        aggregate.append(dict(n=n, r=r, method=method, epsilon=eps,
            systems=len(rows), attained=sum(not row['right_censored'] for row in rows),
            stable_systems=sum(not row['failed'] for row in rows),
            sustained_median=budget, sustained_min=min(row['sustained'] for row in rows) if complete else None,
            sustained_max=max(row['sustained'] for row in rows) if complete else None,
            normalized_rn2=budget / (r*n*n) if complete else None,
            any_left_censored=any(row['left_censored'] for row in rows),
            all_attained=complete, maximum_transitions=max(row['measured_maximum'] for row in rows)))
    write_csv(out / 'thresholds_aggregate.csv', aggregate)
    fits = []
    for method in ('raw', 'truncated'):
        for eps in config['tolerances']:
            eligible = [row for row in aggregate if row['method'] == method and row['epsilon'] == eps
                and row['r']/row['n'] <= config['fit_max_rank_fraction']]
            selected = [row for row in eligible if row['all_attained'] and not row['any_left_censored']]
            fit = dict(method=method, epsilon=eps, eligible_cells=len(eligible), fitted_cells=len(selected),
                cells=[[row['n'], row['r']] for row in selected],
                excluded_cells=[[row['n'], row['r']] for row in eligible if row not in selected],
                caveat='Exploratory conditional fit; two system clusters, common finite schedule, censored cells excluded. No population confidence interval.')
            if len(selected) >= 5:
                design = np.array([[1., np.log(row['n']), np.log(row['r'])] for row in selected])
                values = np.log([row['sustained_median'] for row in selected])
                if np.linalg.matrix_rank(design) == 3:
                    coef = np.linalg.lstsq(design, values, rcond=None)[0]
                    pred = design @ coef
                    fit.update(C=float(np.exp(coef[0])), alpha_n=float(coef[1]), beta_r=float(coef[2]),
                        log_R2=float(1 - np.sum((values-pred)**2)/max(np.sum((values-values.mean())**2), 1e-30)))
            fits.append(fit)
    ratios = []
    lookup = {(row['n'], row['r'], row['method'], row['epsilon']):row for row in aggregate}
    for n, r in sorted({(row['n'], row['r']) for row in aggregate}):
        for eps in config['tolerances']:
            a, b = lookup[n,r,'raw',eps], lookup[n,r,'truncated',eps]
            ratios.append(dict(n=n, r=r, epsilon=eps,
                raw_over_truncated=a['sustained_median']/b['sustained_median'] if a['all_attained'] and b['all_attained'] else None,
                raw_attained=a['attained'], truncated_attained=b['attained'], systems=a['systems']))
    write_csv(out / 'paired_ratios.csv', ratios)
    summary = dict(complete=True, configurations=len(config['tasks']), sampled_methods=['raw','truncated'],
        outer_stages=config['stages'], fits=fits, aggregate=aggregate,
        full_budget=aggregate[0]['maximum_transitions'],
        interpretation='Sustained means all remaining measured stages and at least four confirming observations. Costs/model truth only evaluate; all schedules independent of r,n,method. Fits are not proof of asymptotic upper bounds.')
    atomic_json(out / 'summary.json', summary)
    plots(config, all_rows, reference['records'], aggregate, out)
    print(json.dumps(dict(complete=True, configurations=len(config['tasks']), fits=fits)), flush=True)


def plots(config, records, references, aggregate, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.size':10, 'axes.titlesize':12, 'legend.fontsize':9})
    ranks = [1,2,4,8,16]
    colors = dict(zip(ranks, ['#2b6cb0','#15977d','#d8961f','#b34578','#684da4']))
    style = {'raw':'--', 'truncated':'-'}
    def save(fig, name):
        fig.savefig(out / f'{name}.png', dpi=180, bbox_inches='tight')
        fig.savefig(out / f'{name}.pdf', bbox_inches='tight')
        plt.close(fig)
    def format_axis(ax, xlabel, ylabel):
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        ax.grid(alpha=.22, which='major')
    fig, axes = plt.subplots(1,2,figsize=(13,4.7))
    for ax, n in zip(axes, (50,100)):
        for r in ranks:
            for method in ('raw','truncated'):
                grouped = defaultdict(list)
                for row in records:
                    if row['n']==n and row['r']==r and row['method']==method and row['stage']:
                        grouped[row['stage']].append(row)
                points = sorted(grouped.items())
                x, y, lo, hi = [],[],[],[]
                for _, rows in points:
                    x.append(rows[0]['transitions'])
                    good = all(row['stable'] for row in rows)
                    gaps = [row['gap'] for row in rows] if good else []
                    y.append(float(np.median(gaps)) if good else np.nan)
                    lo.append(min(gaps) if good else np.nan); hi.append(max(gaps) if good else np.nan)
                ax.loglog(x,y,style[method],color=colors[r],linewidth=1.7)
                if method=='truncated': ax.fill_between(x,lo,hi,color=colors[r],alpha=.08)
        ax.set_title(f'n=m={n}; absolute cost gap')
        format_axis(ax,'Cumulative primitive transitions','J(K) - J*')
        for eps in config['tolerances']: ax.axhline(eps,color='#aaaaaa',linewidth=.7,alpha=.6)
    handles = [Line2D([],[],color=colors[r],label=f'r={r}') for r in ranks]
    handles += [Line2D([],[],color='black',linestyle=style[m],label=m) for m in style]
    axes[1].legend(handles=handles,loc='upper right',ncol=2)
    fig.suptitle('NPG end-to-end rank sweep: same initial policy, step size and sample schedule\nMedian of two systems; shaded truncated range; no averaging across failed runs',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.88)); save(fig,'gap_vs_transitions')
    fig, axes = plt.subplots(2,3,figsize=(14,8),squeeze=False)
    for i,n in enumerate((50,100)):
        for j,eps in enumerate(config['tolerances']):
            ax=axes[i,j]
            for method,color in [('raw','#666666'),('truncated','#146fa1')]:
                selected=sorted([row for row in aggregate if row['n']==n and row['method']==method and row['epsilon']==eps],key=lambda x:x['r'])
                values=[row['sustained_median'] if row['all_attained'] else np.nan for row in selected]
                ax.loglog([row['r'] for row in selected],values,'o'+style[method],color=color,label=method)
                for row in selected:
                    if row['all_attained']:
                        ax.vlines(row['r'],row['sustained_min'],row['sustained_max'],color=color,alpha=.5)
                    else:
                        ax.scatter(row['r'],row['maximum_transitions'],marker='^',facecolors='none',edgecolors=color)
                        ax.annotate(f"{row['attained']}/2",(row['r'],row['maximum_transitions']),xytext=(0,5),textcoords='offset points',ha='center',color=color,fontsize=8)
            ax.set_title(f'n={n}, gap <= {eps:g}'); ax.set_xticks(ranks,labels=ranks)
            format_axis(ax,'Rank r','Sustained-attainment transitions')
    axes[0,0].legend(); fig.suptitle('Fixed absolute accuracy: sample budget versus rank\nOpen triangles: at least one run censored at full budget; labels show attained systems',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.90)); save(fig,'threshold_vs_rank')
    fig, axes = plt.subplots(2,3,figsize=(14,8))
    for i,method in enumerate(('raw','truncated')):
        for j,eps in enumerate(config['tolerances']):
            ax=axes[i,j]
            for n,color in [(50,'#d08028'),(100,'#216fa0')]:
                selected=sorted([row for row in aggregate if row['n']==n and row['method']==method and row['epsilon']==eps],key=lambda x:x['r'])
                ax.loglog([row['r'] for row in selected],[row['normalized_rn2'] if row['all_attained'] else np.nan for row in selected],'o-',color=color,label=f'n={n}')
                for row in selected:
                    if not row['all_attained']:
                        ax.scatter(row['r'],row['maximum_transitions']/(row['r']*n*n),marker='^',facecolors='none',edgecolors=color)
            ax.set_title(f'{method}, gap <= {eps:g}'); ax.set_xticks(ranks,labels=ranks)
            format_axis(ax,'Rank r','Transitions / (r n²)')
    axes[0,0].legend(); fig.suptitle('Does rn² explain end-to-end budgets?\nA collapse would be roughly flat in r with coincident n=50/100 curves; censoring retained',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.90)); save(fig,'rn2_collapse')
    fig,axes=plt.subplots(1,3,figsize=(14,4.7))
    for ax,eps in zip(axes,config['tolerances']):
        for method,color in [('raw','#666666'),('truncated','#146fa1')]:
            selected=sorted([row for row in aggregate if row['r']==4 and row['method']==method and row['epsilon']==eps],key=lambda row:row['n'])
            ax.loglog([row['n'] for row in selected],[row['sustained_median'] if row['all_attained'] else np.nan for row in selected],'o'+style[method],color=color,label=method)
            valid=[row for row in selected if row['all_attained']]
            if method=='truncated' and valid:
                anchor=valid[0]
                xs=np.array([row['n'] for row in selected])
                ax.loglog(xs,anchor['sustained_median']*(xs/anchor['n'])**2,':',color='#aaa',label='n² reference')
            for row in selected:
                if not row['all_attained']: ax.scatter(row['n'],row['maximum_transitions'],marker='^',facecolors='none',edgecolors=color)
        ax.set_title(f'r=4, gap <= {eps:g}'); ax.set_xticks([25,50,75,100],labels=[25,50,75,100])
        format_axis(ax,'Dimension n=m','Sustained-attainment transitions')
    axes[0].legend(); fig.suptitle('Fixed-rank dimension dependence (same absolute accuracy)',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.90)); save(fig,'threshold_vs_dimension')
    fig,axes=plt.subplots(1,2,figsize=(13,4.7))
    for ax,n in zip(axes,(50,100)):
        for r in ranks:
            grouped=defaultdict(list)
            for row in references:
                if row['n']==n and row['r']==r and not row['finite_horizon']: grouped[row['stage']].append(row['gap'])
            xs=sorted(grouped)
            ax.semilogy(xs,[np.median(grouped[x]) for x in xs],color=colors[r],label=f'r={r}')
        ax.set_title(f'n={n}: exact infinite-horizon critic')
        format_axis(ax,'Outer NPG updates','Absolute gap (zero-sample diagnostic)')
    axes[1].legend(); fig.suptitle('Optimization reference: unchanged NPG step size',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.92)); save(fig,'exact_outer_convergence')


if __name__=='__main__':
    require_compute()
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); main(args.manifest,args.output)
