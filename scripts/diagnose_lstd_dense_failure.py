"""Replay a failed dense batch and test solver budgets without changing study.

Original scientific engine/collector are loaded from the frozen 50d release.
No sample, policy, threshold or main-run checkpoint is changed by this audit.
"""
import argparse
import hashlib
import importlib
import json
import sys
import time
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--release',required=True,type=Path)
    parser.add_argument('--study',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--task-id',type=int,default=0)
    args=parser.parse_args()
    sys.path[:0]=[str(args.release/'scripts'),str(args.release)]
    engine=importlib.import_module('adaptive50_run')
    subject=importlib.import_module('adaptive_rank_run')
    from full_lstd import solve
    from adaptive_rank import pi_update
    from dense_scaling import rng_for,atomic_json,evaluate
    from threadpoolctl import threadpool_limits
    import numpy as np
    from scipy.linalg import solve_discrete_lyapunov
    cfg=json.loads((args.release/'configs/adaptive50_suite.json').read_text())
    task=cfg['tasks'][args.task_id]
    saved=json.loads((args.study/'LSTD_PI'/'raw'/f"task-{args.task_id:03d}.json").read_text())
    failure=next(r for r in saved['records'] if r['method']=='dense' and r.get('failure')=='full_solver_failure')
    fail_stage=failure['stage']
    n=task['n'];s,sysdiag=engine.load_system(args.study,task)
    result=dict(task=task,failure_stage=fail_stage,frozen_identity=saved['identity'],
        audit_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),status='RUNNING',
        methods=[],original_failure_solver=failure['solver']['full_solver'],
        main_campaign_unchanged=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    with threadpool_limits(limits=cfg['threads']):
        k,x=s['K0'].copy(),np.zeros(n)
        for stage in range(1,fail_stage+1):
            count=cfg['schedules']['LSTD_PI'][stage-1]
            x,z,y=subject.transition_data(s,k,x,count,cfg['burn'],rng_for(202610123,n,
                task['system_seed'],task['policy_seed'],task['trial_seed'],stage))
            if stage<fail_stage:
                full,diag=subject.lstd_fit(z,y,k,s['Q'],s['R'],cfg)
                assert full is not None and diag['converged']
                candidate,_,_,_=pi_update(*full,s['R'],'dense')
                expected=next(r for r in saved['records'] if r['method']=='dense' and r['stage']==stage)
                digest=hashlib.sha256(candidate.tobytes()).hexdigest()
                assert digest==expected['policy_sha256'], 'Replay policy differs from original'
                k=candidate
        next_z=np.concatenate((y,-y@k.T),axis=1)
        costs=np.einsum('ij,ij->i',z[:,:n]@s['Q'],z[:,:n])
        costs+=np.einsum('ij,ij->i',z[:,n:]@s['R'],z[:,n:])
        _,singular,vt=np.linalg.svd(s['B'],full_matrices=False)
        projector=vt[singular<1e-10].T@vt[singular<1e-10]
        f=s['A']-s['B']@k
        sigma=solve_discrete_lyapunov(f,s['W'])
        null_gain=projector@k
        cov=z.T@z/len(z)
        nominal, _=evaluate(s,k)
        result['failed_batch_sha256']=hashlib.sha256(z.tobytes()+next_z.tobytes()+costs.tobytes()).hexdigest()
        result['replay_policy_exact']=True
        result['before_failed_solve']=dict(**nominal,K_op=float(np.linalg.norm(k,2)),
            K_fro2=float(np.sum(k*k)),K_null_fro2=float(np.sum(null_gain**2)),
            null_control_cost=float(np.trace(null_gain@sigma@null_gain.T)),
            observed_z_gram_condition=float(np.linalg.cond(cov)),
            observed_z_gram_eigenvalues=np.linalg.eigvalsh(cov).tolist())
        atomic_json(args.output,result)
        # Identical original-coordinate data and tolerance. Only Krylov budget differs.
        for restart,maxiter in ((40,10),(100,20)):
            wall=time.monotonic()
            h,diag=solve(z,next_z,costs,rtol=cfg['solver_rtol'],restart=restart,maxiter=maxiter)
            row=dict(restart=restart,max_cycles=maxiter,inner_iteration_cap=restart*maxiter,
                     wall_seconds=time.monotonic()-wall,solver=diag)
            if restart==40:
                assert np.isclose(diag['relative_residual'],failure['solver']['full_solver']['relative_residual'],rtol=1e-10,atol=1e-12)
                result['failed_batch_original_solver_reproduced']=True
            if diag['converged']:
                candidate,_,_,_=pi_update(h[n:,n:]-s['R'],h[n:,:n],s['R'],'dense')
                row['next_policy'],_=evaluate(s,candidate)
            result['methods'].append(row)
            atomic_json(args.output,result)
            print(json.dumps(dict(restart=restart,max_cycles=maxiter,iterations=diag['iterations'],
                converged=diag['converged'],relative_residual=diag['relative_residual'],
                seconds=row['wall_seconds'])),flush=True)
    result['status']='COMPLETE';result['seconds']=time.monotonic()-start
    atomic_json(args.output,result)
    print(json.dumps(dict(status='COMPLETE',output=str(args.output))),flush=True)


if __name__=='__main__':main()
