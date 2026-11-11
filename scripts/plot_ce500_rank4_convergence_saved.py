"""Plot only saved CE results; all shown runs have no transition-cost ambiguity."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    with (a.input/'all_checkpoints.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    fig,ax=plt.subplots(figsize=(8.8,4.6),layout='constrained')
    for rank,method,color,label in [(4,'dense','#ba4737','rank 4 dense'),
        (4,'truncated','#1476a3','rank 4 truncated'),(500,'dense','#666666','rank 500 dense reference')]:
        selected=[q for q in rows if int(q['rank'])==rank and q['method']==method]
        budgets=sorted({int(q['transitions']) for q in selected});groups=[]
        for b in budgets:
            rr=[q for q in selected if int(q['transitions'])==b]
            assert len(rr)==30
            groups.append([float(q['gap']) if q['stable'].lower()=='true' and q['gap'] else np.inf for q in rr])
        values=np.asarray(groups);median=np.median(values,axis=1);lower,upper=np.quantile(values,[.25,.75],axis=1)
        ax.plot(budgets,median,'-' if rank==4 else '--',color=color,label=label)
        ax.fill_between(budgets,lower,upper,color=color,alpha=.12)
    for target in [.1,.05]:
        ax.axhline(target,color='.55',ls=':',lw=1)
        ax.text(11000,target*1.07,f'target {target:g}',color='.4',fontsize=9)
    ax.set(xscale='log',yscale='log',xlabel='Primitive transitions (including burn-in)',
        ylabel='Absolute = relative optimality gap',title='CE500 | initial gap = 1 | 30 paired seeds | median and IQR')
    ax.grid(alpha=.2);ax.legend()
    for ext in ['png','svg']:fig.savefig(a.output/('rank4_gap_convergence.'+ext),dpi=180,facecolor='white')
    plt.close(fig)
    (a.output/'local_plot_provenance.json').write_text(json.dumps(dict(kind='saved_data_postprocessing_only',
        python=sys.version,numpy=np.__version__,matplotlib=matplotlib.__version__,
        matplotlib_config_dir=os.environ.get('MPLCONFIGDIR'),temporary_directory=os.environ.get('TEMP'),
        input_csv_sha256=hashlib.sha256((a.input/'all_checkpoints.csv').read_bytes()).hexdigest(),
        plotting_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
