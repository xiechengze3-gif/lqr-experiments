"""Presentation of saved nine-rung tables only. All gap columns retain failures."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import frozen_engine as e

BASE=Path('/scratch/user/changze/lqr_experiments/results/x12-20261106')
COLORS=dict(dense='#df773c',truncated='#287bb5')


def read(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:return list(csv.DictReader(stream))


def fmt(value):
    if value is None or value=='':return 'N/A'
    number=float(value)
    if math.isnan(number):return 'N/A'
    return '∞' if math.isinf(number) else f'{number:.5g}'


def cell(ax,rows,metric):
    rows=sorted(rows,key=lambda r:float(r['rung']))
    assert len(rows)==9 and all(int(float(r['full_pairs']))==32 for r in rows)
    x=np.array([float(r['primitive_per_arm']) for r in rows])/1e6
    finite=[float(r[f'{arm}_{metric}_{suffix}']) for r in rows for arm in COLORS
            for suffix in ['median','q25','q75'] if math.isfinite(float(r[f'{arm}_{metric}_{suffix}']))
            and float(r[f'{arm}_{metric}_{suffix}'])>0]
    bottom,top=(min(finite)/2,max(finite)*2.2) if finite else (.001,1.)
    for arm,color in COLORS.items():
        y,lo,hi=[np.array([float(r[f'{arm}_{metric}_{s}']) for r in rows]) for s in ['median','q25','q75']]
        valid=np.isfinite(y)&(y>0)
        ax.plot(x,np.where(valid,y,np.nan),'o-',color=color,label=arm,ms=3.5,lw=1.2)
        band=np.isfinite(lo)&np.isfinite(hi)&(lo>0)
        ax.fill_between(x,lo,hi,where=band,color=color,alpha=.12)
        for i,value in enumerate(y):
            if not math.isfinite(value):
                ax.plot(x[i],top/1.15,'^',color=color,ms=6)
                ax.annotate('∞',(x[i],top/1.15),xytext=(2,-8),textcoords='offset points',fontsize=7,color=color)
            elif value<=0:
                ax.plot(x[i],bottom*1.15,'v',color=color,ms=5)
                ax.annotate(fmt(value),(x[i],bottom*1.15),xytext=(2,3),textcoords='offset points',fontsize=7,color=color)
            elif math.isinf(hi[i]):
                ax.annotate('',(x[i],top/1.15),(x[i],value),arrowprops=dict(arrowstyle='->',color=color,lw=.7))
    ax.set_xscale('log',base=2);ax.set_yscale('log');ax.set_ylim(bottom,top)
    ax.set_xticks(x,[f'{v:.3g}' for v in x],rotation=25,fontsize=7)
    ax.set_xlabel('Primitive transitions per arm (millions)')
    ax.grid(alpha=.18)
    failure='  '.join(f"{32-int(float(r['dense_stable']))}/{32-int(float(r['truncated_stable']))}" for r in rows)
    ax.text(.02,.03,'Failure counts D/T, each /32 (left to right)\n'+failure,
        transform=ax.transAxes,fontsize=6.5,va='bottom',bbox=dict(facecolor='white',alpha=.8,edgecolor='none'))
    ax.set_title(f"{rows[0]['algorithm']}, n=m={int(float(rows[0]['n']))}")


def emit(fig,folder,name):
    paths=[]
    for extension in ['png','svg']:
        path=folder/(name+'.'+extension)
        assert not path.exists()
        fig.savefig(path,dpi=180,bbox_inches='tight')
        paths.append(path)
    plt.close(fig)
    return paths


def main(config_path):
    e.require_compute();directory=BASE/'report-v1'
    proof=json.loads((directory/'PRODUCTS_COMPLETE_v1.json').read_text(encoding='utf-8'))
    assert proof['status']=='MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED' and proof['config_sha256']==e.sha(config_path)
    for n,h in proof['files'].items():assert e.sha(directory/n)==h
    rows=read(directory/'summary_merged_nine_rungs.csv');primary=[r for r in rows if r['ratio_kind']=='failure_inclusive']
    assert len(rows)==180 and len(primary)==90
    figures=directory/'figures';assert not figures.exists();figures.mkdir()
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    generated=[]
    for metric,label in [('gap','Absolute gap'),('relative_gap','Gap / initial gap')]:
        fig,axes=plt.subplots(5,2,figsize=(12,15))
        for i,n in enumerate([24,36,48,60,72]):
            for j,alg in enumerate(['NPG','PI']):
                cell(axes[i,j],[r for r in primary if int(float(r['n']))==n and r['algorithm']==alg],metric)
                axes[i,j].set_ylabel(label)
                if i==0:axes[i,j].legend(fontsize=7)
        fig.suptitle('X12: n=m=60 added; all nine budgets and all 32 outputs retained per cell\n'
                     'Existing n=24,36,48,72 statistics reused byte-for-byte. Descriptive experiments.',fontsize=10)
        fig.tight_layout(rect=(0,0,1,.96));generated+=emit(fig,figures,'all_dimensions_'+metric)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,alg in zip(axes,['NPG','PI']):
        cell(ax,[r for r in primary if int(float(r['n']))==60 and r['algorithm']==alg],'gap')
        ax.set_ylabel('Absolute gap');ax.legend(fontsize=7)
    fig.suptitle('n=m=60; exact rank 2; all 32 outputs retained at every rung',fontsize=10)
    fig.tight_layout(rect=(0,0,1,.92));generated+=emit(fig,figures,'n60_main_gap')
    selected=[r for r in primary if int(float(r['n']))==60]
    derived=read(directory/'transitions_saved_derived.csv')
    lines=['# X12 saved-data report','',
       'Descriptive extension of the accepted X6b/X10b experiments to n=m=60. No theorem verification or epsilon/probability guarantee.','',
       'Family S, Q=R=W=I, exact rank B=2, retained rank k=2, K0=0, eta=.2, nu=1, H=16. '
       'NPG16/PI8 updates; 16 pulse burn blocks and one baseline block each update; fixed growing integer schedules. '
       'Every arm/rung has its own continuous state and paired external randomness. These are the frozen observation-only Stein NPG and PI learners; PI retains its registered joint compression and PSD regularization. '
       'No critic/LSTD, oracle input, line search, gain clipping, recovery or adaptive rank is introduced.','',
       'Pilot K0-only calibration selected N_cal=2097152 from the complete registered grid. '
       'This selection does not certify all-stage estimation errors or the sufficient theoretical constants. '
       'Every formal configuration was fixed before observations: 8 systems301..308 x4 seeds1701..1704, '
       'nine rungs1/256..1, two algorithms and both arms. All576paired paths/1152arms and193644738560formal transitions are retained.','',
       'Instability is absorbing and consumes its remaining registered budget under K0 padding. '
       'All gap medians/IQR use the full32 denominator with failures at infinity. Failure counts/rates appear at every plotted budget and in CSV. '
       'Both paired-ratio definitions, 5000 system-cluster bootstrap draws, undefined bootstrap mass, '
       'and all attainment/censoring diagnostics follow the unchanged original analyzer. '
       'Saved-stage estimator arrays, updates, padding counts and checkpoint hashes are audited on compute nodes.','',
       'summary.csv under new-n60 contains36new rows in the exact X6b schema. '
       'summary_merged_nine_rungs.csv contains180rows with the accepted144row X10b table as an exact byte prefix. '
       'The original8derived saving-factor rows, failures and per-cell counts are also exact prefixes of their merged copies. '
       'Old results are reused without simulation, bootstrap or reanalysis.','',
       '|algorithm|rung|M per arm|dense gap median|truncated gap median|dense stable|truncated stable|paired ratio [95% CI]|',
       '|---|---:|---:|---:|---:|---:|---:|---|']
    for r in sorted(selected,key=lambda r:(r['algorithm'],float(r['rung']))):
        lines.append('|'+ '|'.join([r['algorithm'],r['rung'],r['primitive_per_arm'],fmt(r['dense_gap_median']),
            fmt(r['truncated_gap_median']),r['dense_stable']+'/32',r['truncated_stable']+'/32',
            f"{fmt(r['paired_ratio_median'])} [{fmt(r['ci_low'])}, {fmt(r['ci_high'])}]"])+'|')
    lines+=['','|algorithm|n60 saving factor|left censored|right censored|unbracketed|',
            '|---|---:|---|---|---|']
    for r in derived:
        lines.append('|'+ '|'.join([r['algorithm'],fmt(r['factor']),r['left_censored'],r['right_censored'],r['unbracketed']])+'|')
    lines+=['','Factors use the verbatim paper cross function: first log-log crossing of the truncated full32 median '
        'curve with the dense full-rung median. No smoothing or extrapolation. Censoring and unidentified targets remain explicit.','',
        'The frozen cost gate uses max(measured n60 pilot body,historical larger-dimension floor), '
        'ceil((1.20*body+30)/60) task limits, all pilots, model-only prep and8SU report reserve. '
        'Actual-spend forecast<=230SU; requested upper<=300SU; total own concurrency<=64. '
        'Completed Slurm elapsed, forecast, requested reservations and AMS settlements are distinct; overlapping AMS and Slurm charges are never added.','',
        'No old result, release, paper source or TeX is edited. Full raw outputs, models, RNG receipts, sources and ledgers accompany the report.']
    report=directory/'SCIENCE_REPORT.md'
    with report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
    generated.append(report)
    result=dict(status='SAVED_CSV_FIGURES_TABLES_RENDERED',source_sha256=e.sha(__file__),config_sha256=e.sha(config_path),
                job=os.environ['SLURM_JOB_ID'],no_new_training_transitions=True,plot_gap_denominator='FULL32_FAILURE_INCLUSIVE',
                files={p.relative_to(directory).as_posix():e.sha(p) for p in generated})
    with (directory/'RENDER_COMPLETE_v1.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(status=result['status'],files=len(generated))),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);main(p.parse_args().config)
