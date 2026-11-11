"""Portable X6a CSV-only plotting. No model solves or trajectory generation."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--csv',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--cache',required=True,type=Path)
    args=parser.parse_args()
    assert not args.out.exists(),'Use a new output version; never replace figures.'
    args.cache.mkdir(parents=True,exist_ok=True)
    os.environ['MPLCONFIGDIR']=str(args.cache.resolve())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with args.csv.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    rows=[r for r in rows if r['role']=='formal']
    args.out.mkdir(parents=True)
    colors=dict(dense='#2066a8',truncated='#d66a24')
    outputs=[]
    for algorithm in ['NPG','PI','CE']:
        metrics=['relative_error','paired_error_ratio']
        if algorithm!='CE':metrics+=['rho_op','left_sin_theta','projection']
        for metric in metrics:
            figure,axes=plt.subplots(2,4,figsize=(16.8,7.4),sharex=True)
            for i,family in enumerate(['S','U']):
                for j,n in enumerate([24,36,48,72]):
                    ax=axes[i,j]
                    group=[r for r in rows if r['algorithm']==algorithm
                           and r['family']==family and int(r['n'])==n]
                    arms=['dense'] if metric in ['rho_op','paired_error_ratio'] else ['dense','truncated']
                    for arm in arms:
                        selected=sorted((r for r in group if r['arm']==arm),key=lambda r:int(r['N']))
                        if not selected:continue
                        x=[int(r['N']) for r in selected]
                        if metric=='projection':
                            y=[float(r['projection_mean']) for r in selected]
                            se=[float(r['projection_se']) for r in selected]
                            ax.errorbar(x,y,yerr=se,color=colors[arm],marker='o',
                                        capsize=3,label=arm,linewidth=1.5)
                        else:
                            y=[float(r[metric+'_median']) for r in selected]
                            lo=[float(r[metric+'_q25']) for r in selected]
                            hi=[float(r[metric+'_q75']) for r in selected]
                            label='dense / truncated' if metric=='paired_error_ratio' else arm
                            ax.plot(x,y,'o-',color=colors[arm],label=label,linewidth=1.5)
                            ax.fill_between(x,lo,hi,color=colors[arm],alpha=.15)
                        ax.set_xscale('log',base=4)
                        ax.set_xticks(x,labels=[r'$2^{'+str(v.bit_length()-1)+'}$' for v in x])
                        ax.tick_params(axis='x',labelsize=9)
                    if metric in ['relative_error','rho_op']:ax.set_yscale('log')
                    if metric in ['rho_op','projection','paired_error_ratio']:
                        ax.axhline(1.,color='.4',linestyle=':',linewidth=1)
                    if metric=='left_sin_theta':ax.set_ylim(-.02,1.02)
                    ax.set_title(f'{family}, n=m={n}')
                    ax.grid(alpha=.2)
                    if i==1:ax.set_xlabel('N transitions' if algorithm=='CE' else 'N pulse blocks')
            titles=dict(relative_error='Relative Frobenius error',
                        paired_error_ratio='Paired estimation-error ratio: dense / truncated',
                        rho_op='Dense operator error / true second singular value',
                        left_sin_theta='Top-2 left-subspace sin(theta)',
                        projection='Projection on true target, mean +/- system SE')
            uncertainty='system means +/- one SE' if metric=='projection' else 'system medians, shaded IQR'
            figure.suptitle(f'{algorithm}: {titles[metric]}\n8 independent systems x 4 seeds; {uncertainty}',fontsize=12)
            handles,labels=axes[0,0].get_legend_handles_labels()
            figure.legend(handles,labels,loc='lower center',ncol=2,frameon=False)
            figure.tight_layout(rect=(0,.045,1,.94))
            for suffix in ['png','svg']:
                path=args.out/(algorithm+'-'+metric+'.'+suffix)
                figure.savefig(path,dpi=180)
                outputs.append(dict(path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            plt.close(figure)
    manifest=dict(status='COMPLETE',scope='CSV_ONLY_ZERO_SIMULATION',
                  csv=str(args.csv),csv_sha256=hashlib.sha256(args.csv.read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),files=outputs)
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest))


if __name__=='__main__':main()
