"""Independent checks, scientific summaries, and figures for the targeted round."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

RELEASE=Path('/scratch/user/changze/lqr_experiments/releases/project2-overnight-20261020')
sys.path[:0]=[str(RELEASE/'scripts'),str(RELEASE)]
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import project2_overnight as science


def q(values, probability):
    values=sorted(float(v) if v is not None and np.isfinite(v) else math.inf for v in values)
    if not values:return None
    result=values[max(0,min(len(values)-1,math.ceil(probability*len(values))-1))]
    return result if math.isfinite(result) else None


def groups(rows, keys):
    result={}
    for row in rows:
        key=tuple(row[k] for k in keys);result.setdefault(key,[]).append(row)
    return result


def summarize(out):
    cfg=json.loads((out/'formal_plan.json').read_text())
    identity=science.sha(out/'formal_plan.json')+'|'+science.sha(science.__file__)
    actors=[json.loads(p.read_text()) for p in sorted((out/'actor').glob('formal-*.json'))]
    mechanism=[json.loads(p.read_text()) for p in sorted((out/'mechanism').glob('task-*.json'))]
    assert len(actors)==72 and len(mechanism)==760,(len(actors),len(mechanism))
    assert {d['spec']['id'] for d in actors}==set(range(72))
    assert {d['spec']['id'] for d in mechanism}==set(range(760))
    assert all(d['identity']==identity for d in actors+mechanism)
    actor_rows=[];stage_rows=[];mechanism_rows=[];noise_rows=[]
    for d in actors:
        meta=d['spec'];last=d['rows'][-1]
        maximum=max((r.get('P_relative_max') or 0) for r in d['rows'])
        record=dict(meta,status=d['status'],seconds=d['seconds'],
            planned_transitions=d['planned_transitions'],actual_transitions=d['actual_transitions'],
            all_stages_in_region=bool(d['status']=='completed' and maximum<=2+1e-9),
            maximum_P_relative=maximum,success=bool(d['status']=='completed' and last['g']<=.1),
            final_gap=last['gap'],final_g=last['g'],final_stable=last['stable'])
        actor_rows.append(record)
        stage_rows += [dict(meta,**r) for r in d['rows']]
    for d in mechanism:
        meta={k:v for k,v in d['spec'].items() if k not in ('budgets',)}
        for row in d['rows']:
            enriched=dict(meta,**row)
            if row['gap'] is not None and row['algorithm'] in ('NPG','known_cov_NPG'):
                enriched['normalized_gap_noise_scale']=row['N']*row['gap']/(row['eta']**2*(meta['m']-meta['r'])*meta['H']*meta['n']**2)
            mechanism_rows.append(enriched)
        noise_rows += [dict(meta,**row) for row in d['noise']]
    report=out/'report';report.mkdir(exist_ok=True)
    for name,rows in [('actor_endpoints',actor_rows),('actor_stages',stage_rows),
                      ('one_step_outputs',mechanism_rows),('null_noise',noise_rows)]:
        science.write_csv(report/(name+'.csv'),rows)
    actor_summary=[]
    for key,rows in sorted(groups(actor_rows,['N','method']).items()):
        actor_summary.append(dict(N=key[0],method=key[1],repetitions=len(rows),
            transitions=rows[0]['planned_transitions'],stable=sum(r['final_stable'] for r in rows),
            success=sum(r['success'] for r in rows),g_q10=q([r['final_g'] for r in rows],.1),
            g_median=q([r['final_g'] for r in rows],.5),g_q90=q([r['final_g'] for r in rows],.9),
            all_stages_in_region=sum(r['all_stages_in_region'] for r in rows),
            statuses={status:sum(r['status']==status for r in rows) for status in sorted({r['status'] for r in rows})}))
    keys=['n','m','r','H','policy','N','algorithm','method'];one_summary=[]
    for key,rows in sorted(groups(mechanism_rows,keys).items()):
        result=dict(zip(keys,key));result.update(repetitions=len(rows),stable=sum(r['stable'] for r in rows),
            gap_q05=q([r['gap'] for r in rows],.05),gap_q10=q([r['gap'] for r in rows],.1),
            gap_median=q([r['gap'] for r in rows],.5),gap_q90=q([r['gap'] for r in rows],.9),
            Z_error_fro2_median=q([r.get('Z_error_fro2') for r in rows],.5))
        one_summary.append(result)
    keys=['n','m','r','H','policy','N'];noise_summary=[]
    for key,rows in sorted(groups(noise_rows,keys).items()):
        result=dict(zip(keys,key));result['repetitions']=len(rows)
        for field in ('null_Z_fro2','null_normalized','known_cov_null_normalized','Gamma_effective_rank',
                      'null_to_conditional_mean','null_cross_to_conditional_mean','delta_variance',
                      'Gram_population_relative_fro','gram_condition','Z_finite_H_bias_fro2'):
            for name,prob in [('q05',.05),('q10',.1),('median',.5),('q90',.9)]:
                result[field+'_'+name]=q([r[field] for r in rows],prob)
        result['known_to_empirical_null_median']=q([r['known_cov_null_fro2']/r['null_Z_fro2'] for r in rows],.5)
        result['threshold_coverage_fraction']=sum(r['threshold_covers_total'] for r in rows)/len(rows)
        noise_summary.append(result)
    for name,rows in [('actor_summary',actor_summary),('one_step_summary',one_summary),('null_noise_summary',noise_summary)]:
        science.write_csv(report/(name+'.csv'),rows)
    # Descriptive fits of the fixed-K noise; all points and failures stay in CSV.
    fits=[]
    center=lambda r:r['n']==50 and r['m']==50 and r['r']==4 and r['H']==16 and r['policy']=='Kstar'
    selected=[r for r in noise_summary if center(r)]
    fits.append(dict(label='central null MSE versus N',slope=float(np.polyfit(np.log([r['N'] for r in selected]),np.log([r['null_Z_fro2_median'] for r in selected]),1)[0])))
    selected=[r for r in noise_summary if r['n']==r['m'] and r['r']==4 and r['H']==16 and r['policy']=='Kstar' and r['N']==131072]
    fits.append(dict(label='null MSE versus (m-r)*n^2',slope=float(np.polyfit(np.log([(r['m']-r['r'])*r['n']**2 for r in selected]),np.log([r['null_Z_fro2_median'] for r in selected]),1)[0])))
    selected=[r for r in noise_summary if r['n']==50 and r['m']==50 and r['r']==4 and r['policy']=='Kstar' and r['N']==131072]
    fits.append(dict(label='central null MSE versus H',slope=float(np.polyfit(np.log([r['H'] for r in selected]),np.log([r['null_Z_fro2_median'] for r in selected]),1)[0])))
    paired=[]
    pairkeys=['n','m','r','H','policy','N','algorithm']
    for key,rows in sorted(groups(mechanism_rows,pairkeys).items()):
        dense={(r['seed'],r['trial']):r for r in rows if r['method']=='dense'}
        low={(r['seed'],r['trial']):r for r in rows if r['method']=='known_rank'}
        ratios=[dense[k]['gap']/low[k]['gap'] for k in dense.keys()&low.keys()
                if dense[k]['gap'] is not None and low[k]['gap'] is not None and low[k]['gap']>0]
        paired.append(dict(zip(pairkeys,key),finite_pairs=len(ratios),
            gap_ratio_q10=q(ratios,.1),gap_ratio_median=q(ratios,.5),gap_ratio_q90=q(ratios,.9)))
    science.write_csv(report/'paired_gap_ratios.csv',paired)
    summary=dict(status='complete',identity=identity,actor_summary=actor_summary,
        actor_trajectories=len(actors),mechanism_tasks=len(mechanism),one_step_outputs=len(mechanism_rows),
        null_noise_rows=len(noise_rows),noise_fits=fits,
        central_noise=[r for r in noise_summary if center(r)],
        central_one_step=[r for r in one_summary if center(r)],
        central_paired=[r for r in paired if center(r)],
        physical_transitions=dict(formal_actor=sum(d['actual_transitions'] for d in actors),
            formal_mechanism=sum(d['physical_transitions'] for d in mechanism)),
        formal_seconds=dict(actor=sum(d['seconds'] for d in actors),mechanism=sum(d['seconds'] for d in mechanism)))
    science.atomic_json(report/'summary.json',summary)
    return cfg,actor_rows,actor_summary,mechanism_rows,noise_rows,one_summary,noise_summary,summary


def independent_audit(out,cfg,actor_rows,summary):
    begin=time.monotonic();checks=[];replays=[];physical=0
    # Re-evaluate every terminal controller through the performance-difference identity.
    for row in actor_rows:
        spec=cfg['actor_tasks'][row['id']];s=science.make_system(spec)
        with np.load(out/'actor'/f"formal-{spec['id']:04d}.npz",allow_pickle=False) as a:k=a['K'].copy()
        f=s['A']-s['B']@k;radius=float(max(abs(np.linalg.eigvals(f))))
        stable=radius<1-1e-10
        assert stable==row['final_stable']
        if stable:
            sigma=solve_discrete_lyapunov(f,s['W'])
            fs=s['A']-s['B']@s['Kstar']
            pstar=solve_discrete_lyapunov(fs.T,s['Q']+s['Kstar'].T@s['R']@s['Kstar'])
            error=k-s['Kstar'];curvature=s['R']+s['B'].T@pstar@s['B']
            gap=float(np.trace(sigma@error.T@curvature@error))
            np.testing.assert_allclose(gap,row['final_gap'],rtol=2e-8,atol=2e-7)
        if row['method']=='known_rank':assert np.linalg.matrix_rank(k,tol=1e-9)<=row['r']
        assert row['actual_transitions']==row['N']*row['H']*max(0,len(json.loads((out/'actor'/f"formal-{spec['id']:04d}.json").read_text())['rows'])-1)+(row['burn']+row['H'])*max(0,len(json.loads((out/'actor'/f"formal-{spec['id']:04d}.json").read_text())['rows'])-1)
        checks.append(dict(id=row['id'],stable=stable,rank=int(np.linalg.matrix_rank(k,tol=1e-9))))
    # Recollect selected full logical tasks, independently solve their regression,
    # and verify null covariance/known covariance quantities against saved results.
    chosen=[0,160,200,280,400,520,680,720]
    for task_id in chosen:
        spec=cfg['mechanism_tasks'][task_id];s=science.make_system(spec)
        k=s['Kstar'] if spec['policy']=='Kstar' else s['K0']
        original=json.loads((out/'mechanism'/f'task-{task_id:04d}.json').read_text())
        null=np.linalg.svd(s['B'].T,full_matrices=True)[0][:,spec['r']:]
        cov=science.pulse_covariance(s,k,spec['H'])
        for index,data in enumerate(science.collect_prefixes(s,k,np.zeros(spec['n']),spec['budgets'],
            science.rng_for(2026102062,spec['n'],spec['m'],spec['r'],spec['seed'],spec['trial'],spec['H'],
                            0 if spec['policy']=='Kstar' else 1),spec['H'],spec['burn'])):
            z=np.linalg.solve(data['stats']['gram'],data['stats']['cross'].T).T
            np.testing.assert_allclose(z,data['Z'],rtol=2e-11,atol=2e-11)
            original_noise=original['noise'][index]
            current=float(np.sum((null.T@z)**2))
            np.testing.assert_allclose(current,original_noise['null_Z_fro2'],rtol=2e-10,atol=2e-10)
            knownz=(data['stats']['cross']/data['N'])@np.linalg.inv(cov)
            np.testing.assert_allclose(float(np.sum((null.T@knownz)**2)),original_noise['known_cov_null_fro2'],rtol=2e-10,atol=2e-10)
            if index==2:
                target=out/'audit/selected_raw';target.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(target/f'task-{task_id:04d}.npz',G=data['G'],Z=data['Z'],
                    Gram=data['stats']['gram'],cross=data['stats']['cross'],Gamma=data['Gamma'],
                    pulse_covariance=cov,**{key:s[key] for key in ('A','B','Q','R','K0','Kstar')})
            replays.append(dict(task=task_id,N=data['N'],null_fro2=current))
        physical+=original['physical_transitions']
    audit=dict(status='PASS',terminal_policies=len(checks),selected_tasks_recollected=len(chosen),
        independently_checked_prefixes=len(replays),audit_only_physical_transitions=physical,
        checks=['terminal performance identity','known-rank output rank','primitive transition ledger',
                'complete logical coverage and identity','independent linear solve',
                'same-seed null score replay','pulse-design covariance score replay'],
        seconds=time.monotonic()-begin,job=os.environ['SLURM_JOB_ID'])
    science.atomic_json(out/'audit/audit.json',audit)
    science.write_csv(out/'audit/terminal_checks.csv',checks)
    science.write_csv(out/'audit/selected_replays.csv',replays)
    return audit


def figures(out,actor_summary,one_summary,noise_rows,noise_summary):
    report=out/'report';plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    colors={'dense':'#666666','known_rank':'#1676B5','adaptive':'#D77B16'}
    labels={'dense':'Dense','known_rank':'Rank-aware','adaptive':'Adaptive'}
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.1),constrained_layout=True)
    for method in ('dense','known_rank','adaptive'):
        selected=sorted([r for r in actor_summary if r['method']==method],key=lambda r:r['transitions'])
        xx=[r['transitions']/1e6 for r in selected]
        yy=[r['g_median'] if r['g_median'] is not None else np.nan for r in selected]
        axes[0].plot(xx,yy,'o-',color=colors[method],label=labels[method])
        axes[1].plot(xx,[r['success']/r['repetitions'] for r in selected],'o-',color=colors[method],label=labels[method])
    axes[0].axhline(.1,color='black',ls='--',lw=1,label='Target')
    axes[0].set(xscale='log',yscale='log',xlabel='Primitive transitions (million)',ylabel='Final relative gap',title='v4 PI: full greedy step, six updates')
    axes[1].set(xscale='log',xlabel='Primitive transitions (million)',ylabel='Success fraction (all 8 systems)',ylim=(-.05,1.05),title='Entire-path stability and final gap <= 0.1')
    axes[0].legend();axes[1].legend()
    for ax in axes:ax.grid(alpha=.2)
    for suffix in ('png','svg'):fig.savefig(report/('v4_pi_full_run.'+suffix),dpi=180)
    plt.close(fig)
    center=lambda r:r['n']==50 and r['m']==50 and r['r']==4 and r['H']==16 and r['policy']=='Kstar'
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    for h in (4,8,16,32):
        selected=sorted([r for r in noise_summary if r['n']==50 and r['m']==50 and r['r']==4 and r['H']==h and r['policy']=='Kstar'],key=lambda r:r['N'])
        axes[0,0].plot([r['N'] for r in selected],[r['null_Z_fro2_median'] for r in selected],'o-',label='H='+str(h))
    axes[0,0].set(xscale='log',yscale='log',xlabel='Evaluation blocks N',ylabel='Null-space Z error squared',title='Same policy: batch and return horizon')
    axes[0,0].legend()
    selected=sorted([r for r in noise_summary if r['n']==r['m'] and r['r']==4 and r['H']==16 and r['policy']=='Kstar' and r['N']==131072],key=lambda r:r['n'])
    axes[0,1].plot([r['n'] for r in selected],[r['null_normalized_median'] for r in selected],'o-',label='Empirical Gram')
    axes[0,1].plot([r['n'] for r in selected],[r['known_cov_null_normalized_median'] for r in selected],'s--',label='Exact pulse-design covariance')
    axes[0,1].set(xlabel='State dimension n',ylabel='N * null error / [(m-r) H n^2]',title='Dimension-normalized null noise')
    axes[0,1].legend()
    selected=sorted([r for r in noise_summary if r['n']==30 and r['policy']=='Kstar' and r['N']==131072],key=lambda r:r['m'])
    axes[1,0].plot([r['m'] for r in selected],[r['null_Z_fro2_median']/(r['m']-r['r']) for r in selected],'o-')
    axes[1,0].set(xlabel='Action dimension m (n=30, r=4)',ylabel='Null error / (m-r)',title='Redundant-action noise per direction')
    for count in (8192,32768,131072):
        ratios=sorted(r['null_to_conditional_mean'] for r in noise_rows if center(r) and r['N']==count)
        axes[1,1].step(ratios,np.arange(1,len(ratios)+1)/len(ratios),where='post',label='N='+str(count))
    axes[1,1].axvline(1,color='black',ls='--',lw=1)
    axes[1,1].set(xlabel='Observed null error / conditional mean',ylabel='Empirical CDF',title='160 paired one-stage repetitions')
    axes[1,1].legend()
    for ax in axes.flat:ax.grid(alpha=.2)
    for suffix in ('png','svg'):fig.savefig(report/('null_noise_mechanism.'+suffix),dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.1),constrained_layout=True)
    for ax,algorithm in zip(axes,('NPG','v4_PI')):
        for method in ('dense','known_rank'):
            selected=sorted([r for r in one_summary if center(r) and r['algorithm']==algorithm and r['method']==method],key=lambda r:r['N'])
            xx=[r['N'] for r in selected]
            ax.plot(xx,[r['gap_median'] or np.nan for r in selected],'o-',color=colors[method],label=labels[method])
            ax.fill_between(xx,[r['gap_q10'] or np.nan for r in selected],[r['gap_q90'] or np.nan for r in selected],color=colors[method],alpha=.15)
        ax.set(xscale='log',yscale='log',xlabel='Evaluation blocks N',ylabel='One-step excess cost',title=algorithm+' at common Kstar')
        ax.legend();ax.grid(alpha=.2)
    for suffix in ('png','svg'):fig.savefig(report/('shared_data_one_step.'+suffix),dpi=180)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    science.require_compute();begin=time.monotonic()
    cfg,actor_rows,actor_summary,mechanism_rows,noise_rows,one_summary,noise_summary,summary=summarize(args.output)
    audit=independent_audit(args.output,cfg,actor_rows,summary)
    figures(args.output,actor_summary,one_summary,noise_rows,noise_summary)
    paths=sorted(p for p in args.output.rglob('*') if p.is_file() and p.suffix in ('.json','.csv','.npz','.png','.svg') and 'artifact_sha256' not in p.name and 'logs' not in p.parts)
    hashes={str(p.relative_to(args.output)):science.sha(p) for p in paths}
    science.atomic_json(args.output/'artifact_sha256.json',hashes)
    science.atomic_json(args.output/'completion.json',dict(status='complete',actor_trajectories=72,mechanism_tasks=760,
        one_step_outputs=summary['one_step_outputs'],audit=audit,report_seconds=time.monotonic()-begin,
        files=len(hashes),manifest_sha256=science.sha(args.output/'artifact_sha256.json'),job=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='complete',summary=summary,audit=audit)),flush=True)


if __name__=='__main__':main()
