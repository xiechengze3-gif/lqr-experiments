"""Reanalyse archived NPG only; no new sampled NPG trajectories."""
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import rng_for,orth,dare,op,atomic_json,evaluate,targets,eta

ARCHIVE=Path('E:/ChatGPT/Results/LQR_experiments/npg-budget-complete-e93b7ffa7fca793e/npg-budget-e93b7ffa7fca793e')


def nested_system(n,rank,seed):
    """Numerically unchanged nested generator, explicit local diagnostic entry.

    Original source: scripts/npg_budget_system.py. Reproduction is checked
    against archived matrices' hashes and initial costs, never a fake Slurm ID.
    """
    rng=rng_for(773291,n,seed);u,v,uq,ur=[orth(rng,n) for _ in range(4)]
    diagonal=rng.uniform(-.25,.55,n);diagonal[0]=1.12
    latent=np.diag(diagonal)+.10*np.diag(np.ones(n-1),1)
    latent+=.025/np.sqrt(n)*rng.normal(size=(n,n));a=u@latent@u.T
    q=(uq*np.linspace(1.,3.,n))@uq.T;r=(ur*np.linspace(1.,2.5,n))@ur.T
    singular=np.zeros(n);singular[:rank]=1.2;b=(u*singular)@v.T;k0=.35*v@u.T
    p0=(3.+2.5*.35**2)/(1.-.925**2);ks,ps=dare(a,b,q,r)
    pinit=solve_discrete_lyapunov((a-b@k0).T,q+k0.T@r@k0)
    return dict(A=a,B=b,Q=q,R=r,W=np.eye(n),K0=k0,Kstar=ks,
                Jstar=float(np.trace(ps)),initial_gap=float(np.trace(pinit)-np.trace(ps)),p0=p0)


def write_csv(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(rows)


def run(out):
    cfg=json.loads((ROOT/'configs/npg_budget_order.json').read_text())
    out.mkdir(parents=True,exist_ok=True);curves=[];endpoints=[];systems={};noise={};provenance=[]
    for path in sorted((ARCHIVE/'raw').glob('task-*.json')):
        data=json.loads(path.read_text());t=data['task'];key=(t['r'],t['system_seed'])
        records=data['records'];diag=data['diagnostics'];gap0=diag['initial_gap']
        if gap0<=1e-10*max(1.,diag['Jstar']):raise ValueError('Invalid archived initial gap')
        systems[key]=diag
        provenance.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        for method in ('raw','truncated'):
            rows=[r for r in records if r['method']==method];last=rows[-1]
            stable=bool(last['stable'] and last.get('observed',True))
            endpoints.append(dict(rank=t['r'],system_seed=t['system_seed'],method=method,
                schedule=t['schedule_id'],planned_transitions=data['planned_total_transitions'],
                actual_transitions=last['transitions'],stable=stable,
                status='completed' if stable else 'controller_instability',
                gap=last['gap'],g=last['gap']/gap0 if last['gap'] is not None else None,
                success=bool(stable and last['gap']/gap0<=.1)))
            first=rows[1]
            noise[(t['r'],t['system_seed'],method,first['N'])]=first.get('critic_error_fro2')
            for row in rows:
                curves.append(dict(rank=t['r'],system_seed=t['system_seed'],method=method,
                    schedule=t['schedule_id'],stage=row['stage'],transitions=row['transitions'],
                    observed=row.get('observed',True),stable=row['stable'],gap=row['gap'],
                    g=row['gap']/gap0 if row['gap'] is not None else None))
    audit=[];exact=[]
    for (rank,seed),diag in sorted(systems.items()):
        s=nested_system(50,rank,seed);q,p=evaluate(s,s['K0']);truth=targets(s,s['K0'],16,p)
        np.testing.assert_allclose(s['initial_gap'],diag['initial_gap'],rtol=1e-10,atol=1e-8)
        hashes={k:hashlib.sha256(np.ascontiguousarray(s[k]).tobytes()).hexdigest() for k in ('A','B','Q','R','K0')}
        audit.append(dict(rank=rank,system_seed=seed,initial_gap=s['initial_gap'],
            rho=q['rho'],spectral_margin=1-q['rho'],operator_margin=1-op(s['A']-s['B']@s['K0']),
            B_fro=float(np.linalg.norm(s['B'])),Z0_fro=float(np.linalg.norm(truth['Z'])),
            B_fro2_per_rank=float(np.sum(s['B']**2)/rank),
            hash_match=all(hashes[k]==diag['hashes'][k] for k in hashes),
            reproduction='initial cost checked; hash equality is platform dependent'))
        np.savez(out/f'npg-system-r{rank}-s{seed}.npz',**{k:v for k,v in s.items() if isinstance(v,np.ndarray)})
        # Identical historical K0 and scalar step, fixed 256 iterations.
        k=s['K0'].copy();step=cfg['step_multiplier']*eta(s)
        for stage in range(257):
            quality,p=evaluate(s,k)
            exact.append(dict(rank=rank,system_seed=seed,stage=stage,eta=step,
                g=quality['gap']/s['initial_gap'] if quality['gap'] is not None else None,**quality))
            if p is None:break
            z=targets(s,k,16,p)['Z'];k=k-step*(s['R']@k+z)
        print(json.dumps(dict(npg_exact_rank=rank,seed=seed,final_g=exact[-1]['g'])),flush=True)
    ratios=[]
    for rank in cfg['ranks']:
        budgets={}
        for method in ('raw','truncated'):
            candidates=[]
            for schedule in cfg['schedules']:
                selected=[e for e in endpoints if e['rank']==rank and e['method']==method and e['schedule']==schedule]
                if len(selected)==4 and all(e['success'] for e in selected):
                    candidates.append(selected[0]['planned_transitions'])
            budgets[method]=min(candidates) if candidates else None
        ratios.append(dict(rank=rank,dense_budget=budgets['raw'],truncated_budget=budgets['truncated'],
            ratio=budgets['raw']/budgets['truncated'] if all(budgets.values()) else None,
            dense_censored=budgets['raw'] is None,truncated_censored=budgets['truncated'] is None,
            criterion='all four independent systems, fixed final stage256, g<=0.1'))
    noise_rows=[dict(rank=r,system_seed=s,method=m,blocks=b,noise_fro2=e) for (r,s,m,b),e in sorted(noise.items())]
    for name,rows in [('initial_diagnostics',audit),('normalized_curves',curves),('endpoints',endpoints),
                       ('exact_critic',exact),('budget_ratios',ratios),('initial_noise',noise_rows)]:
        write_csv(out/(name+'.csv'),rows)
    atomic_json(out/'summary.json',dict(initial=audit,budget_ratios=ratios,
        archived_trajectories=len(endpoints),instabilities=sum(not e['stable'] for e in endpoints),
        exact_critic_runs=len(audit),exact_critic_sampled_transitions=0,
        generator_source_sha256=hashlib.sha256((ROOT/'scripts/npg_budget_system.py').read_bytes()).hexdigest(),
        provenance=provenance))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
