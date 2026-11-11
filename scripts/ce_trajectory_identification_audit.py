"""Independent CE trajectory replay and offline known-parameter interventions.

Interventions are diagnostics, never replacements for the declared CE learner.
"""
import argparse
from pathlib import Path
import os
import resource
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from scipy.linalg import cho_factor,cho_solve
from threadpoolctl import threadpool_limits
import rank_sweep100 as e
from matched_gap_npg_pi import load
from rank_sweep100_report import csv_write


def diagnostics(s,ahat,bhat,rank):
    bt=e.corrected(bhat,'truncated',rank)
    variants={'dense':(ahat,bhat),'truncated':(ahat,bt),
        'known_A_dense_B':(s['A'],bhat),'known_A_truncated_B':(s['A'],bt),
        'estimated_A_known_B':(ahat,s['B']),
        'recomposed_A_truncated_B':(ahat+(bt-bhat)@s['K0'],bt)}
    rows=[]
    for name,(a,b) in variants.items():
        try:
            k,_=e.dare(a,b,s['Q'],s['R']);q,_=e.evaluate(s,k)
        except (ValueError,np.linalg.LinAlgError):q=dict(stable=False,gap=None,rho=None)
        rows.append(dict(variant=name,**q))
    return rows


def audit(cfg):
    assert os.environ.get('SLURM_JOB_ID')
    source=Path(cfg['ce_source']);out=Path(cfg['output'])/'ce-identification-audit';out.mkdir(parents=True,exist_ok=True)
    c=e.read(source/'resolved_config.json');rows=[];max_residual=0.;max_policy=0.;replays=0;physical=0
    # Audit all formal final joint OLS fits, slices, and actual Riccati outputs.
    for rank in cfg['ranks']:
        s,_=load(cfg,rank)
        for seed in c['confirm_seeds']:
            stem=f'ce-r{rank:03d}-s{seed:04d}'
            with np.load(source/'estimates'/(stem+'.npz')) as z:
                theta=cho_solve(cho_factor((z['gram']+z['gram'].T)/2),z['cross'].T).T
                np.testing.assert_array_equal(theta[:,:100],z['Ahat']);np.testing.assert_array_equal(theta[:,100:],z['Bhat'])
                residual=float(np.linalg.norm(theta@z['gram']-z['cross'])/np.linalg.norm(z['cross']))
                assert residual<1e-10;max_residual=max(max_residual,residual)
                ahat,bhat=z['Ahat'].copy(),z['Bhat'].copy()
            raw=e.read(source/'raw'/(stem+'.json'))
            with np.load(source/'policies'/(stem+'.npz')) as z:policies=z['policies']
            for j,m in enumerate(('dense','truncated')):
                k,_=e.dare(ahat,e.corrected(bhat,m,rank),s['Q'],s['R'])
                difference=float(np.max(abs(k-policies[-2+j])));max_policy=max(max_policy,difference);assert difference<2e-12
            for q in diagnostics(s,ahat,bhat,rank):
                rows.append(dict(rank=rank,seed=seed,ols_samples=max(c['confirm_budgets']),transitions=raw['physical_transitions'],
                    source='saved_final_joint_OLS',A_error_fro2=float(np.sum((ahat-s['A'])**2)),
                    B_error_fro2=float(np.sum((bhat-s['B'])**2)),B_truncated_error_fro2=float(np.sum((e.corrected(bhat,'truncated',rank)-s['B'])**2)),**q))
    # Independent raw-design least squares, sign, and one-step time alignment.
    direct=[]
    for rank in (2,100):
        s,_=load(cfg,rank);k=s['K0'];f=s['A']-s['B']@k
        pulse=e.rng_for(c['sampling_seed'],3,9904,0,0);noise=e.rng_for(c['sampling_seed'],3,9904,0,1)
        x,_=e.nominal_chunk(np.ascontiguousarray(f),np.zeros(100),noise.normal(size=(c['burn'],100)))
        xp=x.copy();pp=c['sigma']*pulse.normal(size=(4096,100));ww=noise.normal(size=(4096,100))
        end,z,y=e.ce_chunk(np.ascontiguousarray(f),s['B'],k,x,pp,ww)
        np.testing.assert_array_equal(z[0,:100],xp);np.testing.assert_array_equal(z[1:,:100],y[:-1])
        np.testing.assert_allclose(z[:,100:]+z[:,:100]@k.T,pp,atol=2e-13)
        np.testing.assert_allclose(y-z[:,:100]@s['A'].T-z[:,100:]@s['B'].T,ww,atol=2e-13)
        lstsq=np.linalg.lstsq(z,y,rcond=None)[0].T
        streamed=cho_solve(cho_factor(z.T@z),z.T@y).T
        err=float(np.max(abs(lstsq-streamed)));assert err<2e-12
        exact=np.linalg.lstsq(z,z@np.c_[s['A'],s['B']].T,rcond=None)[0].T
        recovery=float(np.max(abs(exact-np.c_[s['A'],s['B']])));assert recovery<2e-12
        physical+=4096+c['burn'];direct.append(dict(rank=rank,OLS_direct_vs_statistics_max_error=err,noiseless_AB_recovery_max_error=recovery,
            time_alignment=True,actual_action_sign=True,dynamics_residual_matches_generated_noise=True))
    # Replay original paired formal sources around both actual threshold regions.
    # Raw data are newly simulated here and charged only to audit overhead.
    selected={3072,6144,14336,28672,32768}
    for rank in (2,100):
        s,_=load(cfg,rank);k=s['K0'];f=np.ascontiguousarray(s['A']-s['B']@k)
        for seed in c['confirm_seeds']:
            pulse=e.rng_for(c['sampling_seed'],3,seed,0,0);noise=e.rng_for(c['sampling_seed'],3,seed,0,1)
            x,_=e.nominal_chunk(f,np.zeros(100),noise.normal(size=(c['burn'],100)))
            gram=np.zeros((200,200));cross=np.zeros((100,200));done=0;fits={}
            stem=f'ce-r{rank:03d}-s{seed:04d}'
            with np.load(source/'policies'/(stem+'.npz')) as z:original=z['policies'].copy()
            for index,budget in enumerate(c['confirm_budgets']):
                if budget>32768:break
                while done<budget:
                    count=min(c['chunk_size'],budget-done)
                    x,z,y=e.ce_chunk(f,s['B'],k,x,c['sigma']*pulse.normal(size=(count,100)),noise.normal(size=(count,100)))
                    gram+=z.T@z;cross+=y.T@z;done+=count
                theta=cho_solve(cho_factor((gram+gram.T)/2),cross.T).T
                for j,m in enumerate(('dense','truncated')):
                    candidate,_=e.dare(theta[:,:100],e.corrected(theta[:,100:],m,rank),s['Q'],s['R'])
                    err=float(np.max(abs(candidate-original[2*index+j])));assert err<2e-12
                    max_policy=max(max_policy,err);replays+=1
                if budget in selected:
                    fits['theta_'+str(budget)]=theta.copy()
                    for q in diagnostics(s,theta[:,:100],theta[:,100:],rank):
                        rows.append(dict(rank=rank,seed=seed,ols_samples=budget,transitions=budget+c['burn'],source='replayed_original_trajectory',**q))
            e.save_npz(out/'replayed_joint_fits'/(stem+'.npz'),**fits)
            physical+=done+c['burn']
        print(f'CE replay rank {rank} complete',flush=True)
    csv_write(out/'all_diagnostics.csv',rows)
    summary=[]
    for rank in cfg['ranks']:
        for count in sorted({q['ols_samples'] for q in rows if q['rank']==rank}):
            group=[q for q in rows if q['rank']==rank and q['ols_samples']==count]
            for variant in sorted({q['variant'] for q in group}):
                rr=[q for q in group if q['variant']==variant];gaps=[q['gap'] for q in rr if q['stable']]
                summary.append(dict(rank=rank,ols_samples=count,transitions=count+c['burn'],variant=variant,seeds=len(rr),
                    unstable=sum(not q['stable'] for q in rr),gap_median=float(np.median(gaps)) if gaps else None,
                    gap_q25=float(np.quantile(gaps,.25)) if gaps else None,gap_q75=float(np.quantile(gaps,.75)) if gaps else None))
    csv_write(out/'summary.csv',summary)
    e.atomic_json(out/'audit.json',dict(status='PASS',saved_formal_joint_fits=150,saved_formal_Riccati_replays=300,
        original_trajectory_prefix_policy_replays=replays,OLS_normal_equation_max_relative_residual=max_residual,
        original_policy_max_absolute_difference=max_policy,direct_raw_design_checks=direct,
        audit_primitive_transitions=physical,summary=summary,
        interventions='Known A / known B / A recomposed to preserve estimated closed-loop are offline diagnostics; none replaces primary CE.',
        slurm_job_id=os.environ['SLURM_JOB_ID'],peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        sources={p:e.sha(ROOT/p) for p in ['scripts/ce_trajectory_identification_audit.py','dense_scaling.py','scripts/rank_sweep100.py']}))
    print('CE identification audit PASS',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);args=p.parse_args()
    with threadpool_limits(1):audit(e.read(args.manifest))
