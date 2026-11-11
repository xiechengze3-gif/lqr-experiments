"""Saved CSV figure refinement: clean pair-count tables and explicit stable-region views."""
import csv,json,math,os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import engine as e

def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
def save(fig,dest,name):
    fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(dest/(name+'.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)

def x2():
    old=e.OUT/'X2/report-ce';dest=e.OUT/'X2/report-ce-v2';assert not dest.exists();dest.mkdir()
    rows=read(old/'fixed_budget_ratios.csv');fig,axs=plt.subplots(2,2,figsize=(11,5.3),gridspec_kw={'height_ratios':[4,1]})
    for col,metric in enumerate(['absolute_gap_ratio','relative_gap_ratio']):
        ax=axs[0,col];table=[]
        for nd,color in zip([16,64,256],['#386aab','#cf7735','#57976a']):
            points=sorted([r for r in rows if int(r['r'])==2 and float(r['N_over_d'])==nd and r['metric']==metric],key=lambda r:int(r['n']))
            assert len(points)==4
            x=[float(r['n_over_r']) for r in points];y=[float(r['paired_ratio_median']) for r in points]
            ax.plot(x,y,'o-',color=color,label=f'N/(n+m)={nd}')
            ax.fill_between(x,[float(r['bootstrap95_low']) for r in points],[float(r['bootstrap95_high']) for r in points],color=color,alpha=.1)
            table.append([r['finite_pairs']+'/32' for r in points])
        ax.axhline(1,color='grey',ls='--',lw=.7);ax.set(yscale='log',xticks=[6,12,24,48],xlabel='n/r (r=2)',
           ylabel='Paired dense / truncated gap',title=metric.replace('_',' '));ax.legend(fontsize=7,frameon=False);ax.grid(alpha=.2)
        below=axs[1,col];below.axis('off');t=below.table(cellText=table,rowLabels=['N/d16','N/d64','N/d256'],colLabels=['n12','n24','n48','n96'],loc='center')
        t.auto_set_font_size(False);t.set_fontsize(7);t.scale(1,1.15);below.set_title('Finite pairs / full32; whole-system bootstrap95% intervals above',fontsize=7)
    fig.suptitle('X2 CE fixed budgets: finite-pair diagnostics; absolute/relative ratios coincide by initial-gap cancellation',fontsize=9)
    save(fig,dest,'fixed_budget_ratios_clean')
    e.save(dest/'REPORT.json',dict(status='COMPLETE',scope='SAVED_CSV_FIGURE_REFINEMENT',source_report_sha256=e.sha(old/'REPORT.json'),
       new_training_transitions=0,source_sha256=e.sha(__file__),job=os.environ['SLURM_JOB_ID']))

def x3():
    old=e.OUT/'X3/report-ce';dest=e.OUT/'X3/report-ce-v2';assert not dest.exists();dest.mkdir()
    rows=read(old/'all_statistics.csv');env=read(old/'fixed_k_envelope.csv');regions=[]
    for n in [16,32]:
        fig,axs=plt.subplots(1,3,figsize=(12,4))
        for ax,sp in zip(axs,['smooth','gapped','flat']):
            cell=[r for r in rows if int(r['n'])==n and r['spectrum']==sp and r['metric']=='gap'];lookup={(int(r['N']),r['mode']):r for r in cell}
            envelope={int(r['N']):r for r in env if int(r['n'])==n and r['spectrum']==sp};modes=['dense','adaptive_paper','adaptive_split']
            valid=[N for N in sorted(envelope) if int(envelope[N]['stable_count'])==32 and all(int(lookup[(N,mode)]['stable_count'])==32 for mode in modes)]
            regions.append(dict(n=n,spectrum=sp,displayed_prefixes=valid,rule='all32 outputs stable for dense, both adaptive rules and selected fixed-k median envelope'))
            if valid:
                for mode,color in zip(modes,['#386aab','#cf7735','#57976a']):
                    selected=[lookup[(N,mode)] for N in valid]
                    ax.plot(valid,[float(r['median']) for r in selected],'-o',ms=3,color=color,label=mode)
                    ax.fill_between(valid,[float(r['q25']) for r in selected],[float(r['q75']) for r in selected],color=color,alpha=.1)
                ax.plot(valid,[float(envelope[N]['envelope_median']) for N in valid],'k--',lw=1,label='fixed-k envelope (diagnostic)')
                ax.set(xscale='log',yscale='log',xlabel='Regression N (add512 burn)',ylabel='Absolute gap, median/IQR',title=f'n{n}, {sp}\nEach displayed cell stable32/32')
            else:
                ax.text(.5,.5,'No common all-stable prefix\nSee complete grid and failure heatmap',ha='center',va='center',transform=ax.transAxes)
                ax.set_title(f'n{n}, {sp}')
            ax.grid(alpha=.2)
        axs[-1].legend(fontsize=6,frameon=False);fig.suptitle('X3 CE stable-region view; full grid, failed outputs and all fixed orders remain in report-ce',fontsize=9)
        save(fig,dest,f'stable_region_n{n}')
    fig,axs=plt.subplots(1,2,figsize=(10,3.5))
    for ax,n in zip(axs,[16,32]):
        for sp,color in zip(['smooth','gapped','flat'],['#386aab','#cf7735','#57976a']):
            selected=sorted([r for r in env if int(r['n'])==n and r['spectrum']==sp],key=lambda r:int(r['N']))
            ax.step([int(r['N'])/(2*n) for r in selected],[int(r['best_k']) for r in selected],where='mid',color=color,label=sp)
        ax.set(xscale='log',xlabel='N/(n+m)',ylabel='Retained order minimizing fixed-k median',title=f'n=m{n}; post-hoc diagnostic');ax.legend(frameon=False,fontsize=7);ax.grid(alpha=.2)
    fig.suptitle('X3 fixed-order envelope: displayed order need not change monotonically; no truth-based learner selection',fontsize=9)
    save(fig,dest,'best_retained_order')
    e.save(dest/'REPORT.json',dict(status='COMPLETE',scope='SAVED_CSV_FIGURE_REFINEMENT',source_report_sha256=e.sha(old/'REPORT.json'),
       stable_regions=regions,full_grid_preserved=True,new_training_transitions=0,source_sha256=e.sha(__file__),job=os.environ['SLURM_JOB_ID']))

def main():
    e.require_compute();plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    x2();x3();print(json.dumps(dict(status='COMPLETE',new_learning_runs=0)))

if __name__=='__main__':main()
