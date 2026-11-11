"""Audit/report equal-mode CE with frozen rank-specific budget grids."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from threadpoolctl import threadpool_limits
import rank_sweep100 as e
import ce500_matched_gap as run
import ce500_equal_modes as family
from ce_matched_initial_gap import performance_gap
from ce500_report import write_csv,wilson,threshold,boot_interval,finite,plots


def audit_shard(cfg,shard):
    out=Path(cfg['output']);plan=e.read(out/'formal_plan.json');ident=family.identity(cfg)
    seeds=cfg['confirm_seeds'][5*shard:5*(shard+1)];assert len(seeds)==5
    destination=out/'audit-shards'/f'shard-{shard:02d}.json'
    if destination.exists():
        saved=e.read(destination)
        assert saved['identity']==ident and saved['formal_plan_sha256']==e.sha(out/'formal_plan.json')
        assert saved['report_source_sha256']==e.sha(Path(__file__))
        assert all(e.sha(out/k)==v for k,v in saved['sources_sha256'].items())
        print(json.dumps(dict(status='reused_verified',shard=shard)),flush=True);return
    hashes={};checked=0;fit_count=0;full_pairs=0;gap_error=0.;fit_error=0.;began=time.monotonic()
    for rank in cfg['ranks']:
        s=run.load_system(cfg,rank);budgets=plan['budgets_by_rank'][str(rank)]
        for seed in seeds:
            stem=f'ce-r{rank:03d}-s{seed:04d}';rp=out/'raw'/(stem+'.json');raw=e.read(rp)
            assert raw['identity']==ident and raw['budgets']==budgets
            hashes[str(rp.relative_to(out))]=e.sha(rp)
            for budget in budgets:
                pair=[q for q in raw['records'] if q['ols_samples']==budget]
                assert [q['method'] for q in pair]==['dense','truncated']
                pp=out/pair[0]['policy_file'];assert e.sha(pp)==pair[0]['policy_sha256']==pair[1]['policy_sha256']
                hashes[str(pp.relative_to(out))]=e.sha(pp)
                with np.load(pp,allow_pickle=False) as arr:
                    ks=[arr['shared'].copy()]*2 if rank==cfg['n'] else [arr[k].copy() for k in ('dense','truncated')]
                if rank==cfg['n']:
                    np.testing.assert_array_equal(*ks)
                    assert {k:v for k,v in pair[0].items() if k!='method'}=={k:v for k,v in pair[1].items() if k!='method'}
                    full_pairs+=1
                for j,(row,k) in enumerate(zip(pair,ks)):
                    if rank==cfg['n'] and j:continue
                    gap,rho,_=performance_gap(s,k) if np.isfinite(k).all() else (np.inf,np.inf,None)
                    assert bool(np.isfinite(gap))==row['stable']
                    if row['stable']:
                        err=abs(gap-row['gap']);gap_error=max(gap_error,err);assert err<2e-8
                    checked+=1
            cp=out/'checkpoints'/(stem+'.npz');fit=out/'estimates'/(stem+'.npz')
            hashes[str(cp.relative_to(out))]=e.sha(cp);hashes[str(fit.relative_to(out))]=e.sha(fit)
            with np.load(cp,allow_pickle=False) as arr:
                theta=run.cho_solve(run.cho_factor((arr['gram']+arr['gram'].T)/2),arr['cross'].T).T
            with np.load(fit,allow_pickle=False) as arr:
                err=float(np.max(abs(theta-np.concatenate((arr['Ahat'],arr['Bhat']),axis=1))))
            fit_error=max(fit_error,err);assert err<2e-11;fit_count+=1
            print(json.dumps(dict(shard=shard,audited_rank=rank,seed=seed,seconds=time.monotonic()-began)),flush=True)
    result=dict(status='PASS',shard=shard,seeds=seeds,identity=ident,
                formal_plan_sha256=e.sha(out/'formal_plan.json'),report_source_sha256=e.sha(Path(__file__)),
                unique_policies_reevaluated=checked,final_joint_OLS_recomputed=fit_count,
                full_rank_paired_budget_checks=full_pairs,maximum_performance_identity_gap_error=gap_error,
                maximum_OLS_fit_replay_error=fit_error,sources_sha256=hashes,
                seconds=time.monotonic()-began,slurm_job_id=os.environ['SLURM_JOB_ID'])
    e.atomic_json(destination,result);print(json.dumps(dict(status='PASS',shard=shard,policies=checked)),flush=True)


def report(cfg,phase,full_audit):
    out=Path(cfg['output']);dest=out/f'report-{phase}';dest.mkdir(parents=True,exist_ok=True)
    ident=family.identity(cfg);seeds=cfg[phase+'_seeds'];count=len(seeds)
    plan=e.read(out/'formal_plan.json') if phase=='confirm' else None
    shard_proofs=[];preverified={}
    if phase=='confirm' and not full_audit:
        for shard in range(6):
            proof=e.read(out/'audit-shards'/f'shard-{shard:02d}.json')
            assert proof['status']=='PASS' and proof['identity']==ident
            assert proof['formal_plan_sha256']==e.sha(out/'formal_plan.json')
            assert proof['report_source_sha256']==e.sha(Path(__file__))
            shard_proofs.append(proof)
            for rel,digest in proof['sources_sha256'].items():
                assert rel not in preverified;preverified[rel]=digest
        covered=[s for proof in shard_proofs for s in proof['seeds']]
        assert sorted(covered)==sorted(seeds) and len(covered)==len(set(covered))
    grids={r:([v+cfg['burn'] for v in plan['budgets_by_rank'][str(r)]] if plan else
              [v+cfg['burn'] for v in cfg['pilot_budgets']]) for r in cfg['ranks']}
    allrows=[];data={};hashes={};physical=0;checked=0;full_pairs=0;fit_count=0
    gap_error=0.;fit_error=0.;replay_error=0.;policy_diagnostics=[];began=time.monotonic()
    for rank in cfg['ranks']:
        s=run.load_system(cfg,rank);v=s['V'];u=s['U']
        for seed in seeds:
            stem=f'ce-r{rank:03d}-s{seed:04d}';raw_path=out/'raw'/(stem+'.json');raw=e.read(raw_path)
            assert raw['identity']==ident
            assert raw['physical_transitions']==max(grids[rank])
            assert raw['budgets']==[v-cfg['burn'] for v in grids[rank]]
            hashes[str(raw_path.relative_to(out))]=e.sha(raw_path);physical+=raw['physical_transitions']
            if preverified:assert hashes[str(raw_path.relative_to(out))]==preverified[str(raw_path.relative_to(out))]
            assert len(raw['records'])==2*len(grids[rank])
            for budget in grids[rank]:
                pair=[q for q in raw['records'] if q['transitions']==budget]
                assert [q['method'] for q in pair]==['dense','truncated']
                for key in ('A_error_fro2','ols_residual','ols_samples','actual_transitions','policy_file','policy_sha256'):
                    assert pair[0][key]==pair[1][key]
                pp=out/pair[0]['policy_file'];assert e.sha(pp)==pair[0]['policy_sha256']
                hashes[str(pp.relative_to(out))]=e.sha(pp)
                if preverified:assert hashes[str(pp.relative_to(out))]==preverified[str(pp.relative_to(out))]
                with np.load(pp,allow_pickle=False) as arr:
                    ks=[arr['shared'].copy()]*2 if rank==cfg['n'] else [arr[k].copy() for k in ('dense','truncated')]
                if rank==cfg['n']:
                    np.testing.assert_array_equal(*ks)
                    assert {k:z for k,z in pair[0].items() if k!='method'}=={k:z for k,z in pair[1].items() if k!='method'}
                    full_pairs+=1
                if full_audit or seed==seeds[0] or budget==grids[rank][-1]:
                    for j,(row,k) in enumerate(zip(pair,ks)):
                        if rank==cfg['n'] and j:continue
                        gap,rho,_=performance_gap(s,k) if np.isfinite(k).all() else (np.inf,np.inf,None)
                        assert bool(np.isfinite(gap))==row['stable']
                        if row['stable']:
                            err=abs(gap-row['gap']);gap_error=max(gap_error,err);assert err<2e-8,(rank,seed,budget,err)
                        checked+=1
                if phase=='confirm' and budget==cfg['common_diagnostic_OLS_samples']+cfg['burn']:
                    for row,k in zip(pair,ks):
                        if not row['stable']:continue
                        delta=k-s['Kstar'];sv=np.linalg.svd(delta,compute_uv=False)
                        fro2=float(np.sum(delta**2));op2=float(sv[0]**2)
                        ksv=np.linalg.svd(k,compute_uv=False)
                        kr=int(np.count_nonzero(ksv>1e-10));dr=int(np.count_nonzero(sv>1e-10))
                        if row['method']=='truncated':assert kr<=rank and dr<=min(cfg['n'],2*rank)
                        active=np.sum((v[:,:rank].T@delta)**2,axis=1)
                        special_row=float(np.sum((v[:,0]@delta)**2))
                        special_col=float(np.sum((delta@u[:,0])**2))
                        overlap=float(v[:,0]@delta@u[:,0])**2
                        policy_diagnostics.append(dict(rank=rank,seed=seed,method=row['method'],transitions=budget,
                            K_rank=kr,deltaK_rank=dr,deltaK_op2=op2,deltaK_fro2=fro2,
                            effective_rank=fro2/op2,spectral_shape=fro2/(rank*op2),gap=row['gap'],
                            gap_over_fro2=row['gap']/fro2,active_row_energy_sum=float(active.sum()),
                            active_row_energy_min=float(active.min()),active_row_energy_max=float(active.max()),
                            first_active_over_average=float(active[0]/active.mean()),
                            first_mode_row_or_column_energy=special_row+special_col-overlap))
                allrows+=pair
            with np.load(out/'checkpoints'/(stem+'.npz'),allow_pickle=False) as arr:
                theta=run.cho_solve(run.cho_factor((arr['gram']+arr['gram'].T)/2),arr['cross'].T).T
            if preverified:
                for rel in ('checkpoints/'+stem+'.npz','estimates/'+stem+'.npz'):
                    assert e.sha(out/rel)==preverified[rel]
            with np.load(out/'estimates'/(stem+'.npz'),allow_pickle=False) as arr:
                saved=np.concatenate((arr['Ahat'],arr['Bhat']),axis=1)
            err=float(np.max(abs(theta-saved)));fit_error=max(fit_error,err);assert err<2e-11;fit_count+=1
            if seed==seeds[0]:
                with np.load(out/raw['records'][-1]['policy_file'],allow_pickle=False) as arr:
                    for method in ('dense','truncated'):
                        bfit=run.e.corrected(theta[:,cfg['n']:],method,rank)
                        # Independently reconstruct full-rank SVD for the identity control.
                        if rank==cfg['n'] and method=='truncated':bfit=e.trunc(theta[:,cfg['n']:],rank)
                        expected=arr['shared' if rank==cfg['n'] else method]
                        try:
                            k,_=e.dare(theta[:,:cfg['n']],bfit,s['Q'],s['R'])
                        except (ValueError,np.linalg.LinAlgError):
                            saved_row=next(q for q in raw['records'] if q['method']==method and q['transitions']==grids[rank][-1])
                            assert saved_row['failure']=='riccati_failure' and not np.isfinite(expected).all()
                            continue
                        err=float(np.max(abs(k-expected)));replay_error=max(replay_error,err);assert err<2e-10
            for method in ('dense','truncated'):
                data[rank,method,seed]=[next(q for q in raw['records'] if q['transitions']==b and q['method']==method) for b in grids[rank]]
            print(json.dumps(dict(audited_rank=rank,seed=seed,seconds=time.monotonic()-began)),flush=True)
    indices=np.random.default_rng(cfg['bootstrap_seed']).integers(0,count,size=(cfg['bootstrap_replicates'],count))
    rates=[];requirements=[];gap_arrays={};boot_n={};fixed=[]
    for rank in cfg['ranks']:
        budgets=grids[rank]
        for method in ('dense','truncated'):
            records=[data[rank,method,seed] for seed in seeds]
            gap=np.array([[q['gap'] if q['stable'] else np.inf for q in group] for group in records]);gap_arrays[rank,method]=gap
            for target in cfg['relative_targets']:
                success=gap<=target*cfg['initial_gap'];n90=float(threshold(success,budgets))
                boot=threshold(success[indices],budgets);boot_n[rank,method,target]=boot;ci=boot_interval(boot)
                hit=budgets.index(n90) if np.isfinite(n90) else None;series=[]
                for j,budget in enumerate(budgets):
                    wins=int(success[:,j].sum());lo,hi=wilson(wins,count)
                    unstable=sum(q[j].get('failure')=='controller_instability' for q in records)
                    failures=sum(q[j].get('failure')=='riccati_failure' for q in records)
                    il,ih=wilson(unstable,count)
                    point=dict(rank=rank,method=method,relative_target=target,absolute_target=target,
                        transitions=budget,seeds=count,successes=wins,success_rate=wins/count,ci95_low=lo,ci95_high=hi,
                        instabilities=unstable,instability_ci95_low=il,instability_ci95_high=ih,numerical_failures=failures)
                    rates.append(point);series.append(point)
                chosen=series[hit] if hit is not None else series[-1]
                requirements.append(dict(rank=rank,method=method,relative_target=target,initial_gap=1.,seeds=count,
                    N_hat_90=finite(n90),status='reached' if hit is not None else 'not reached',
                    previous_tested_budget=budgets[hit-1] if hit is not None and hit else None,
                    bootstrap95_low=ci['low'],bootstrap95_high=ci['high'],
                    bootstrap_unreached_fraction=float(np.isinf(boot).mean()),
                    successes=chosen['successes'],success_ci95_low=chosen['ci95_low'],success_ci95_high=chosen['ci95_high'],
                    instabilities=chosen['instabilities'],instability_ci95_low=chosen['instability_ci95_low'],
                    instability_ci95_high=chosen['instability_ci95_high'],numerical_failures=chosen['numerical_failures'],
                    max_budget=max(budgets),endpoint_successes=int(success[:,-1].sum())))
    contrasts=[];fits=[];adjacent=[]
    for rank in cfg['ranks']:
        for j,budget in enumerate(grids[rank]):
            d=gap_arrays[rank,'dense'][:,j];t=gap_arrays[rank,'truncated'][:,j]
            f=gap_arrays[cfg['n'],'dense'][:,grids[cfg['n']].index(budget)] if budget in grids[cfg['n']] else None
            fixed.append(dict(rank=rank,transitions=budget,dense_gap_median=finite(np.median(d)),truncated_gap_median=finite(np.median(t)),
                dense_gap_q25=finite(np.quantile(d,.25)),dense_gap_q75=finite(np.quantile(d,.75)),
                truncated_gap_q25=finite(np.quantile(t,.25)),truncated_gap_q75=finite(np.quantile(t,.75)),
                full_dense_over_low_trunc=finite(np.median(f)/np.median(t)) if f is not None and np.isfinite(t).all() else None))
        for target in cfg['relative_targets']:
            baseline=next(q for q in requirements if q['rank']==cfg['n'] and q['method']=='dense' and q['relative_target']==target)
            selected=next(q for q in requirements if q['rank']==rank and q['method']=='truncated' and q['relative_target']==target)
            numer,denom=baseline['N_hat_90'],selected['N_hat_90']
            aa,bb=boot_n[cfg['n'],'dense',target],boot_n[rank,'truncated',target]
            valid=np.isfinite(aa)&np.isfinite(bb)
            ci=boot_interval(aa/bb) if valid.all() else dict(low=None,high=None)
            contrasts.append(dict(rank=rank,relative_target=target,full_rank_dense_N=numer,low_rank_truncated_N=denom,
                sample_saving_factor_full_over_low=numer/denom if numer and denom else None,
                bootstrap95_low=ci['low'],bootstrap95_high=ci['high'],bootstrap_valid_fraction=float(valid.mean())))
    for target in cfg['relative_targets']:
        focus=[next(q for q in contrasts if q['rank']==r and q['relative_target']==target) for r in (2,4,8,32)]
        if all(q['sample_saving_factor_full_over_low'] is not None for q in focus):
            x=np.array([cfg['n']/q['rank'] for q in focus]);y=np.array([q['sample_saving_factor_full_over_low'] for q in focus])
            alpha,lc=np.polyfit(np.log(x),np.log(y),1)
            fits.append(dict(relative_target=target,ranks=[2,4,8,32],zero_intercept_proportional_c=float(x@y/(x@x)),
                             power_fit_c=float(np.exp(lc)),power_fit_alpha=float(alpha)))
            for lo,hi in zip(focus[:-1],focus[1:]):
                adjacent.append(dict(relative_target=target,low_rank=lo['rank'],high_rank=hi['rank'],
                    gain_ratio=lo['sample_saving_factor_full_over_low']/hi['sample_saving_factor_full_over_low'],
                    inverse_rank_prediction=hi['rank']/lo['rank']))
    tables=[('sample_complexity',requirements),('success_by_budget',rates),('fixed_budget_gaps',fixed),
            ('low_rank_vs_full_rank',contrasts),('all_checkpoints',allrows),
            ('initial_systems',e.read(out/'verification.json')['systems'])]
    if policy_diagnostics:tables.append(('policy_spectral_diagnostics',policy_diagnostics))
    if adjacent:tables.append(('adjacent_gain_ratios',adjacent))
    for name,rows in tables:write_csv(dest/(name+'.csv'),rows)
    shard_count=sum(q['unique_policies_reevaluated'] for q in shard_proofs)
    if shard_proofs:
        expected=sum((1 if r==cfg['n'] else 2)*count*len(grids[r]) for r in cfg['ranks'])
        assert shard_count==expected
        gap_error=max(gap_error,max(q['maximum_performance_identity_gap_error'] for q in shard_proofs))
    audit=dict(status='PASS',phase=phase,paired_tasks=count*len(cfg['ranks']),unique_policies_reevaluated=shard_count or checked,
        additional_aggregate_policy_rechecks=checked if shard_proofs else 0,
        full_audit_shards=[q['slurm_job_id'] for q in shard_proofs],
        full_rank_paired_budget_checks=full_pairs,final_joint_OLS_recomputed=fit_count,
        maximum_performance_identity_gap_error=gap_error,maximum_OLS_fit_replay_error=fit_error,
        maximum_DARE_policy_replay_error=replay_error,physical_transitions=physical,algorithm_charged_transitions=2*physical,
        source_sha256=hashes,slurm_job_id=os.environ['SLURM_JOB_ID'])
    summary=dict(status='complete',phase=phase,seeds=seeds,dimension=cfg['n'],initial_gap=1.,
                 relative_targets=cfg['relative_targets'],budgets_by_rank=grids,requirements=requirements,
                 low_rank_vs_full_rank=contrasts,descriptive_gain_fits=fits,adjacent_gain_ratios=adjacent,audit=audit)
    e.atomic_json(dest/'audit.json',audit);e.atomic_json(dest/'summary.json',summary)
    plots(cfg,dest,requirements,rates,fixed)
    fig,axes=plt.subplots(1,2,figsize=(11,4.4),layout='constrained')
    for ax,target in zip(axes,cfg['relative_targets']):
        q=[r for r in contrasts if r['relative_target']==target and r['rank']!=cfg['n']]
        reached=any(r['sample_saving_factor_full_over_low'] is not None for r in q)
        if reached:
            ax.plot([r['rank'] for r in q],[r['sample_saving_factor_full_over_low'] or np.nan for r in q],'o-',label='Equal controlled modes')
        else:
            ax.text(.5,.5,'Full-rank baseline not reached\nSample-saving ratio censored',transform=ax.transAxes,ha='center')
        if q[0]['sample_saving_factor_full_over_low']:
            rr=np.geomspace(2,32,200);ax.plot(rr,q[0]['sample_saving_factor_full_over_low']*2/rr,'--',label='1/r reference, rank-2 anchored')
        ax.set(xscale='log',xlabel='Actuation rank',ylabel='Sample saving: full500 dense / rank-r trunc',title=f'Relative target {target:g}',xticks=[2,4,8,32],xlim=(1.8,36))
        if reached:ax.set_yscale('log');ax.legend(fontsize=8)
        ax.set_xticklabels([2,4,8,32])
    fig.suptitle('Replicated unstable controlled modes | initial gap=1')
    for ext in ('png','svg'):fig.savefig(dest/('sample_saving_vs_rank.'+ext),dpi=180)
    plt.close(fig)
    rows=''.join(f"<tr><td>{q['rank']}</td><td>{q['relative_target']}</td><td>{q['low_rank_truncated_N'] or 'not reached'}</td>"
                 f"<td>{q['full_rank_dense_N'] or 'not reached'}</td><td>{format(q['sample_saving_factor_full_over_low'],'.3f') if q['sample_saving_factor_full_over_low'] else 'not reached'}</td></tr>" for q in contrasts)
    content=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>CE500 等难度模态对照</title>
<style>body{{font:16px/1.6 system-ui;max-width:1200px;margin:30px auto;padding:0 20px}}img{{max-width:100%}}td,th{{padding:7px 12px;border:1px solid #ccd4dd}}table{{border-collapse:collapse}}</style>
<h1>CE500：每个新增受控模态具有相同标量 LQR 难度</h1>
<p>阶段：{phase}；每个 rank {count} seeds。A_r=0.45I+0.75U_rU_rᵀ，B_r=U_rV_rᵀ，Q=R=W=I。
每个受控模态均为1.2不稳定模态，Kstar 的非零奇异值全相同。初始 gap=1，relative targets .1/.05。
A 随 rank 改变，这是机制对照，不能单独证明旧现象只由一个不稳定模态造成。</p>
<p>完整 trajectory OLS，dense/truncated 共用 Ahat 和原始 Bhat，仅截断 Bhat。
全部 burn-in 计入预算。主收益=full500 dense 的 N90 / rank-r truncated 的 N90。</p>
<table><tr><th>Rank</th><th>Target</th><th>Truncated N90</th><th>Full dense N90</th><th>省样本倍数</th></tr>{rows}</table>
<img src="sample_saving_vs_rank.png"><img src="sample_complexity_vs_rank.png">
<img src="success_probability_vs_budget.png"><img src="absolute_relative_gap_convergence.png">
<p>至少90%是观察到的成功率。成功率区间为 Wilson 95%；30/30时下界约0.886，并非95%置信下界达到0.9。
首次达标已测预算不做插值；bootstrap 不消除网格分辨率误差。失败保留，未达标记为 not reached。
同 rank dense 可能受冻结预算上限删失。</p>
<p>低 rank 描述性拟合（2/4/8/32）：{json.dumps(fits,ensure_ascii=False)}。</p>
<p><a href="summary.json">汇总与拟合</a> · <a href="sample_complexity.csv">样本需求</a> ·
<a href="success_by_budget.csv">成功率</a> · <a href="audit.json">独立数值核查</a></p></html>'''
    (dest/'results.html').write_text(content,encoding='utf-8')
    copy=out/'frozen/scripts/ce500_equal_modes_report.py';copy.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(__file__,copy)
    print(json.dumps(dict(status='complete',phase=phase,contrasts=contrasts,fits=fits,
                          audit={k:v for k,v in audit.items() if k!='source_sha256'})),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['pilot','confirm','audit-shard']);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--full-audit',action='store_true');args=p.parse_args();assert os.environ.get('SLURM_JOB_ID')
    with threadpool_limits(1):
        if args.phase=='audit-shard':audit_shard(e.read(args.manifest),int(os.environ['SLURM_ARRAY_TASK_ID']))
        else:report(e.read(args.manifest),args.phase,args.full_audit)


if __name__=='__main__':main()
