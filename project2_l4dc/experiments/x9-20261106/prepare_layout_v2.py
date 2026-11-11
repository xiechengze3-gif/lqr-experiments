"""Extract saved-CSV plot functions; change layout only, never rerun statistics."""
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    path=HERE/'render_report.py';text=path.read_text();tree=ast.parse(text)
    functions={n.name:ast.get_source_segment(text,n) for n in tree.body if isinstance(n,ast.FunctionDef)}
    imports='''"""X9 layout correction from verified saved CSV; no simulation or statistical recomputation."""
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
'''
    figure=functions['figure_cell']
    before="""ax.text(.02, .03, 'Failures dense/truncated, each /32\\n'+failed,
            transform=ax.transAxes, fontsize=6.8, va='bottom',
            bbox=dict(facecolor='white', alpha=.8, edgecolor='none'))"""
    after="""ax.text(0, -.28, 'Failures dense/truncated, each /32\\n'+failed,
            transform=ax.transAxes, fontsize=6.8, va='top')"""
    assert figure.count(before)==1;figure=figure.replace(before,after)
    assert figure.replace(after,before)==functions['figure_cell']
    helper=imports+'\n\n'+'\n\n'.join([functions['read'],functions['fmt'],figure,functions['emit']])+'\n\n'
    helper+='''def main():
    for key in ['TEMP','TMP','MPLCONFIGDIR','XDG_CACHE_HOME']:
        assert Path(os.environ[key]).drive.upper()=='E:' and Path(os.environ[key]).is_dir()
    meta=json.loads((INPUT/'PREVIEW_VERIFIED_v1.json').read_text())
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
        fig.suptitle('X9: full-population median/IQR, n=m=24, retained order 2\\n'
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
    with (ROOT/'PRESENTATION_v2.json').open('x') as stream:json.dump(proof,stream,indent=2)
    print(json.dumps({k:v for k,v in proof.items() if k!='files'}))


if __name__=='__main__':main()
'''
    ast.parse(helper)
    target=HERE/'presentation-v2';assert not target.exists();target.mkdir()
    with (target/'render_saved_csv.py').open('x',encoding='utf-8',newline='\n') as stream:stream.write(helper)
    proof=dict(status='LAYOUT_ONLY_SOURCE_EXTRACTED',original_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        new_source_sha256=hashlib.sha256((target/'render_saved_csv.py').read_bytes()).hexdigest(),
        numerical_figure_code_reversible_identical=True,read_and_emit_functions_literal_identical=True,
        source_only_no_numerical_imports=True,new_jobs=0,SU=0)
    with (target/'SOURCE_LAYOUT_PROOF_v2.json').open('x') as stream:json.dump(proof,stream,indent=2)
    print(json.dumps(proof))


if __name__=='__main__':main()
