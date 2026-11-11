"""Snapshot paired constant/growing NPG curves; retain partial status."""
import argparse
import json
from pathlib import Path

import numpy as np


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--current',type=Path,required=True)
    parser.add_argument('--constant',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    current_proof=json.loads((args.current/'verification.json').read_text())
    old_proof=json.loads((args.constant/'verification.json').read_text())
    compatibility=json.loads((args.current/'compatibility_verification.json').read_text())
    assert current_proof['status']==old_proof['status']==compatibility['status']=='PASS'
    assert compatibility['identity']==current_proof['identity']
    constant=json.loads((args.constant/'NPG'/'raw'/'task-000.json').read_text())
    assert constant['identity']==old_proof['identity']
    raw=args.current/'NPG'/'raw'/'task-000.json'
    complete=raw.exists()
    if complete:
        current=json.loads(raw.read_text())
        assert current['identity']==current_proof['identity']
        rows=current['records']
        assert current['task']==constant['task']
    else:
        with np.load(args.current/'NPG'/'checkpoints'/'task-000.npz',allow_pickle=False) as archive:
            assert json.loads(str(archive['identity']))==current_proof['identity']
            rows=json.loads(str(archive['records']))
    latest=max(r['stage'] for r in rows)
    final=[r for r in rows if r['stage']==latest]
    total=constant['assigned_total_budget']
    assert all(r['assigned_total_budget']==total for r in rows)
    args.destination.mkdir(parents=True,exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    methods=['dense','adaptive_1','known_rank']
    names=['Dense','Adaptive truncation (c=1)','Fixed rank 4 reference']
    fig,axes=plt.subplots(2,3,figsize=(15,7))
    for col,(method,name) in enumerate(zip(methods,names)):
        for row_index,(metric,label) in enumerate([('value','True cost J(K)'),('gap','Absolute gap J(K) - J*')]):
            ax=axes[row_index,col]
            for records,color,style,title in [(constant['records'],'#888888','--','Constant batch: complete'),
                                              (rows,'#0072b2','-',f'Growing batch: {latest}/64 updates')]:
                observed=[r for r in records if r['method']==method and r.get('observed',True)
                          and r['stable'] and r.get(metric) is not None]
                ax.plot([r['actual_transitions']/1e6 for r in observed],
                        [max(r[metric],1e-12) if metric=='gap' else r[metric] for r in observed],
                        color=color,linestyle=style,lw=1.8,marker='o',markersize=2.5,label=title)
            ax.set_xlim(0,total/1e6*1.02)
            if metric=='gap':ax.set_yscale('log')
            ax.grid(alpha=.2);ax.set_xlabel('Actual transitions (millions)');ax.set_ylabel(label)
            if row_index==0:ax.set_title(name)
    fig.suptitle('Exact rank 4 | n=m=50 | One system / one data seed\n'
                 'Same 64 updates and planned total budget; growing run is incomplete' if not complete else
                 'Exact rank 4 | n=m=50 | One system / one data seed\nSame 64 updates and complete total budget',fontsize=12)
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='lower center',ncol=2,frameon=False)
    fig.tight_layout(rect=(0,.05,1,.92))
    fig.savefig(args.destination/'exact_npg_constant_vs_growing.png',dpi=160);plt.close(fig)
    def compact(record):
        return {k:record.get(k) for k in ('method','stage','N','actual_transitions','value','gap','rho','retained_rank','threshold','stable')}
    result=dict(complete=complete,stage=latest,planned_budget=total,
                current=[compact(r) for r in final],
                constant_final=[compact(r) for r in constant['records'] if r['stage']==64],
                current_identity=current_proof['identity'],constant_identity=old_proof['identity'])
    (args.destination/'snapshot.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(complete=complete,stage=latest,planned_budget=total,
                         current=[compact(r) for r in final]),indent=2))


if __name__=='__main__':main()
