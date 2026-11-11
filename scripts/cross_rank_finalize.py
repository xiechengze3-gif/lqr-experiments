"""Supplementary dimension/collapse plots, exact references, and provenance audit."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dense_scaling import (require_compute,system,targets,evaluate,pi_gain,dare,trunc,atomic_json)
from dense_scaling import eta


def main(release, root):
    release, root = Path(release), Path(root)
    report=root/'report'; summary=json.loads((report/'summary.json').read_text())
    thresholds=summary['thresholds']; idx=json.loads((release/'configs/cross_rank_index.json').read_text())
    preview_path=root/'preview/pi_ce_fixed_precision.json'
    subset_thresholds_checked=0
    if preview_path.exists():
        subset=json.loads(preview_path.read_text())['thresholds']
        key=lambda t:(t['algorithm'],t['method'],t['n'],t['r'],t['tail'],t['epsilon'])
        full={key(t):t for t in thresholds}
        assert all(t==full[key(t)] for t in subset)
        subset_thresholds_checked=len(subset)
    lstd_hash=hashlib.sha256((release/'scripts/full_lstd.py').read_bytes()).hexdigest()
    engine_hash=hashlib.sha256(Path(system.__code__.co_filename).read_bytes()).hexdigest()
    failures=[]; audit=[]
    for profile in idx['profiles']:
        cfgpath=release/f'configs/cross_rank_{profile}.json';cfg=json.loads(cfgpath.read_text())
        manifesthash=hashlib.sha256(cfgpath.read_bytes()).hexdigest()
        expectedsource=release/'scripts'/('npg_rank_scaling.py' if profile.startswith('npg-') else 'pi_ce_rank.py')
        sourcehash=hashlib.sha256(expectedsource.read_bytes()).hexdigest()
        for tid,task in enumerate(cfg['tasks']):
            payload=json.loads((root/profile/'raw'/f'task-{tid:03d}.json').read_text())
            assert payload['manifest_sha256']==manifesthash and payload['source_sha256']==sourcehash
            assert payload['task']==task
            assert payload['engine_sha256']==engine_hash
            if not profile.startswith('npg-'):
                assert payload['lstd_sha256']==lstd_hash
            for method in ('raw','truncated'):
                rows=[r for r in payload['records'] if r['method']==method]
                for row in rows:
                    if profile=='ce': expected=row['N']+512
                    elif profile.startswith('npg-'):
                        expected=row['stage']*(cfg['burn']+(cfg['batch_schedule'][0]+1)*cfg['horizon'])
                    else: expected=row['stage']*(cfg['burn']+cfg['batch_schedule'][0])
                    assert row['transitions']==expected
                    if 'solver' in row:
                        assert row['solver']['coefficients']==(2*task['n'])*(2*task['n']+1)//2
                        assert row['solver']['samples']==row['N']
                    if 'solver' in row and row['solver']['converged']:
                        assert row['solver']['relative_residual']<=2*cfg['solver_rtol']
                actual=max(r['transitions'] for r in rows if r.get('observed',True))
                audit.append(dict(profile=profile,task_id=tid,method=method,
                    actual_transitions=actual,stable_output=rows[-1]['stable'],
                    rows=len(rows),solver_failures=sum(not r.get('solver',{}).get('converged',True) for r in rows)))
    colors={'raw':'#c44e52','truncated':'#4c72b0'}
    endpoints=list(csv.DictReader((report/'endpoints.csv').open()))
    costfits=[]
    for algo in ('CE','PI-LSTD','NPG'):
        for method in colors:
            candidates=[e for e in endpoints if e['algorithm']==algo and e['method']==method
                and float(e['tail'])==0 and int(e['r'])/int(e['n'])<=.2
                and int(e['N'])>=128*int(e['n'])]
            good=[]
            for e in candidates:
                group=[g for g in candidates if (g['n'],g['r'],g['N'])==(e['n'],e['r'],e['N'])]
                if len(group)==2 and all(g['eligible']=='True' and g['gap'] and float(g['gap'])>1e-12 for g in group):good.append(e)
            x=np.array([[1,np.log(int(e['n'])),np.log(int(e['r'])),-np.log(int(e['planned_transitions']))] for e in good])
            fit=dict(algorithm=algo,method=method,observations=len(good),
                interpretation='Descriptive total fixed-output gap, conditional stable complete paired groups; includes finite-iteration optimization residual for PI/NPG, not a statistical-error decomposition or sample-complexity proof.')
            if len(good)>=8 and np.linalg.matrix_rank(x)==4:
                y=np.log([float(e['gap']) for e in good]);coef=np.linalg.lstsq(x,y,rcond=None)[0]
                fit.update(C=float(np.exp(coef[0])),alpha_n=float(coef[1]),beta_r=float(coef[2]),gamma_M=float(coef[3]),
                    log_R2=float(1-np.sum((y-x@coef)**2)/max(np.sum((y-y.mean())**2),1e-30)))
            costfits.append(fit)
    atomic_json(report/'fixed_output_cost_fits.json',dict(fits=costfits,slurm_job_id=os.environ['SLURM_JOB_ID']))
    for algo,power in (('CE',1),('PI-LSTD',2),('NPG',2)):
        fig,axes=plt.subplots(2,3,figsize=(13,8),constrained_layout=True)
        for col,eps in enumerate((5.,2.,1.)):
            for method in colors:
                rows=sorted([t for t in thresholds if t['algorithm']==algo and t['method']==method and t['tail']==0 and t['r']==4 and t['epsilon']==eps],key=lambda t:t['n'])
                good=[t for t in rows if t['budget']]
                for row,normalized in ((0,False),(1,True)):
                    ax=axes[row,col]
                    for t in rows:
                        budget=t['budget'] or t['lower_budget']
                        value=budget/(t['r']*t['n']**power) if normalized else budget
                        marker={'attained':'o','left_censored':'v','right_censored':'^'}[t['status']]
                        ax.scatter(t['n'],value,color=colors[method],marker=marker)
                    ax.plot([t['n'] for t in good],[t['budget']/(t['r']*t['n']**power) if normalized else t['budget'] for t in good],color=colors[method],label=method)
                    ax.set(xscale='log',yscale='log',xlabel='Dimension n (r=4)',ylabel=f'M / (r n^{power})' if normalized else 'Primitive transitions',title=f'{algo}, gap <= {eps:g}')
                    ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.suptitle('Fixed-output minimum tested budget; down/up markers = left/right censored')
        fig.savefig(report/f'{algo.lower().replace("-","_")}_dimension_collapse.png',dpi=180)
        fig.savefig(report/f'{algo.lower().replace("-","_")}_dimension_collapse.pdf');plt.close(fig)
    # Exact PI convergence and CE truncation floor: references use zero samples.
    tasks=json.loads((release/'configs/cross_rank_ce.json').read_text())['tasks']
    reference=[]
    for task in tasks:
        s=system(task)
        for method in colors:
            k=s['K0'].copy()
            for stage in range(7):
                quality,p=evaluate(s,k)
                reference.append(dict(algorithm='PI-LSTD',method=method,stage=stage,
                    n=task['n'],r=task['r'],seed=task['system_seed'],tail=task['tail'],**quality))
                if not quality['stable']:break
                t=targets(s,k,16,p)
                k,_,_=pi_gain(s,t['G'],t['C'],None if method=='raw' else task['r'])
            b=s['B'] if method=='raw' else trunc(s['B'],task['r'])
            k,_=dare(s['A'],b,s['Q'],s['R']);quality,_=evaluate(s,k)
            reference.append(dict(algorithm='CE',method=method,stage=1,
                n=task['n'],r=task['r'],seed=task['system_seed'],tail=task['tail'],**quality))
            k=s['K0'].copy()
            for stage in range(81):
                quality,p=evaluate(s,k)
                reference.append(dict(algorithm='NPG',method=method,stage=stage,
                    n=task['n'],r=task['r'],seed=task['system_seed'],tail=task['tail'],**quality))
                if not quality['stable']:break
                t=targets(s,k,16,p)
                z=t['Z'] if method=='raw' else trunc(t['Z'],task['r'])
                k-=2*eta(s)*(s['R']@k+z)
    atomic_json(report/'pi_ce_exact_reference.json',dict(records=reference,
        interpretation='Zero-sample oracle diagnostics only; no learner or budget selection uses these references.',
        slurm_job_id=os.environ['SLURM_JOB_ID']))
    feasible=[]
    for algo,endstage in (('CE',1),('PI-LSTD',6),('NPG',80)):
        final=[r for r in reference if r['algorithm']==algo and r['stage']==endstage]
        for method in colors:
            for n,rank,tail in sorted(set((r['n'],r['r'],r['tail']) for r in final)):
                group=[r for r in final if r['method']==method and (r['n'],r['r'],r['tail'])==(n,rank,tail)]
                for eps in (5.,2.,1.,.5,.1):
                    feasible.append(dict(algorithm=algo,method=method,n=n,r=rank,tail=tail,epsilon=eps,
                        exact_fixed_output_max_gap=max(r['gap'] for r in group) if all(r['stable'] for r in group) else None,
                        exact_fixed_output_attains=all(r['stable'] and r['gap']<=eps for r in group)))
    atomic_json(report/'exact_output_feasibility.json',dict(records=feasible,
        interpretation='Exact reference feasibility at declared output iteration; it is a diagnostic, not a lower bound for every noisy policy sequence. NPG targets .5/.1 are secondary diagnostics and can be limited by the 80-iteration optimization residual.'))
    oracle={(r['method'],r['n'],r['r'],r['seed']):r['gap'] for r in reference
        if r['algorithm']=='NPG' and r['stage']==80 and r['tail']==0 and r['stable']}
    diagnostic=[]
    for method in colors:
        candidates=[e for e in endpoints if e['algorithm']=='NPG' and e['method']==method
            and float(e['tail'])==0 and int(e['r'])/int(e['n'])<=.2
            and int(e['N'])>=128*int(e['n'])]
        good=[];excluded=[]
        for key in sorted(set((e['n'],e['r'],e['N']) for e in candidates)):
            group=[e for e in candidates if (e['n'],e['r'],e['N'])==key]
            if len(group)!=2 or not all(e['eligible']=='True' for e in group):
                excluded.append(dict(cell=key,reason='incomplete_or_unstable_pair'));continue
            delta=float(np.mean([float(e['gap'])-oracle[(method,int(e['n']),int(e['r']),int(e['seed']))] for e in group]))
            if delta<=0:excluded.append(dict(cell=key,reason='nonpositive_signed_mean_difference'));continue
            good.append(dict(n=int(key[0]),r=int(key[1]),N=int(key[2]),M=int(group[0]['planned_transitions']),delta=delta))
        fit=dict(method=method,groups=len(good),included=good,excluded=excluded)
        if len(good)>=8:
            x=np.array([[1,np.log(e['n']),np.log(e['r']),-np.log(e['M'])] for e in good]);y=np.log([e['delta'] for e in good])
            if np.linalg.matrix_rank(x)==4:
                coef=np.linalg.lstsq(x,y,rcond=None)[0]
                fit.update(C=float(np.exp(coef[0])),alpha_n=float(coef[1]),beta_r=float(coef[2]),gamma_M=float(coef[3]),
                    log_R2=float(1-np.sum((y-x@coef)**2)/max(np.sum((y-y.mean())**2),1e-30)))
        diagnostic.append(fit)
    atomic_json(report/'npg_exact_subtracted_diagnostic.json',dict(fits=diagnostic,
        interpretation='Signed mean sampled-minus-matched-iteration exact cost. Different policy trajectories: not an additive statistical/optimization decomposition and not end-to-end complexity proof. Constant batch levels independently varied; same N>=128n window as total-cost fits; two systems; conditional positive stable groups only.'))
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    for col,n in enumerate((50,100)):
        for row,algo in enumerate(('PI-LSTD','NPG')):
            ax=axes[row,col]
            profile='pi-524288' if algo=='PI-LSTD' else 'npg-1048576'
            cfg=json.loads((release/f'configs/cross_rank_{profile}.json').read_text())
            ids=[i for i,t in enumerate(cfg['tasks']) if t['n']==n and t['r']==4 and t['tail']==0]
            for method in colors:
                records=[]
                for tid in ids:
                    payload=json.loads((root/profile/'raw'/f'task-{tid:03d}.json').read_text())
                    records += [r for r in payload['records'] if r['method']==method]
                stages=sorted(set(r['stage'] for r in records))
                good=[];values=[]
                for stage in stages:
                    group=[r for r in records if r['stage']==stage]
                    if len(group)==2 and all(r['stable'] and r.get('observed',True) for r in group):
                        good.append(stage);values.append(max(1e-12,float(np.mean([r['gap'] for r in group]))))
                ax.plot(good,values,color=colors[method],label=f'sampled {method}')
            exact=[r for r in reference if r['algorithm']==algo and r['method']=='raw' and r['n']==n and r['r']==4 and r['tail']==0]
            stages=sorted(set(r['stage'] for r in exact))
            ax.plot(stages,[max(1e-12,float(np.mean([r['gap'] for r in exact if r['stage']==stage]))) for stage in stages],color='#55a868',linestyle='--',label='exact critic (zero samples)')
            ax.set(yscale='log',xlabel='Outer iteration',ylabel='Mean absolute gap',title=f'{algo}, n={n}, r=4, largest tested batch')
            ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(report/'pi_npg_outer_comparison.png',dpi=180)
    fig.savefig(report/'pi_npg_outer_comparison.pdf');plt.close(fig)
    atomic_json(report/'numerical_audit.json',dict(pass_all=True,profiles=idx['profiles'],
        paired_tasks=len(idx['profiles'])*len(tasks),methods_checked=len(audit),records=audit,
        solver_failures=sum(a['solver_failures'] for a in audit),
        subset_thresholds_checked=subset_thresholds_checked,
        full_lstd_sha256=lstd_hash,engine_sha256=engine_hash,
        slurm_job_id=os.environ['SLURM_JOB_ID'],source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))


if __name__=='__main__':
    require_compute();p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();main(a.release,a.output)
