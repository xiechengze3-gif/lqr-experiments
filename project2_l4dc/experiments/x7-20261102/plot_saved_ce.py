"""Render frozen X7 CSV values only; no model solves or statistical refitting."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
runtime=ROOT/'runtime-plot-v1'
for sub in ('mpl','tmp','cache'):(runtime/sub).mkdir(parents=True,exist_ok=True)
os.environ['MPLCONFIGDIR']=str(runtime/'mpl')
os.environ['XDG_CACHE_HOME']=str(runtime/'cache')
os.environ['TEMP']=str(runtime/'tmp');os.environ['TMP']=str(runtime/'tmp')
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D

CELLS=[('24','geometric'),('24','polynomial'),('48','geometric'),('48','polynomial')]
RULES=['dense','adaptive_paper','adaptive_split','sensitivity_C0p5','sensitivity_C1p0']
LABEL={'dense':'Dense','adaptive_paper':'Paper C=2.569','adaptive_split':'Split proxy',
       'sensitivity_C0p5':'Sensitivity C=0.5','sensitivity_C1p0':'Sensitivity C=1.0'}
COLOR=['#202833','#ba423d','#157f82','#7b69a4','#c18a21']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def f(row,key):return float(row[key]) if row[key] else math.nan
def label(mode):return LABEL.get(mode,'k='+mode[1:])
def cell(rows,n,spectrum):return [r for r in rows if r['n']==n and r['spectrum']==spectrum]
def budgets(rows):return sorted({int(r['N']) for r in rows})
def mode_order(rows):
    modes=list(dict.fromkeys(r['mode'] for r in rows))
    return sorted([m for m in modes if m.startswith('k')],key=lambda x:int(x[1:]))+[
        m for m in RULES if m in modes]
def failures(rows):return sum(int(r['full'])-int(r['stable']) for r in rows)
def fail_title(rows):
    denominator=sum(int(r['full']) for r in rows)
    return f"{failures(rows)}/{denominator} failed outputs"
def finish(fig,out,name,caption,legend=None):
    if legend:
        fig.legend(handles=legend,loc='upper center',bbox_to_anchor=(.5,.96),
                   ncol=min(3,len(legend)),frameon=False,fontsize=10)
    fig.text(.5,.012,caption,ha='center',va='bottom',fontsize=9)
    for ext in ('png','svg'):
        path=out/(name+'.'+ext);assert not path.exists()
        fig.savefig(path,dpi=180,facecolor='white')
    plt.close(fig)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    assert out.is_relative_to(ROOT) and not out.exists();out.mkdir(parents=True)
    proof=json.loads((ROOT/'summary-verification.json').read_text())
    for name,expected in proof['files'].items():assert sha(ROOT/name)==expected
    summary=read('summary.csv');ratios=read('paired_ratios.csv')
    best=read('posthoc_best_fixed.csv');orders=read('adaptive_orders.csv');slopes=read('log_slopes.csv')
    assert len(summary)==336 and len(ratios)==624
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,
        'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})

    fig,axes=plt.subplots(2,2,figsize=(15,11))
    fig.suptitle('CE with full-rank B: fixed-order error and truncation bias',y=.985,fontsize=16)
    fig.subplots_adjust(left=.075,right=.89,top=.91,bottom=.10,hspace=.36,wspace=.27)
    for ax,(n,spectrum) in zip(axes.flat,CELLS):
        group=cell(summary,n,spectrum);group=[r for r in group if r['mode']=='dense' or r['mode'].startswith('k')]
        ns=budgets(group);modes=mode_order(group);lookup={(r['mode'],int(r['N'])):r for r in group}
        data=[[f(lookup[m,N],'relative_gap_median') for N in ns] for m in modes]
        image=ax.imshow(data,norm=LogNorm(vmin=.002,vmax=10),cmap='viridis_r',aspect='auto')
        ax.set_xticks(range(len(ns)),[str(N) for N in ns],rotation=25,ha='right')
        ax.set_yticks(range(len(modes)),[label(m) for m in modes]);ax.set_xlabel('Regression transitions N')
        ax.set_title(f'n=m={n}, {spectrum}; {fail_title(group)}',pad=10)
        for i,m in enumerate(modes):
            for j,N in enumerate(ns):
                row=lookup[m,N];value=f(row,'relative_gap_median')
                text=f'{value:.2g}' if math.isfinite(value) else '∞'
                if int(row['stable'])<32:text+=f"\nF={32-int(row['stable'])}/32"
                ax.text(j,i,text,ha='center',va='center',fontsize=8,
                        color='white' if value>.2 else '#101010')
        for b in cell(best,n,spectrum):
            if b['best_fixed_mode']:
                i=modes.index(b['best_fixed_mode']);j=ns.index(int(b['N']))
                ax.scatter(j,i,s=480,marker='s',facecolors='none',edgecolors='#ff905d',linewidths=1.8)
    cax=fig.add_axes([.92,.17,.016,.64]);fig.colorbar(image,cax=cax,label='Full-32 median relative gap (log color)')
    finish(fig,out,'fixed_orders',
        'Orange box: post hoc best fixed order by absolute gap, including dense; not a learner. Each cell uses all 32 runs.\n'
        'Failure gaps are +∞; all displayed cells have 0/32 failures. N excludes 512 burn-in transitions; colors saturate outside [0.002, 10].')

    fig,axes=plt.subplots(2,2,figsize=(14,10.5))
    fig.suptitle('CE: adaptive rules and registered sensitivities',y=.993,fontsize=16)
    fig.subplots_adjust(left=.075,right=.98,top=.84,bottom=.12,hspace=.40,wspace=.25)
    handles=[]
    for ax,(n,spectrum) in zip(axes.flat,CELLS):
        group=cell(summary,n,spectrum);ns=budgets(group)
        for mode,color in zip(RULES,COLOR):
            rs=sorted([r for r in group if r['mode']==mode],key=lambda r:int(r['N']))
            line,=ax.plot(ns,[f(r,'relative_gap_median') for r in rs],'-o',color=color,label=label(mode),ms=4)
            ax.fill_between(ns,[f(r,'relative_gap_q25') for r in rs],
                            [f(r,'relative_gap_q75') for r in rs],color=color,alpha=.09)
            if len(handles)<5:handles.append(line)
        lookup={(r['mode'],r['N']):r for r in group}
        bs=sorted(cell(best,n,spectrum),key=lambda r:int(r['N']))
        ys=[f(lookup[b['best_fixed_mode'],b['N']],'relative_gap_median') for b in bs]
        envelope,=ax.plot(ns,ys,'--D',color='#568230',ms=4,label='Post hoc best fixed (absolute gap)')
        if len(handles)==5:handles.append(envelope)
        ax.axhline(1,color='#777777',ls=':',lw=.8)
        ax.set_xscale('log',base=4);ax.set_yscale('log');ax.grid(alpha=.16)
        ax.set_xticks(ns,[str(x) for x in ns],rotation=25,ha='right')
        ax.set_xlabel('Regression transitions N');ax.set_ylabel('Relative gap g(K)/g(K0)')
        ax.set_title(f'n=m={n}, {spectrum}; {fail_title(group)}')
    finish(fig,out,'adaptive_gaps',
        'Lines: full-32 failure-inclusive medians; bands: IQR. Sensitivities are not selected using outcomes.\n'
        'Post hoc order is a group diagnostic, chosen using absolute gap; plotted values are relative gaps. All arm × N cells: 0/32 failures.',handles)

    fig,axes=plt.subplots(2,2,figsize=(14,10))
    fig.suptitle('CE: chosen order grows with sample size',y=.99,fontsize=16)
    fig.subplots_adjust(left=.07,right=.98,top=.83,bottom=.12,hspace=.38,wspace=.24)
    handles=[]
    for ax,(n,spectrum) in zip(axes.flat,CELLS):
        group=cell(orders,n,spectrum);ns=budgets(group)
        for mode,color in zip(RULES[1:],COLOR[1:]):
            rs=sorted([r for r in group if r['mode']==mode],key=lambda r:int(r['N']))
            line,=ax.plot(ns,[f(r,'k_median') for r in rs],'-o',color=color,label=label(mode),ms=4)
            ax.fill_between(ns,[f(r,'k_q25') for r in rs],[f(r,'k_q75') for r in rs],color=color,alpha=.13)
            if len(handles)<4:handles.append(line)
        bs=sorted(cell(best,n,spectrum),key=lambda r:int(r['N']))
        line,=ax.plot(ns,[f(r,'best_fixed_k') for r in bs],'--D',color='#568230',label='Post hoc best fixed',ms=4)
        if len(handles)==4:handles.append(line)
        ax.axhline(int(n),color='#777777',ls=':',lw=.8)
        ax.set_xscale('log',base=4);ax.set_ylim(-1,int(n)+2);ax.grid(alpha=.16)
        ax.set_xticks(ns,[str(x) for x in ns],rotation=25,ha='right')
        ax.set_xlabel('Regression transitions N');ax.set_ylabel('Retained order k')
        ax.set_title(f'n=m={n}, {spectrum}; paper rule first N: k=0 in 32/32')
    finish(fig,out,'adaptive_orders',
        'Lines/bands: chosen-order medians/IQR; k=0 is a valid threshold outcome. Dotted line: dense order n.\n'
        'Post hoc fixed order includes dense and is not available to the learner. All plotted rules have 0/32 policy failures at each N.',handles)

    fig,axes=plt.subplots(2,2,figsize=(15,13))
    fig.suptitle('CE: paired dense / arm gap ratios, every registered arm',y=.985,fontsize=16)
    fig.subplots_adjust(left=.15,right=.89,top=.92,bottom=.09,hspace=.30,wspace=.45)
    for ax,(n,spectrum) in zip(axes.flat,CELLS):
        group=cell(ratios,n,spectrum);group=[r for r in group if r['ratio_kind']=='failure_inclusive']
        ns=budgets(group);modes=mode_order(group);lookup={(r['mode'],int(r['N'])):r for r in group}
        data=[[f(lookup[m,N],'paired_ratio_median') for N in ns] for m in modes]
        image=ax.imshow(data,norm=LogNorm(vmin=.1,vmax=10),cmap='RdBu',aspect='auto')
        ax.set_xticks(range(len(ns)),[str(N) for N in ns],rotation=25,ha='right')
        ax.set_yticks(range(len(modes)),[label(m) for m in modes],fontsize=9)
        ax.set_xlabel('Regression transitions N');ax.set_title(f'n=m={n}, {spectrum}; every pair stable (32/32)')
        for i,m in enumerate(modes):
            for j,N in enumerate(ns):
                v=f(lookup[m,N],'paired_ratio_median')
                ax.text(j,i,f'{v:.2g}',ha='center',va='center',fontsize=8,color='white' if v<.3 or v>3 else '#111111')
    cax=fig.add_axes([.92,.18,.015,.64]);fig.colorbar(image,cax=cax,label='Paired ratio median; >1 favors truncation')
    finish(fig,out,'paired_ratios',
        'Full-32 paired medians, not ratios of group medians. Both-stable and failure-inclusive versions coincide here.\n'
        'CSV retains 95% bootstrap intervals, both-failed exclusions and empty-draw counts. Colors saturate outside [0.1, 10].')

    fig,axes=plt.subplots(2,2,figsize=(15,12))
    fig.suptitle('CE: registered log-gap versus log-N slopes',y=.99,fontsize=16)
    fig.subplots_adjust(left=.15,right=.98,top=.90,bottom=.10,hspace=.31,wspace=.48)
    for ax,(n,spectrum) in zip(axes.flat,CELLS):
        group=cell(slopes,n,spectrum);group=[r for r in group if r['metric']=='relative_gap']
        modes=mode_order(group)
        for window,offset,color,marker in [('all_six',-.13,'#157f82','o'),('last_three',.13,'#ba423d','s')]:
            lookup={r['mode']:r for r in group if r['window']==window}
            for i,m in enumerate(modes):
                r=lookup[m];v=f(r,'log_gap_log_N_slope')
                if not math.isfinite(v):ax.text(0,i+offset,'NA');continue
                lo=f(r,'bootstrap_ci_low');hi=f(r,'bootstrap_ci_high')
                # A bootstrap interval need not bracket the point estimate. Draw it directly.
                ax.hlines(i+offset,lo,hi,color=color,lw=1.5)
                ax.plot(v,i+offset,marker,color=color,ms=4)
        ax.axvline(-1,color='#333333',ls='--',lw=1);ax.axvline(0,color='#777777',ls=':',lw=.8)
        ax.set_yticks(range(len(modes)),[label(m) for m in modes],fontsize=9)
        ax.invert_yaxis();ax.set_xlim(-1.35,.12);ax.grid(axis='x',alpha=.18)
        ax.set_xlabel('Slope of full-32 median relative gap')
        unidentified=sum(int(r['bootstrap_unidentified']) for r in group)
        ax.set_title(f'n=m={n}, {spectrum}; unidentified draws={unidentified}')
    finish(fig,out,'log_slopes',
        'Teal circles: all six budgets; red squares: last three. Horizontal bars: saved 95% cluster-bootstrap intervals.\n'
        'Intervals condition on finite-positive medians; unidentified mass is reported. Fixed-order bias floors need not have slope −1.')
    names=['fixed_orders','adaptive_gaps','adaptive_orders','paired_ratios','log_slopes']
    result={'status':'RENDERED_SAVED_CSV_ONLY','source_csv_sha256':proof['files'],
        'script_sha256':sha(Path(__file__)), 'matplotlib_version':matplotlib.__version__,
        'new_scientific_calculations':False,'cache_and_temp':str(runtime),
        'figures':{p.name:sha(p) for name in names for p in [out/(name+'.png'),out/(name+'.svg')]}}
    (out/'PLOT_MANIFEST.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
