"""CSV-only CE gap-ratio/certificate plots; never evaluates a policy."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path


def read(path):
    with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    a=p.parse_args();assert not a.out.exists()
    a.cache.mkdir(parents=True,exist_ok=True);os.environ['MPLCONFIGDIR']=str(a.cache.resolve())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=read(a.data/'summary.csv');cert=read(a.data/'certificate_summary.csv')
    assert len(rows)==80 and len(cert)==8
    a.out.mkdir(parents=True);files=[]
    budgets=[2048,8192,32768,131072,524288];ns=[24,36,48,72]
    colors=['#2066a8','#da6b25','#3c9366','#9355a6','#797027']
    def save(fig,name):
        for suffix in ['png','svg']:
            path=a.out/(name+'.'+suffix);fig.savefig(path,dpi=180)
            files.append(dict(path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        plt.close(fig)
    for kind in ['both_stable','failure_inclusive']:
        figure=plt.figure(figsize=(14.5,8.6));grid=figure.add_gridspec(2,2,height_ratios=[3.8,1.6])
        handles=[]
        for j,family in enumerate(['S','U']):
            ax=figure.add_subplot(grid[0,j]);subset=[r for r in rows if r['family']==family and r['ratio_kind']==kind]
            positive=[float(r[key]) for r in subset for key in ['ratio_median','ci_low','ci_high']
                      if r[key] and math.isfinite(float(r[key])) and float(r[key])>0]
            cap=max(positive)*1.35
            lookup={(int(r['n']),int(r['N'])):r for r in subset}
            for color,N in zip(colors,budgets):
                group=[lookup[(n,N)] for n in ns];x=[n/2 for n in ns]
                y=[float(r['ratio_median']) for r in group]
                line=ax.plot(x,[min(v,cap) for v in y],'o-',color=color,
                    label=r'$N=2^{'+str(N.bit_length()-1)+'}$')[0]
                if j==0:handles.append(line)
                for xx,yy,row in zip(x,y,group):
                    low=float(row['ci_low']);high=float(row['ci_high'])
                    ax.vlines(xx,max(low,.01),min(high,cap),color=color,alpha=.8)
                    ax.hlines(max(low,.01),xx-.25,xx+.25,color=color)
                    if math.isfinite(high):ax.hlines(high,xx-.25,xx+.25,color=color)
                    else:
                        ax.annotate(r'$+\infty$',xy=(xx,cap),xytext=(xx,cap*.74),
                            arrowprops=dict(arrowstyle='->',color=color),color=color,
                            fontsize=8,ha='center')
            ax.set_yscale('log');ax.set_ylim(min(.8,min(positive)*.8),cap*1.12)
            ax.axhline(1.,color='.4',linestyle=':',linewidth=1)
            ax.set_xticks([n/2 for n in ns]);ax.set_xlabel('n / r (r = 2)')
            ax.set_ylabel('gap(dense) / gap(rank 2)');ax.set_title('Family '+family)
            ax.grid(alpha=.2)
            ta=figure.add_subplot(grid[1,j]);ta.axis('off')
            cells=[[lookup[(n,N)]['dense_stable']+' / '+lookup[(n,N)]['truncated_stable']
                    for N in budgets] for n in ns]
            table=ta.table(cellText=cells,rowLabels=['n='+str(n) for n in ns],
                colLabels=[r'$2^{'+str(N.bit_length()-1)+'}$' for N in budgets],
                cellLoc='center',loc='center')
            table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1,1.5)
            ta.set_title('Stable dense / rank-2 counts (each out of 32), columns N',fontsize=10,pad=10)
        qualifier='both-stable pairs' if kind=='both_stable' else 'failure-inclusive pairs; only joint failures dropped'
        figure.suptitle('Same-data CE gap ratios: '+qualifier+'\n95% system-cluster bootstrap; arrows mark infinite upper bounds',fontsize=13)
        figure.legend(handles,[h.get_label() for h in handles],loc='lower center',ncol=5,frameon=False)
        figure.tight_layout(rect=(0,.05,1,.92));save(figure,'CE-ratio-'+kind)
    figure,axes=plt.subplots(1,2,figsize=(11,4.4))
    for family,color in [('S','#2066a8'),('U','#da6b25')]:
        group=sorted((r for r in cert if r['family']==family),key=lambda r:int(r['n']))
        for ax,metric,title in zip(axes,['P0_op','v_star'],['Initial certificate norm','Optimal sensitivity v_star']):
            x=[int(r['n']) for r in group];y=[float(r[metric+'_median']) for r in group]
            lo=[float(r[metric+'_q25']) for r in group];hi=[float(r[metric+'_q75']) for r in group]
            ax.plot(x,y,'o-',color=color,label=family);ax.fill_between(x,lo,hi,color=color,alpha=.16)
            ax.set_yscale('log');ax.set_xlabel('n = m');ax.set_title(title);ax.grid(alpha=.2)
    axes[0].axhline(1.5625,color='.4',linestyle=':',label='S class bound')
    axes[0].legend(frameon=False);axes[1].legend(frameon=False)
    figure.suptitle('Median / IQR over 8 independent systems; certificates are evaluation metadata')
    figure.tight_layout();save(figure,'CE-certificates')
    manifest=dict(status='COMPLETE_CSV_ONLY',new_transitions=0,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        csv_hashes={name:hashlib.sha256((a.data/name).read_bytes()).hexdigest() for name in ['summary.csv','certificate_summary.csv']},files=files)
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest))


if __name__=='__main__':main()
