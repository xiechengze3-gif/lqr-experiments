"""CSV-only presentation v2:stable counts in every panel and honest censor marks.

Original frozen plot_saved_actor.py is preserved. No model loading, simulation,
policy evaluation, statistical recomputation, filtering or selection is added.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT.parents[3]/'.runtime/x6-20261101'
os.environ['MPLCONFIGDIR']=str(RUNTIME/'matplotlib')
os.environ['TMP']=os.environ['TEMP']=str(RUNTIME/'temp')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
for key in ['MPLCONFIGDIR','TMP']:
    directory=Path(os.environ[key]);assert directory.drive.upper()=='E:'
    directory.mkdir(parents=True,exist_ok=True)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(encoding='utf-8',newline='') as stream:
        rows=[]
        for original in csv.DictReader(stream):
            row={}
            for key,value in original.items():
                if value=='':row[key]=None
                else:
                    try:row[key]=float(value)
                    except ValueError:row[key]=value
            rows.append(row)
        return rows


def mark(ax,x,y,lo,hi,color,marker,label=None):
    bottom,top=ax.get_ylim()
    if y is None:return
    plotted=min(top/1.7,max(bottom*1.7,y))
    low=bottom*1.2 if lo is None or lo<=0 else max(bottom*1.2,lo)
    high=top/1.2 if hi is None or math.isinf(hi) else min(top/1.2,hi)
    ax.errorbar(x,plotted,yerr=[[max(0,plotted-low)],[max(0,high-plotted)]],
        color=color,marker=marker,capsize=2,linestyle='none',label=label,markersize=5)
    if math.isinf(y) or (hi is not None and math.isinf(hi)):
        ax.annotate('',xy=(x,top/1.08),xytext=(x,top/2.3),arrowprops=dict(arrowstyle='->',color=color))
    if y==0 or lo==0:
        ax.annotate('',xy=(x,bottom*1.08),xytext=(x,bottom*2.3),arrowprops=dict(arrowstyle='->',color=color))


def save(fig,path,manifest):
    for extension in ['png','svg']:
        target=path.with_suffix('.'+extension);fig.savefig(target,dpi=180,bbox_inches='tight')
        manifest[target.name]=sha(target)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    assert not a.out.exists() and a.out.drive.upper()=='E:';a.out.mkdir(parents=True)
    rows=read(a.report/'summary.csv');attainment=read(a.report/'attainment.csv')
    dimensions=sorted({int(r['n']) for r in rows});rungs=sorted({r['rung'] for r in rows})
    assert rungs==[1/64,1/16,1/4,1]
    labels={1/64:'1/64',1/16:'1/16',1/4:'1/4',1.:'1'}
    colors={'dense':'#c34e38','truncated':'#207aaf'};manifest={}
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,4,figsize=(16,7),layout='constrained')
    for i,alg in enumerate(['NPG','PI']):
        for j,rung in enumerate(rungs):
            ax=axes[i,j];selected=[r for r in rows if r['algorithm']==alg and r['rung']==rung]
            finite=[r[k] for r in selected for k in ['ci_low','ci_high','paired_ratio_median']
                    if r[k] is not None and r[k]>0 and math.isfinite(r[k])]
            ymax=max([1]+[(n-2)/4 for n in dimensions]+finite)*3
            ymin=min([1]+finite)/3
            ax.set_yscale('log');ax.set_ylim(max(1e-5,ymin),ymax)
            ax.axhline(1,color='0.65',lw=.8)
            ax.plot(dimensions,[(n-2)/4 for n in dimensions],color='0.6',ls=':',label='Structural factor (n-2)/4')
            for kind,color,marker,offset in [('both_stable','#207aaf','o',-.5),('failure_inclusive','#c34e38','s',.5)]:
                for k,n in enumerate(dimensions):
                    r=next(v for v in selected if v['n']==n and v['ratio_kind']==kind)
                    mark(ax,n+offset,r['paired_ratio_median'],r['ci_low'],r['ci_high'],color,marker,
                         kind.replace('_',' ') if k==0 else None)
            ticks=[]
            for n in dimensions:
                r=next(v for v in selected if v['n']==n)
                ticks.append(f'{n}\nD{int(r["dense_stable"])}/T{int(r["truncated_stable"])} of32')
            ax.set_xticks(dimensions,ticks);ax.set_xlim(min(dimensions)-5,max(dimensions)+5)
            ax.set_title(f'{alg}, base x {labels[rung]}');ax.grid(axis='y',alpha=.18)
            if j==0:ax.set_ylabel('Paired gap dense / truncated')
            if i==0 and j==0:ax.legend(fontsize=7,loc='best')
    fig.suptitle('X6b: paired terminal gaps;95% system-cluster bootstrap CI; arrows mark infinity/zero',fontsize=12)
    save(fig,a.out/'paired-ratio-vs-dimension',manifest)
    fig,axes=plt.subplots(2,len(dimensions),figsize=(4*len(dimensions),7),layout='constrained',squeeze=False)
    for i,alg in enumerate(['NPG','PI']):
        for j,n in enumerate(dimensions):
            ax=axes[i,j];cell=[r for r in rows if r['n']==n and r['algorithm']==alg and r['ratio_kind']=='both_stable']
            finite=[r[f'{arm}_relative_gap_{s}'] for r in cell for arm in colors for s in ['median','q25','q75']
                    if r[f'{arm}_relative_gap_{s}']>0 and math.isfinite(r[f'{arm}_relative_gap_{s}'])]
            ax.set_xscale('log');ax.set_yscale('log')
            ax.set_ylim(min([.05]+finite)/3,max([.1]+finite)*3)
            for arm,color in colors.items():
                for k,r in enumerate(sorted(cell,key=lambda v:v['primitive_per_arm'])):
                    mark(ax,r['primitive_per_arm'],r[arm+'_relative_gap_median'],
                         r[arm+'_relative_gap_q25'],r[arm+'_relative_gap_q75'],color,
                         'o' if arm=='dense' else 's',arm if k==0 else None)
            ax.axhline(.1,color='.5',ls=':',lw=.8);ax.axhline(.05,color='.7',ls=':',lw=.8)
            ordered=sorted(cell,key=lambda r:r['primitive_per_arm'])
            ax.set_xticks([r['primitive_per_arm'] for r in ordered],
                [f'{r["primitive_per_arm"]:.3g}\nD{int(r["dense_stable"])}/T{int(r["truncated_stable"])} of32' for r in ordered])
            ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            ax.tick_params(axis='x',labelsize=7)
            ax.set_xlim(ordered[0]['primitive_per_arm']*.8,ordered[-1]['primitive_per_arm']*1.3)
            ax.set_title(f'{alg}, n={n}');ax.set_xlabel('Primitive transitions per arm')
            if j==0:ax.set_ylabel('Relative gap, full32 median/IQR')
            if i==0 and j==0:ax.legend()
    fig.suptitle('Full32 failure-inclusive median/IQR; D/T stable counts at every observed budget',fontsize=11)
    save(fig,a.out/'relative-gap-vs-budget',manifest)
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for i,alg in enumerate(['NPG','PI']):
        for j,epsilon in enumerate([.1,.05]):
            ax=axes[i,j];cell=[r for r in attainment if r['algorithm']==alg and r['relative_epsilon']==epsilon]
            finite=[r[k] for r in cell for k in ['smallest_observed_budget','bootstrap_ci_low','bootstrap_ci_high']
                    if r[k] is not None and r[k]>0 and math.isfinite(r[k])]
            limits=[r['censored_above'] for r in cell if r['censored_above'] is not None]
            ax.set_yscale('log');ax.set_ylim(min(finite+limits)/2,max(finite+limits)*3)
            stable_counts={}
            for arm,color in colors.items():
                for k,n in enumerate(dimensions):
                    r=next(v for v in cell if v['n']==n and v['arm']==arm)
                    x=n+(-.5 if arm=='dense' else .5)
                    point=r['smallest_observed_budget'];censored=math.isinf(point)
                    reference=r['censored_above'] if censored else point
                    source=next(v for v in rows if v['n']==n and v['algorithm']==alg and
                                v['ratio_kind']=='both_stable' and v['primitive_per_arm']==reference)
                    stable_counts[n,arm]=int(source[arm+'_stable'])
                    if censored:
                        # A censor mark is at the actual largest tested budget,
                        # never at an invented shared finite terminal value.
                        ax.plot(x,reference,color=color,marker='^',markerfacecolor='none',
                                linestyle='none',label=arm if k==0 else None)
                        lo,hi=r['bootstrap_ci_low'],r['bootstrap_ci_high']
                        if lo is not None and math.isfinite(lo):
                            upper=hi if hi is not None and math.isfinite(hi) else reference
                            ax.vlines(x,lo,upper,color=color,lw=.8)
                        ax.annotate('',xy=(x,min(reference*2,ax.get_ylim()[1]/1.1)),
                            xytext=(x,reference),arrowprops=dict(arrowstyle='->',color=color))
                    else:
                        mark(ax,x,point,r['bootstrap_ci_low'],r['bootstrap_ci_high'],color,
                             'o' if arm=='dense' else 's',arm if k==0 else None)
            ax.set_xticks(dimensions,[f'{n}\nD{stable_counts[n,"dense"]}/T{stable_counts[n,"truncated"]} of32' for n in dimensions])
            ax.set_xlim(min(dimensions)-5,max(dimensions)+5)
            ax.set_title(f'{alg}, relative epsilon={epsilon}');ax.set_xlabel('n=m')
            if j==0:ax.set_ylabel('Smallest observed ladder budget (>=29/32)')
            if i==0 and j==0:ax.legend()
    fig.suptitle('Observed ladder only; >=29/32 criterion; arrows retain censoring, no interpolation\n'
        'D/T stable counts at each arm\'s selected rung (largest tested rung if unattained)',fontsize=10)
    save(fig,a.out/'observed-budget-to-epsilon',manifest)
    result=dict(status='CSV_ONLY_FIGURES',source_sha256=sha(Path(__file__)),
        inputs={name:sha(a.report/name) for name in ['summary.csv','attainment.csv']},figures=manifest)
    (a.out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
