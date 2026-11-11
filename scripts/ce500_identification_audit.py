"""Independent raw trajectory least-squares and saved CE policy replay at 500d."""
import argparse
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from threadpoolctl import threadpool_limits
import ce500_matched_gap as run
import rank_sweep100 as e


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--phase',choices=['pilot','confirm'],default='confirm');a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    cfg=e.read(a.manifest);out=Path(cfg['output']);dest=out/'identification-audit'
    dest.mkdir(parents=True,exist_ok=True);rows=[];began=time.monotonic();count=8192
    with threadpool_limits(1):
        for rank in cfg['ranks']:
            s=run.load_system(cfg,rank);n=cfg['n'];pulse,noise=run.rngs(cfg,9003)
            f=np.ascontiguousarray(s['A']-s['B']@s['K0'])
            x,_=e.nominal_chunk(f,np.zeros(n),noise.normal(size=(cfg['burn'],n)))
            pulses=cfg['sigma']*pulse.normal(size=(count,n));noises=noise.normal(size=(count,n))
            endpoint,z,y=e.ce_chunk(f,s['B'],s['K0'],x,pulses,noises)
            np.testing.assert_allclose(z[1:,:n],y[:-1],rtol=0,atol=0)
            np.testing.assert_allclose(z[:,n:],-z[:,:n]@s['K0'].T+pulses,atol=1e-12,rtol=1e-12)
            truth=np.concatenate((s['A'],s['B']),axis=1)
            label_error=float(np.max(abs(y-z@truth.T-noises)))
            noiseless=np.linalg.lstsq(z,y-noises,rcond=None)[0].T
            true_error=float(np.max(abs(noiseless-truth)))
            raw=np.linalg.lstsq(z,y,rcond=None)[0].T
            gram=z.T@z;cross=y.T@z
            sufficient=run.cho_solve(run.cho_factor((gram+gram.T)/2),cross.T).T
            solver_error=float(np.max(abs(raw-sufficient)))
            assert max(label_error,true_error,solver_error)<2e-11
            seed=cfg[a.phase+'_seeds'][0];stem=f'ce-r{rank:03d}-s{seed:04d}'
            saved=e.read(out/'raw'/(stem+'.json'));budget=max(saved['budgets'])
            final=[q for q in saved['records'] if q['ols_samples']==budget]
            with np.load(out/'estimates'/(stem+'.npz'),allow_pickle=False) as fit:
                ahat,bhat=fit['Ahat'].copy(),fit['Bhat'].copy()
            errors={}
            with np.load(out/final[0]['policy_file'],allow_pickle=False) as gains:
                for method in ('dense','truncated'):
                    recovered,_=e.dare(ahat,e.corrected(bhat,method,rank),s['Q'],s['R'])
                    stored=gains['shared'] if rank==n else gains[method]
                    errors[method]=float(np.max(abs(recovered-stored)))
                    assert errors[method]<2e-11
            row=dict(rank=rank,raw_OLS_samples=count,label_alignment_error=label_error,
                noiseless_AB_recovery_error=true_error,raw_lstsq_vs_sufficient_statistics_error=solver_error,
                replay_seed=seed,replay_OLS_budget=budget,Riccati_policy_replay_errors=errors)
            rows.append(row);print(__import__('json').dumps(row),flush=True)
    e.atomic_json(dest/'audit.json',dict(status='PASS',phase=a.phase,results=rows,
        diagnostic_primitive_transitions=len(rows)*(cfg['burn']+count),
        seconds=time.monotonic()-began,slurm_job_id=os.environ['SLURM_JOB_ID'],identity=run.identity(cfg),
        audit_source_sha256=e.sha(Path(__file__)),
        pipeline='[x_t,u_t] -> x_{t+1}; raw joint lstsq vs joint Gram OLS; unchanged Ahat; only Bhat truncated; saved-policy DARE replay'))


if __name__=='__main__':main()
