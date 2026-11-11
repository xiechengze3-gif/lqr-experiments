"""One additional common central budget; unchanged estimator and logical seeds."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/project2-overnight-20261020'
OPS=BASE/'releases/project2-overnight-high-budget-v4'


def submit():
    assert json.loads((OUT/'completion.json').read_text())['audit']['status']=='PASS'
    assert not (OUT/'submission-high-budget.json').exists(),'Inspect existing receipt before replay'
    cfg=json.loads((OUT/'formal_plan.json').read_text())
    cfg['output']=str(OUT/'high-budget');cfg['mechanism_tasks']=cfg['mechanism_tasks'][:160]
    assert all(t['n']==50 and t['m']==50 and t['r']==4 and t['H']==16 and t['policy']=='Kstar' for t in cfg['mechanism_tasks'])
    for t in cfg['mechanism_tasks']:t['budgets']=[8192,32768,131072,524288]
    cfg['supplement']=dict(reason='Common central one-step PI comparison in its stable large-sample regime',
        existing_rows_retained=True,additional_N=524288,seed_coverage='all existing 4 systems x 40 trials',
        estimator_update_and_random_stream_unchanged=True,freeze_epoch=time.time())
    plan=OUT/'high_budget_plan.json';plan.write_text(json.dumps(cfg,indent=2)+'\n')
    receipt=dict(status='submitting',jobs={},tasks=160,bundles=14,
        additional_requested_SU_bound=14*5/60+.25,science='one extra common N; all smaller prefixes independently reproduced')
    path=OUT/'submission-high-budget.json';path.write_text(json.dumps(receipt,indent=2)+'\n')
    for key,mode,minutes,array,dep in [('array','bundle',5,'0-13%14',None),('report','report',15,None,'array')]:
        cmd=['sbatch','--parsable','-A','132685389143','-p','short','--exclude=c136,c294','-t',str(minutes),
             '-J','p2-night-high-'+key,'-o',str(OUT/'logs'/('high-'+key+'-%A_%a.out'))]
        if array:cmd+=['--array',array]
        if dep:cmd+=['--dependency','afterok:'+receipt['jobs'][dep]]
        cmd += [str(OPS/'slurm/project2_overnight_high_budget.sbatch'),mode]
        job=subprocess.check_output(cmd,cwd=OPS,universal_newlines=True).strip();assert job.isdigit(),job
        receipt['jobs'][key]=job;path.write_text(json.dumps(receipt,indent=2)+'\n')
    receipt['status']='submitted';path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


def report():
    sys.path[:0]=[str(BASE/'releases/project2-overnight-report-v3/scripts'),
        str(BASE/'releases/project2-overnight-20261020/scripts'),str(BASE/'releases/project2-overnight-20261020')]
    import numpy as np
    import project2_overnight_report as previous
    import project2_overnight as science
    science.require_compute()
    plan=OUT/'high_budget_plan.json'
    identity=science.sha(plan)+'|'+science.sha(science.__file__)
    data=[json.loads(p.read_text()) for p in sorted((OUT/'high-budget/mechanism').glob('task-*.json'))]
    assert len(data)==160 and {d['spec']['id'] for d in data}==set(range(160))
    def compare(a,b):
        assert type(a)==type(b) or (isinstance(a,(int,float)) and isinstance(b,(int,float)))
        if isinstance(a,dict):
            assert a.keys()==b.keys()
            for k in a:compare(a[k],b[k])
        elif isinstance(a,list):
            assert len(a)==len(b)
            for x,y in zip(a,b):compare(x,y)
        elif isinstance(a,(int,float)) and not isinstance(a,bool):
            np.testing.assert_allclose(a,b,rtol=5e-10,atol=5e-8)
        else:assert a==b
    rows=[];noise=[]
    for d in data:
        assert d['identity']==identity and len(d['rows'])==36 and len(d['noise'])==4
        old=json.loads((OUT/'mechanism'/f"task-{d['spec']['id']:04d}.json").read_text())
        compare(old['rows'],d['rows'][:27]);compare(old['noise'],d['noise'][:3])
        meta={k:v for k,v in d['spec'].items() if k!='budgets'}
        rows += [dict(meta,**r) for r in d['rows'][-9:]]
        noise += [dict(meta,**d['noise'][-1])]
    destination=OUT/'high-budget/report';destination.mkdir(parents=True,exist_ok=True)
    science.write_csv(destination/'one_step_outputs.csv',rows)
    science.write_csv(destination/'null_noise.csv',noise)
    keys=['n','m','r','H','policy','N','algorithm','method'];summaries=[]
    for key,rr in sorted(previous.groups(rows,keys).items()):
        summaries.append(dict(zip(keys,key),repetitions=len(rr),stable=sum(r['stable'] for r in rr),
            gap_q05=previous.q([r['gap'] for r in rr],.05),gap_q10=previous.q([r['gap'] for r in rr],.1),
            gap_median=previous.q([r['gap'] for r in rr],.5),gap_q90=previous.q([r['gap'] for r in rr],.9),
            Z_error_fro2_median=previous.q([r.get('Z_error_fro2') for r in rr],.5)))
    noise_summary={}
    for field in ('null_Z_fro2','null_normalized','known_cov_null_normalized','Gamma_effective_rank',
                  'null_to_conditional_mean','null_cross_to_conditional_mean','delta_variance'):
        noise_summary[field]={name:previous.q([r[field] for r in noise],prob)
            for name,prob in [('q05',.05),('q10',.1),('median',.5),('q90',.9)]}
    noise_summary['known_to_empirical_null_median']=previous.q([r['known_cov_null_fro2']/r['null_Z_fro2'] for r in noise],.5)
    science.write_csv(destination/'one_step_summary.csv',summaries)
    base=json.loads((OUT/'report/summary.json').read_text())
    one_summary=base['central_one_step']+summaries
    plt=previous.plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    colors={'dense':'#666666','known_rank':'#1676B5'}
    labels={'dense':'Dense','known_rank':'Rank-aware'}
    for ax,algorithm in zip(axes[0],('NPG','v4_PI')):
        for method in ('dense','known_rank'):
            selected=sorted([r for r in one_summary if r['algorithm']==algorithm and r['method']==method],key=lambda r:r['N'])
            xx=[r['N'] for r in selected]
            ax.plot(xx,[r['gap_median'] if r['gap_median'] is not None else np.nan for r in selected],'o-',color=colors[method],label=labels[method])
            ax.fill_between(xx,[r['gap_q10'] if r['gap_q10'] is not None else np.nan for r in selected],[r['gap_q90'] if r['gap_q90'] is not None else np.nan for r in selected],color=colors[method],alpha=.15)
        ax.set(xscale='log',yscale='log',xlabel='Evaluation blocks N',ylabel='One-step excess cost',title=algorithm+' at common Kstar')
        ax.legend()
    for method in ('dense','known_rank'):
        selected=sorted([r for r in one_summary if r['algorithm']=='v4_PI' and r['method']==method],key=lambda r:r['N'])
        axes[1,0].plot([r['N'] for r in selected],[r['stable']/r['repetitions'] for r in selected],'o-',color=colors[method],label=labels[method])
    axes[1,0].set(xscale='log',xlabel='Evaluation blocks N',ylabel='Stable fraction / 160',ylim=(-.05,1.05),title='PI stability across the full budget range')
    axes[1,0].legend()
    counts=[r['N'] for r in base['central_noise']]+[524288]
    empirical=[r['null_normalized_median'] for r in base['central_noise']]+[noise_summary['null_normalized']['median']]
    exact=[r['known_cov_null_normalized_median'] for r in base['central_noise']]+[noise_summary['known_cov_null_normalized']['median']]
    axes[1,1].plot(counts,empirical,'o-',label='Empirical Gram')
    axes[1,1].plot(counts,exact,'s--',label='Exact pulse-design covariance')
    axes[1,1].set(xscale='log',xlabel='Evaluation blocks N',ylabel='N * null error / [(m-r) H n^2]',title='Noise remains with known design covariance')
    axes[1,1].legend()
    for ax in axes.flat:ax.grid(alpha=.2)
    for suffix in ('png','svg'):fig.savefig(destination/('shared_data_one_step_extended.'+suffix),dpi=180)
    plt.close(fig)
    result=dict(status='complete',logical_tasks=160,additional_unique_one_step_outputs=len(rows),
        smaller_prefix_output_checks=160*27,smaller_prefix_noise_checks=160*3,
        physical_transitions=sum(d['physical_transitions'] for d in data),
        one_step_summary=summaries,null_noise_summary=noise_summary,
        source_science_hash=science.sha(science.__file__),manifest_hash=science.sha(plan),
        original_audit=json.loads((OUT/'audit/audit.json').read_text())['status'])
    science.atomic_json(destination/'summary.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['submit','report']);a=p.parse_args()
    if a.mode=='submit':submit()
    else:report()
