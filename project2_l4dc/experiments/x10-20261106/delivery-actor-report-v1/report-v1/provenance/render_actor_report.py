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

BASE=Path('/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b')
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
    e.require_compute()
    directory=BASE/'report-v1'
    proof=json.loads((directory/'PRODUCTS_COMPLETE_v1.json').read_text())
    assert proof['status']=='MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED'
    assert proof['config_sha256']==e.sha(config_path)
    for name,digest in proof['files'].items():assert e.sha(directory/name)==digest
    rows=read(directory/'summary_merged_nine_rungs.csv')
    primary=[r for r in rows if r['ratio_kind']=='failure_inclusive']
    assert len(rows)==144 and len(primary)==72
    figures=directory/'figures';assert not figures.exists();figures.mkdir()
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    generated=[]
    for metric,label in [('gap','Absolute gap'),('relative_gap','Gap / initial gap')]:
        fig,axes=plt.subplots(4,2,figsize=(12,12))
        for i,n in enumerate([24,36,48,72]):
            for j,algorithm in enumerate(['NPG','PI']):
                selected=[r for r in primary if int(float(r['n']))==n and r['algorithm']==algorithm]
                cell(axes[i,j],selected,metric);axes[i,j].set_ylabel(label)
                if i==0:axes[i,j].legend(fontsize=7)
        fig.suptitle('X10b: nine registered rungs, full-population median/IQR\n'
                     'Original four rungs reused byte-for-byte; five added. Descriptive densification.',fontsize=10)
        fig.tight_layout(rect=(0,0,1,.95));generated+=emit(fig,figures,'all_dimensions_'+metric)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,algorithm in zip(axes,['NPG','PI']):
        cell(ax,[r for r in primary if int(float(r['n']))==72 and r['algorithm']==algorithm],'gap')
        ax.set_ylabel('Absolute gap');ax.legend(fontsize=7)
    fig.suptitle('n=m=72; exact rank 2; all 32 outputs retained at every rung',fontsize=10)
    fig.tight_layout(rect=(0,0,1,.92));generated+=emit(fig,figures,'n72_main_gap')
    derived=read(directory/'transitions_saved_derived.csv')
    four=read(directory/'transitions_saved_original_four_recomputed.csv')
    lines=['# X10b saved-data report','',
        'Descriptive densification of X6b. The five added rungs and all systems/seeds were fixed before the pilot. '
        'This report makes no new theorem verification or epsilon/probability claim.','',
        'Family S; n=m in 24,36,48,72; exact actuation rank 2; Q=R=W=I; K0=0; '
        'eta=.2, nu=1, H=16; 16 pulse burn blocks and one baseline block per stage; NPG16/PI8 updates. '
        'Original models, integer stage growth, N_cal, pairing and observation-only learners are preserved. '
        'One continuous trajectory per arm/rung. Instability is absorbing; remaining transitions are consumed by the registered K0 padding.','',
        'The original four-rung summary bytes are the exact prefix of summary_merged_nine_rungs.csv. '
        'The 80 new summary rows follow the unchanged original statistics and system-bootstrap draws. '
        'Only the report coverage assertion was generalized from four to the five registered new rungs; '
        'COVERAGE_SOURCE_PROOF_v1.json verifies the reversible one-line change and literal identity of all other functions.','',
        'Every gap median/IQR uses the full denominator 32, with failures at infinity. '
        'Both paired-ratio definitions and bootstrap undefined mass are retained in the summary. '
        'Figures show failure counts in left-to-right rung order; failure_counts_by_cell.csv gives counts and rates; '
        'failures.csv contains every saved baseline and new endpoint failure.','',
        '|n|algorithm|rung|M per arm|dense gap median|truncated gap median|dense stable|truncated stable|paired ratio [95% CI]|',
        '|---:|---|---:|---:|---:|---:|---:|---:|---|']
    for r in sorted(primary,key=lambda r:(float(r['n']),r['algorithm'],float(r['rung']))):
        lines.append('|'+ '|'.join([r['n'],r['algorithm'],r['rung'],r['primitive_per_arm'],
             fmt(r['dense_gap_median']),fmt(r['truncated_gap_median']),r['dense_stable']+'/32',r['truncated_stable']+'/32',
             f"{fmt(r['paired_ratio_median'])} [{fmt(r['ci_low'])}, {fmt(r['ci_high'])}]"])+'|')
    lines+=['','|n|algorithm|nine-rung saving factor|four-rung factor|left censored|right censored|unbracketed|',
            '|---:|---|---:|---:|---|---|---|']
    for r in derived:
        old=next(s for s in four if s['algorithm']==r['algorithm'] and float(s['n'])==float(r['n']))
        lines.append('|'+ '|'.join([r['n'],r['algorithm'],fmt(r['factor']),fmt(old['factor']),
                     r['left_censored'],r['right_censored'],r['unbracketed']])+'|')
    lines+=['','Saving factors use the verbatim paper cross function: first log-log crossing of the truncated '
        'full-population median curve with the dense full-rung median. No smoothing or extrapolation. '
        'Left censoring is an observed bound; missing targets or finite brackets remain flagged. '
        'The recomputed original four-rung values match every field of the captured paper CSV.','',
        'Budget/provenance files distinguish predicted actual spend, requested allocation upper bounds and completed '
        'Slurm elapsed cost. AMS settlement overlaps Slurm and is never added to it. '
        'The clarified gates are actual forecast <=160 SU and requested upper <=200 SU, including pilot and report.','',
        'The original pilot failed only because old remote reference arrays were missing (57s); its two timing jobs were dependency-canceled (0s). The explicitly authorized correction reused completed NPG without resampling and ran only PI replay plus the original untouched timing jobs. All strict record/array/RNG/count checks passed, with no changed learning source or tolerance. Both resource-v1 and resource-v2, original failures and cumulative requested/spent costs are retained in the full delivery.', '',
        'Formal and report consume packaged model/old CSV bytes verified against the local X6b-report-v1 delivery. No old remote X6b raw file is required. New complete-task outputs are copied incrementally to the E-drive delivery with file hashes; original sources/results are preserved.', '',
        'No existing results, releases, paper source or TeX were edited.']
    report=directory/'SCIENCE_REPORT.md'
    with report.open('x',encoding='utf-8') as stream:stream.write('\n'.join(lines)+'\n')
    generated.append(report)
    receipt=dict(status='SAVED_CSV_FIGURES_TABLES_RENDERED',source_sha256=e.sha(__file__),
        config_sha256=e.sha(config_path),job=os.environ['SLURM_JOB_ID'],no_new_training_transitions=True,
        plot_gap_denominator='FULL32_FAILURE_INCLUSIVE',
        files={p.relative_to(directory).as_posix():e.sha(p) for p in generated})
    with (directory/'RENDER_COMPLETE_v1.json').open('x') as stream:json.dump(receipt,stream,indent=2)
    print(json.dumps(dict(status=receipt['status'],files=len(generated))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True)
    main(p.parse_args().config)
