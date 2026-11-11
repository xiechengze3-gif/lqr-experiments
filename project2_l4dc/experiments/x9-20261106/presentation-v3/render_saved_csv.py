"""X9 layout correction from verified saved CSV; no simulation or statistical recomputation."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
COLORS = dict(dense='#df773c', truncated='#287bb5')
ROOT=Path(__file__).resolve().parent
INPUT=ROOT.parent/'preview-report-v1'


def read(path):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))

def fmt(value):
    if value is None or value == '':
        return 'N/A'
    x = float(value)
    if math.isnan(x):
        return 'N/A'
    return '∞' if math.isinf(x) else f'{x:.5g}'

def figure_cell(ax, rows, metric):
    rows = sorted(rows, key=lambda r: float(r['alpha']))
    x = np.array([float(r['alpha']) for r in rows])
    positive = [float(r[f'{arm}_{metric}_{suffix}']) for r in rows
                for arm in COLORS for suffix in ['median', 'q25', 'q75']
                if math.isfinite(float(r[f'{arm}_{metric}_{suffix}']))
                and float(r[f'{arm}_{metric}_{suffix}']) > 0]
    bottom = min(positive)/2 if positive else .001
    top = max(positive)*2.2 if positive else 1.
    for arm, color in COLORS.items():
        y, lo, hi = [np.array([float(r[f'{arm}_{metric}_{suffix}']) for r in rows])
                     for suffix in ['median', 'q25', 'q75']]
        finite = np.isfinite(y) & (y > 0)
        plotted = np.where(finite, y, np.nan)
        ax.plot(x, plotted, 'o-', color=color, label=arm, ms=4)
        valid_band = np.isfinite(lo) & np.isfinite(hi) & (lo > 0)
        ax.fill_between(x, lo, hi, where=valid_band, color=color, alpha=.13)
        for i, value in enumerate(y):
            if not math.isfinite(value):
                ax.plot(x[i], top/1.15, '^', color=color, ms=6)
                ax.annotate('∞', (x[i], top/1.15), xytext=(3, -8), textcoords='offset points', color=color, fontsize=8)
            elif value <= 0:
                ax.plot(x[i], bottom*1.15, 'v', color=color, ms=6)
                ax.annotate(fmt(value), (x[i], bottom*1.15), xytext=(3, 3), textcoords='offset points', color=color, fontsize=8)
            if math.isfinite(value) and value > 0 and math.isinf(hi[i]):
                ax.annotate('', (x[i], top/1.15), (x[i], value), arrowprops=dict(arrowstyle='->', color=color, lw=.7))
    ax.set_yscale('log')
    ax.set_ylim(bottom, top)
    ax.set_xticks(x, [f'{v:g}' for v in x])
    ax.set_xlabel('alpha')
    ax.grid(alpha=.2)
    failed = '; '.join(f"{float(r['alpha']):g}: {32-int(float(r['dense_stable']))}/{32-int(float(r['truncated_stable']))}" for r in rows)
    ax.text(0, -.28, 'Failures dense/truncated, each /32\n'+failed,
            transform=ax.transAxes, fontsize=6.8, va='top')
    ax.set_title(rows[0]['algorithm']+f"; rung={float(rows[0]['rung']):g}; M={int(float(rows[0]['primitive_per_arm'])):,}", fontsize=9)

def emit(fig, directory, name):
    files = []
    for ext in ['png', 'svg']:
        path = directory/(name+'.'+ext)
        assert not path.exists()
        fig.savefig(path, dpi=170, bbox_inches='tight')
        files.append(path)
    plt.close(fig)
    return files

def main():
    for key in ['TEMP','TMP','MPLCONFIGDIR','XDG_CACHE_HOME']:
        assert Path(os.environ[key]).drive.upper()=='E:' and Path(os.environ[key]).is_dir()
    meta=json.loads((INPUT/'PREVIEW_VERIFIED_v1.json').read_text(encoding='utf-8'))
    assert meta['status']=='FROZEN_STATISTICS_RENDER_PREVIEW_ONLY'
    for ref in meta['files']:
        assert hashlib.sha256((INPUT/ref['path']).read_bytes()).hexdigest()==ref['sha256']
    summary=read(INPUT/'summary.csv');assert len(summary)==80
    rows=[r for r in summary if r['ratio_kind']=='failure_inclusive'];assert len(rows)==40
    folder=ROOT/'figures';assert not folder.exists();folder.mkdir()
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    products=[]
    rungs=[1/64,1/16,1/4,1.]
    for metric,label in [('gap','Absolute gap'),('relative_gap','Gap / initial gap')]:
        fig,axes=plt.subplots(4,2,figsize=(12,15))
        for i,rung in enumerate(rungs):
            for j,algorithm in enumerate(['NPG','PI']):
                selected=[r for r in rows if float(r['rung'])==rung and r['algorithm']==algorithm]
                assert len(selected)==5
                figure_cell(axes[i,j],selected,metric);axes[i,j].set_ylabel(label)
        handles,labels=axes[0,0].get_legend_handles_labels()
        fig.suptitle('X9: full-population median/IQR, n=m=24, retained order 2\n'
                     'alpha=0 reuses X6b; alpha=.4 is the large-tail control. Empirical scan outside certified theorem conditions.',fontsize=10,y=.995)
        fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.956),ncol=2,frameon=False)
        fig.tight_layout(rect=(0,0,1,.935),h_pad=3.2)
        products+=emit(fig,folder,'all_rungs_'+metric)
    fig,axes=plt.subplots(1,2,figsize=(12,5.4))
    for ax,algorithm in zip(axes,['NPG','PI']):
        figure_cell(ax,[r for r in rows if float(r['rung'])==1 and r['algorithm']==algorithm],'gap')
        ax.set_ylabel('Absolute gap')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.suptitle('Full-rung comparison; alpha=0 reused; all failures retained. Median/IQR over 8 systems × 4 seeds.',fontsize=10,y=.995)
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.94),ncol=2,frameon=False)
    fig.tight_layout(rect=(0,0,1,.87))
    products+=emit(fig,folder,'full_rung_gap')
    proof=dict(status='SAVED_CSV_LAYOUT_ONLY_RENDER_COMPLETE',
        summary_sha256=hashlib.sha256((INPUT/'summary.csv').read_bytes()).hexdigest(),
        original_render_proof_sha256=hashlib.sha256((INPUT/'RENDER_COMPLETE_v1.json').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        numerical_statistics_recomputed=False,new_training_transitions=0,Grace_SU=0,Slurm_job_id=None,
        changes='Only image geometry, failure-label position and one shared legend outside axes. Original y-values/IQR/failure/Infinity drawing code retained.',
        files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in products})
    with (ROOT/'PRESENTATION_v3.json').open('x') as stream:json.dump(proof,stream,indent=2)
    print(json.dumps({k:v for k,v in proof.items() if k!='files'}))


if __name__=='__main__':main()
