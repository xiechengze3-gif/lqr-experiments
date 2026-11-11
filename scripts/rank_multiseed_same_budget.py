"""Paired same-budget supplement; statistics and figures on Grace compute nodes."""
import argparse
import csv
import hashlib
import json
import os
import shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dense_scaling import require_compute, atomic_json


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    return float(value) if np.isfinite(value) else None


def short(value):
    for scale,suffix in ((1e9,'B'),(1e6,'M'),(1e3,'k')):
        if value>=scale:
            return f'{value/scale:.3g}{suffix}'
    return str(int(value))


def main(report):
    report=Path(report)
    unchanged={name:sha(report/name) for name in ('endpoints.csv','samples_to_precision.csv','summary.json','numerical_audit.json')}
    summary=json.loads((report/'summary.json').read_text())
    assert summary['status']=='complete' and len(summary['algorithms'])==1
    assert json.loads((report/'numerical_audit.json').read_text())['status']=='PASS'
    algorithm=summary['algorithms'][0]
    with (report/'endpoints.csv').open(newline='') as stream:
        endpoints=list(csv.DictReader(stream))
    grouped={}
    for e in endpoints:
        key=e['cell'],int(e['samples'])
        grouped.setdefault(key,{})[(e['method'],int(e['seed']))]=e
    pairs=[]
    for (cell,budget),lookup in sorted(grouped.items()):
        assert len(lookup)==2*len(summary['system_seeds'])
        raw,truncated=[],[]
        for seed in summary['system_seeds']:
            for method,values in (('raw',raw),('truncated',truncated)):
                e=lookup[(method,seed)]
                values.append(float(e['gap']) if e['eligible']=='True' else np.inf)
        raw,truncated=np.array(raw),np.array(truncated)
        both=np.isfinite(raw)&np.isfinite(truncated)&(truncated>0)
        ratio=float(np.median(raw[both]/truncated[both])) if both.any() else None
        base=next(iter(lookup.values()))
        record=dict(algorithm=algorithm,cell=cell,n=int(base['n']),r=int(base['r']),tail_mode=base['tail_mode'],
                    level=float(base['level']),samples=budget,systems=len(raw),
                    raw_eligible=int(np.isfinite(raw).sum()),truncated_eligible=int(np.isfinite(truncated).sum()),
                    paired_eligible=int(both.sum()),paired_gap_ratio_median=ratio,
                    truncated_better_systems=int((truncated<raw).sum()),raw_better_systems=int((raw<truncated).sum()),
                    both_failed_systems=int((~np.isfinite(raw)&~np.isfinite(truncated)).sum()))
        for method,values in (('raw',raw),('truncated',truncated)):
            quantile=np.quantile(values,[.25,.5,.75],method='inverted_cdf')
            for label,value in zip(('q25','median','q75'),quantile):
                record[f'{method}_gap_{label}']=number(value)
        pairs.append(record)
    for mode,label in (('exact','exact'),('frobenius','small-tail')):
        fig,axes=plt.subplots(1,2,figsize=(12.8,5.3))
        for ax,n in zip(axes,(50,100)):
            selected=[p for p in pairs if p['n']==n and p['r'] in (1,2,4,8,16) and p['tail_mode']==mode]
            largest=max(p['samples'] for p in selected)
            selected=sorted([p for p in selected if p['samples']==largest],key=lambda p:p['r'])
            assert [p['r'] for p in selected]==[1,2,4,8,16]
            finite_values=[p[f'{method}_gap_{q}'] for p in selected for method in ('raw','truncated')
                           for q in ('q25','median','q75') if p[f'{method}_gap_{q}'] is not None]
            ceiling=max(finite_values,default=1.)*3.
            for method,color in (('raw','#b43b39'),('truncated','#1769aa')):
                x=np.array([p['r'] for p in selected])
                y=[max(1e-12,p[f'{method}_gap_median']) if p[f'{method}_gap_median'] is not None else np.nan for p in selected]
                ax.plot(x,y,color=color,marker='o',label=method)
                low=np.array([max(1e-12,p[f'{method}_gap_q25']) if p[f'{method}_gap_q25'] is not None else np.nan for p in selected])
                high=np.array([max(1e-12,p[f'{method}_gap_q75']) if p[f'{method}_gap_q75'] is not None else np.nan for p in selected])
                ax.fill_between(x,low,high,color=color,alpha=.15)
                for p in selected:
                    if p[f'{method}_gap_median'] is None:
                        ax.scatter(p['r'],ceiling,color=color,marker='^')
                        ax.annotate('failed median',(p['r'],ceiling),fontsize=7,color=color,xytext=(0,5),textcoords='offset points',ha='center')
            gain=['--' if p['paired_gap_ratio_median'] is None else f"{p['paired_gap_ratio_median']:.3g}x" for p in selected]
            counts=[f"{p['raw_eligible']}/{p['truncated_eligible']}" for p in selected]
            ax.set(xscale='log',yscale='log',xlabel='Rank r',ylabel='Median cost gap (failed runs = infinity)',
                   title=f'{algorithm}, n={n}, M={short(largest)}')
            ax.set_xticks([1,2,4,8,16],labels=[1,2,4,8,16])
            ax.set_xlim(.8,20)
            ax.set_ylim(max(1e-12,min(finite_values,default=1.))*.6,ceiling*1.8)
            ax.grid(alpha=.2)
            ax.legend()
            ax.text(.5,-.22,'r:  1       2       4       8       16\npaired gap ratio:  '+'   '.join(gain)+'\neligible raw/truncated:  '+'   '.join(counts),
                    transform=ax.transAxes,ha='center',fontsize=8)
        tail='exact B' if mode=='exact' else 'small tail, ||B-B_r||_F=0.03'
        fig.suptitle(f'Same sample budget across rank: {tail}',fontsize=14)
        fig.subplots_adjust(top=.84,bottom=.3,wspace=.27)
        fig.text(.5,.025,'10 independent systems. Shading: interquartile range. Same primitive-transition budget within each panel.\n'
                 'Gap ratios use paired eligible systems; eligibility counts disclose failures. Ratios above 1 favor truncation.',ha='center',fontsize=9)
        fig.savefig(report/f'same_budget_{label}_rank.png',dpi=160)
        fig.savefig(report/f'same_budget_{label}_rank.pdf')
        plt.close(fig)
    with (report/'paired_same_budget.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    assert all(sha(report/name)==digest for name,digest in unchanged.items())
    shutil.copyfile(__file__,report/'same_budget_supplement_source.py')
    atomic_json(report/'same_budget_supplement_provenance.json',dict(status='PASS',algorithm=algorithm,
        source_sha256=sha(__file__),inputs_unchanged=unchanged,slurm_job_id=os.environ['SLURM_JOB_ID'],
        failed_runs_retained=True,paired_ratio_conditional_on_eligible_disclosed=True))
    print(json.dumps(dict(status='PASS',algorithm=algorithm,pairs=len(pairs))),flush=True)


if __name__=='__main__':
    require_compute()
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    main(args.report)
