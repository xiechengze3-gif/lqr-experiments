"""Independent local audit of saved PI critics, updates and true-system gaps."""
import argparse
import hashlib
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
import rank_sweep100 as e
from dense_scaling import pi_gain
from actuation_redundancy import diagnostics as loss_diagnostics
from rank_sweep100_report import csv_write


def audit(out,system_root):
    cfg=e.read(out/'resolved_config.json');ident=cfg['identity']
    for name,digest in ident['sources'].items():assert e.sha(e.ROOT/name)==digest,('Source identity differs',name)
    systems={};private={}
    for rank in cfg['ranks']:
        path=system_root/f'r{rank:03d}.npz';assert e.sha(path)==cfg['system_artifact_sha256'][str(rank)]
        with np.load(path,allow_pickle=False) as arrays:
            systems[rank]={key:(float(arrays[key]) if arrays[key].ndim==0 else arrays[key].copy())
                for key in ('A','B','Q','R','W','K0','Kstar','Jstar','initial_gap')}
            private[rank]=dict(Beff=arrays['U'][:,:rank].copy(),O=arrays['V'].copy(),Pstar=arrays['Pstar'].copy())
    planned={(rank,seed) for rank in cfg['ranks'] for seed in cfg['pilot_seeds']+cfg['confirm_seeds']}
    sources=sorted((out/'raw').glob('*.json'));raw=[e.read(path) for path in sources]
    assert {(d['rank'],d['seed']) for d in raw}==planned and len(raw)==len(planned)
    checked=0;updates=0;unstable=0;fullrank=0;first_pairs=0;max_quality_error=0.;max_update_error=0.;decomposition=[];cleanup=[]
    for i,(path,d) in enumerate(zip(sources,raw)):
        assert d['identity']==ident
        policy=out/'policies'/path.with_suffix('.npz').name;critic=out/'critics'/path.with_suffix('.npz').name
        assert e.sha(policy)==d['policy_sha256'] and e.sha(critic)==d['critic_sha256']
        with np.load(policy,allow_pickle=False) as a:policies={key:a[key].copy() for key in a.files}
        with np.load(critic,allow_pickle=False) as a:critics={key:a[key].copy() for key in a.files}
        if d['rank']==cfg['n']:
            np.testing.assert_array_equal(policies['dense'],policies['truncated'])
            np.testing.assert_array_equal(critics['dense'],critics['truncated']);fullrank+=1
        np.testing.assert_array_equal(critics['dense'][1],critics['truncated'][1]);first_pairs+=1
        s=systems[d['rank']];n=cfg['n'];path_failed={m:False for m in policies}
        for row in d['records']:
            method=row['method'];stage=row['stage']
            assert row['transitions']==sum(cfg['batch_schedule'][:stage])+stage*cfg['burn']
            if path_failed[method]:
                assert row['failure']=='prior_failure' and not row['observed'];continue
            if row['failure']=='numerical_failure':
                path_failed[method]=True;assert not row['whole_path_stable'];continue
            k=policies[method][stage];q,pvalue=e.evaluate(s,k)
            assert q['stable']==row['stable'];checked+=1;unstable+=int(not q['stable'])
            for key in ('rho','gap','cost','relative_gap'):
                if q[key] is None:assert row[key] is None
                else:
                    max_quality_error=max(max_quality_error,abs(q[key]-row[key]))
                    np.testing.assert_allclose(q[key],row[key],atol=2e-8,rtol=1e-8)
            if stage:
                h=critics[method][stage];np.testing.assert_allclose(h,h.T,atol=2e-12)
                assert hashlib.sha256(h.tobytes()).hexdigest()==row['raw_critic_sha256']
                rank=None if method=='dense' or d['rank']==n else d['rank']
                replay=pi_gain({'R':s['R']},h[n:,n:]-s['R'],h[n:,:n],rank)[0]
                max_update_error=max(max_update_error,float(np.max(abs(replay-k))))
                np.testing.assert_allclose(replay,k,atol=2e-10,rtol=2e-9);updates+=1
                assert row['solver']['converged'] and row['solver']['relative_residual']<=2*cfg['solver_rtol']
                assert row['solver']['coordinates']=='original' and row['solver']['whitening'] is False
                assert row['solver']['low_rank_critic'] is False
            if not q['stable']:path_failed[method]=True;assert not row['whole_path_stable']
            else:
                assert row['whole_path_stable']
                for eps in (cfg['epsilon'],cfg['epsilon']/2):assert (q['gap']<=eps)==(row['gap']<=eps)
            if stage==len(cfg['batch_schedule']) and q['stable']:
                diag=loss_diagnostics(s,private[d['rank']],k)
                decomposition.append(dict(rank=d['rank'],seed=d['seed'],method=method,
                    phase='pilot' if d['seed'] in cfg['pilot_seeds'] else 'confirm',
                    gap=diag['gap'],redundant_loss=diag['redundant_loss'],effective_loss=diag['effective_loss'],
                    redundant_fraction=diag['redundant_loss']/max(diag['gap'],1e-30),
                    decomposition_residual=diag['decomposition_residual']))
                # Post-hoc true-critic diagnostics only, never sent to a learner.
                exact=dict(rank=d['rank'],seed=d['seed'],method=method,
                    phase='pilot' if d['seed'] in cfg['pilot_seeds'] else 'confirm',
                    before_gap=q['gap'])
                reference_k=k.copy();reference_p=pvalue
                for step in (1,2):
                    reference_k=pi_gain({'R':s['R']},s['B'].T@reference_p@s['B'],
                                        s['B'].T@reference_p@s['A'],None)[0]
                    quality,reference_p=e.evaluate(s,reference_k)
                    assert quality['stable']
                    exact[f'after_{step}_gap']=quality['gap']
                    exact[f'after_{step}_meets_primary']=quality['gap']<=cfg['epsilon']
                    exact[f'after_{step}_meets_sensitivity']=quality['gap']<=cfg['epsilon']/2
                cleanup.append(exact)
        if (i+1)%25==0:print(f'PI audit {i+1}/{len(raw)}',flush=True)
    result=dict(status='PASS',source_tasks=len(raw),policy_checkpoints_checked=checked,
        unstable_policies_checked=unstable,critic_updates_replayed=updates,full_rank_paired_task_checks=fullrank,
        first_estimate_pairing_checks=first_pairs,maximum_quality_recompute_difference=max_quality_error,
        maximum_actor_replay_difference=max_update_error,identity=ident,
        original_coordinates_verified=True,all_target_classifications_recomputed=True,
        offline_exact_PI_cleanup_endpoints=len(cleanup),offline_exact_PI_cleanup_updates=2,
        cleanup_learning_transitions=0)
    e.atomic_json(out/'audit.json',result)
    report=out/'report-confirm';report.mkdir(exist_ok=True)
    csv_write(report/'endpoint_loss_decomposition_all_seeds.csv',decomposition)
    csv_write(report/'endpoint_exact_PI_cleanup_all_seeds.csv',cleanup)
    summary=[]
    for rank in cfg['ranks']:
        for method in ('dense','truncated'):
            group=[d for d in decomposition if d['rank']==rank and d['method']==method and d['phase']=='confirm']
            if group:
                row=dict(rank=rank,method=method,stable_seeds=len(group))
                for key in ('gap','redundant_loss','effective_loss','redundant_fraction'):row[key+'_median']=float(np.median([r[key] for r in group]))
                summary.append(row)
    csv_write(report/'endpoint_loss_decomposition_summary.csv',summary)
    print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--system-root',type=Path,required=True)
    a=p.parse_args()
    with threadpool_limits(limits=1):audit(a.output,a.system_root)
