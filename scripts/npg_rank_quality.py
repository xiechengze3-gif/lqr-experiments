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
    print(json.dumps(dict(numerical_audit='PASS',stable=sum(stable),methods=len(stable))),flush=True)


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();main(a.release,a.output)
