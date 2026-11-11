"""Post-run budget/provenance audit and paired gain plots, on Grace only."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from dense_scaling import require_compute, atomic_json


def main(release, output):
    release, root = Path(release), Path(output)
    config = json.loads((release/'configs/npg_rank_scaling.json').read_text())
    digest = hashlib.sha256((release/'configs/npg_rank_scaling.json').read_bytes()).hexdigest()
    source_digest = hashlib.sha256((release/'scripts/npg_rank_scaling.py').read_bytes()).hexdigest()
    final, stable = [], []
    for tid, task in enumerate(config['tasks']):
        payload = json.loads((root/'raw'/f'task-{tid:03d}.json').read_text())
        assert payload['manifest_sha256'] == digest and payload['source_sha256'] == source_digest
        assert payload['task'] == task
        for method in ('raw','truncated'):
            rows = sorted([r for r in payload['records'] if r['method']==method],key=lambda r:r['stage'])
            assert [r['stage'] for r in rows] == list(range(config['stages']+1))
            total = 0
            for stage, row in enumerate(rows):
                if stage:
                    total += config['burn']+(config['batch_schedule'][stage-1]+1)*config['horizon']
                assert row['transitions']==total, (tid,method,stage)
            stable.append(rows[-1]['stable'])
            final.append(dict(n=task['n'],r=task['r'],system_seed=task['system_seed'],method=method,
                gap=rows[-1]['gap'],stable=rows[-1]['stable'],transitions=rows[-1]['transitions']))
    reference=json.loads((root/'reference.json').read_text())
    exact=[r for r in reference['records'] if r['stage']==config['stages'] and not r['finite_horizon']]
    assert all(r['stable'] for r in exact)
    summary=json.loads((root/'report/summary.json').read_text())
    assert summary['complete'] and summary['configurations']==len(config['tasks'])
    atomic_json(root/'report/numerical_audit.json',dict(verification='PASS',
        tests=['immutable manifest/source provenance','complete per-method stages','all burn-in/baseline transitions counted',
               'paired methods have identical budgets','exact references stable'],
        sampled_final_stable=sum(stable),sampled_methods=len(stable),
        exact_maximum_final_gap=max(r['gap'] for r in exact),full_budget=final[0]['transitions'],final_records=final))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes=plt.subplots(1,3,figsize=(14,4.8))
    paired=list(csv.DictReader((root/'report/paired_ratios.csv').open(newline='')))
    for ax,eps in zip(axes,config['tolerances']):
        for n,color in [(50,'#d08028'),(100,'#216fa0')]:
            points=sorted([r for r in paired if int(r['n'])==n and float(r['epsilon'])==eps],key=lambda r:int(r['r']))
            x=[int(r['r']) for r in points]
            y=[float(r['raw_over_truncated']) if r['raw_over_truncated'] else np.nan for r in points]
            ax.semilogx(x,y,'o-',color=color,label=f'n={n}')
        ax.axhline(1,color='#888',linestyle=':',linewidth=1)
        ax.set_title(f'Absolute gap <= {eps:g}')
        ax.set_xticks([1,2,4,8,16],labels=[1,2,4,8,16]); ax.grid(alpha=.2)
        ax.set_xlabel('Rank r');ax.set_ylabel('Raw budget / truncated budget')
    axes[0].legend(); fig.suptitle('Matched-accuracy budget gains\nRatios shown only when both methods attain in both systems; censoring is in threshold figures',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.88))
    fig.savefig(root/'report/paired_budget_gain.png',dpi=180,bbox_inches='tight')
    fig.savefig(root/'report/paired_budget_gain.pdf',bbox_inches='tight');plt.close(fig)
    all_rows=list(csv.DictReader((root/'report/records.csv').open(newline='')))
    fig,axes=plt.subplots(1,2,figsize=(12,4.6))
    for ax,n in zip(axes,(50,100)):
        for method,color,linestyle in [('raw','#777','--'),('truncated','#12699c','-')]:
            groups=defaultdict(list)
            for row in all_rows:
                if int(row['n'])==n and int(row['r'])==4 and row['method']==method:
                    groups[int(row['stage'])].append(row)
            xs=sorted(groups);ys=[]
            for x in xs:
                group=groups[x]
                ys.append(np.median([float(r['gap']) for r in group]) if all(r['stable']=='True' and r['gap'] for r in group) else np.nan)
            ax.semilogy(xs,ys,linestyle,color=color,label=method)
        groups=defaultdict(list)
        for row in reference['records']:
            if row['n']==n and row['r']==4 and not row['finite_horizon']:groups[row['stage']].append(row['gap'])
        xs=sorted(groups)
        ax.semilogy(xs,[np.median(groups[x]) for x in xs],color='#269b62',label='exact critic')
        ax.set_title(f'n={n}, r=4');ax.set_xlabel('Outer NPG updates');ax.set_ylabel('Absolute gap')
        ax.grid(alpha=.2);ax.legend()
    fig.suptitle('Optimization versus critic precision at the same step and iteration count\nExact critic is a zero-sample diagnostic; sampled arms follow the common growing-batch schedule',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.88))
    fig.savefig(root/'report/outer_convergence_comparison.png',dpi=180,bbox_inches='tight')
    fig.savefig(root/'report/outer_convergence_comparison.pdf',bbox_inches='tight');plt.close(fig)
    # Matched-iteration exact costs expose optimization overhead. This is a
    # diagnostic comparison, not an additive decomposition or a new target.
    exact_lookup={(row['n'],row['r'],row['system_seed']):row['gap'] for row in exact}
    endpoint_groups=defaultdict(list)
    for row in final:
        endpoint_groups[row['n'],row['r'],row['method']].append(row)
    endpoint=[]
    for (n,r,method),rows in sorted(endpoint_groups.items()):
        good=all(row['stable'] for row in rows)
        gaps=[row['gap'] for row in rows] if good else []
        differences=[row['gap']-exact_lookup[n,r,row['system_seed']] for row in rows] if good else []
        endpoint.append(dict(n=n,r=r,method=method,stable_systems=sum(row['stable'] for row in rows),
            gap_mean=float(np.mean(gaps)) if good else None,
            gap_min=min(gaps) if good else None,gap_max=max(gaps) if good else None,
            exact_mean=float(np.mean([exact_lookup[n,r,row['system_seed']] for row in rows])),
            sample_minus_exact_mean=float(np.mean(differences)) if good else None,
            normalized_excess_rn2=float(np.mean(differences))/(r*n*n) if good else None))
    exploratory=[]
    for method in ('raw','truncated'):
        selected=[row for row in endpoint if row['method']==method and row['r']/row['n']<=config['fit_max_rank_fraction']
            and row['sample_minus_exact_mean'] is not None and row['sample_minus_exact_mean']>0]
        fit=dict(method=method,metric='mean sampled gap minus matched-iteration exact gap',
            cells=[[row['n'],row['r']] for row in selected],
            caveat='Diagnostic only: subtraction is not an exact error decomposition; does not establish a fixed-accuracy end-to-end sample complexity or its inverse-budget dependence.')
        if len(selected)>=5:
            x=np.array([[1.,np.log(row['n']),np.log(row['r'])] for row in selected])
            y=np.log([row['sample_minus_exact_mean'] for row in selected])
            if np.linalg.matrix_rank(x)==3:
                coef=np.linalg.lstsq(x,y,rcond=None)[0]
                fit.update(alpha_n=float(coef[1]),beta_r=float(coef[2]),
                    log_R2=float(1-np.sum((y-x@coef)**2)/max(np.sum((y-y.mean())**2),1e-30)))
        exploratory.append(fit)
    atomic_json(root/'report/endpoint_diagnostic.json',dict(records=endpoint,fits=exploratory,
        common_total_transitions=final[0]['transitions'],outer_stages=config['stages'],
        inference='Primary sample-complexity figures use total absolute gap. Exact subtraction here only diagnoses optimization overhead and sampling effects; never selects a policy.'))
    fig,axes=plt.subplots(2,2,figsize=(12,9))
    for ax,n in zip(axes[0],(50,100)):
        for method,color,linestyle in [('raw','#777','--'),('truncated','#12699c','-')]:
            selected=sorted([row for row in endpoint if row['n']==n and row['method']==method],key=lambda row:row['r'])
            ax.semilogx([row['r'] for row in selected],[row['gap_mean'] if row['gap_mean'] is not None else np.nan for row in selected],
                'o'+linestyle,color=color,label=method)
            for row in selected:
                if row['gap_mean'] is not None:ax.vlines(row['r'],row['gap_min'],row['gap_max'],color=color,alpha=.4)
        selected=sorted([row for row in endpoint if row['n']==n and row['method']=='raw'],key=lambda row:row['r'])
        ax.semilogx([row['r'] for row in selected],[row['exact_mean'] for row in selected],'o-',color='#269b62',label='exact critic')
        ax.set_title(f'n={n}: final absolute gap at the same budget')
        ax.set_xlabel('Rank r');ax.set_ylabel('Absolute gap');ax.grid(alpha=.2);ax.legend()
        ax.set_xticks([1,2,4,8,16],labels=[1,2,4,8,16])
    for ax,method in zip(axes[1],('raw','truncated')):
        for n,color in [(50,'#d08028'),(100,'#216fa0')]:
            selected=sorted([row for row in endpoint if row['n']==n and row['method']==method],key=lambda row:row['r'])
            ax.plot([row['r'] for row in selected],[row['normalized_excess_rn2'] if row['normalized_excess_rn2'] is not None else np.nan for row in selected],
                'o-',color=color,label=f'n={n}')
        ax.set_xscale('log');ax.set_yscale('symlog',linthresh=1e-7)
        ax.set_title(f'{method}: exact-subtracted diagnostic')
        ax.set_xlabel('Rank r');ax.set_ylabel('(Sampled gap - exact gap) / (r n²)')
        ax.set_xticks([1,2,4,8,16],labels=[1,2,4,8,16]);ax.grid(alpha=.2);ax.legend()
    fig.suptitle('Rank effects at a fixed total budget and update count\nExact subtraction is diagnostic; it is not the fixed-accuracy sample-complexity criterion',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.92))
    fig.savefig(root/'report/endpoint_rank_diagnostic.png',dpi=180,bbox_inches='tight')
    fig.savefig(root/'report/endpoint_rank_diagnostic.pdf',bbox_inches='tight');plt.close(fig)
    print(json.dumps(dict(numerical_audit='PASS',stable=sum(stable),methods=len(stable))),flush=True)


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();main(a.release,a.output)
