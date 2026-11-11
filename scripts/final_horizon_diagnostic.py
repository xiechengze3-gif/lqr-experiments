"""Separate finite-H bias from old second-step critic error without actor runs."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from dense_scaling import targets,evaluate,rng_for,atomic_json
from adaptive_rank_run import direct_data
from adaptive_rank import pi_update,noise_proxy
from final_npg_audit import write_csv


def run(out):
    old=Path('E:/ChatGPT/Results/LQR_experiments/adaptive50-20261012');rows=[];total=0
    for tid in range(4):
        data=json.loads((old/'DIRECT_PI/raw'/f'task-{tid:03d}.json').read_text());t=data['task']
        with np.load(old/'systems'/f'system-{tid:03d}.npz') as d:s={k:d[k].copy() for k in d.files}
        _,full,halves,used=direct_data(s,s['K0'],np.zeros(50),65536,1024,16,
            rng_for(202610123,50,t['system_seed'],t['policy_seed'],t['trial_seed'],1))
        total+=used
        scale=noise_proxy(np.concatenate(halves[0][:2],axis=1),np.concatenate(halves[1][:2],axis=1))
        for method in ('dense','known_rank','adaptive_1'):
            k,*_=pi_update(*full[:2],s['R'],method,scale,4 if method=='known_rank' else None)
            q,p=evaluate(s,k);f=s['A']-s['B']@k
            for h in (8,16,32,64):
                truth=targets(s,k,h,p)
                rows.append(dict(task=tid,method=method,horizon=h,rho=q['rho'],
                    F_operator=float(np.linalg.norm(f,2)),P_operator=float(np.linalg.norm(p,2)),
                    G_energy=float(np.sum(truth['G']**2)),Z_energy=float(np.sum(truth['Z']**2)),
                    G_finite_horizon_bias_fro2=float(np.sum((truth['G']-truth['GH'])**2)),
                    Z_finite_horizon_bias_fro2=float(np.sum((truth['Z']-truth['ZH'])**2)),
                    diagnostic_only=True))
    out.mkdir(parents=True,exist_ok=True);write_csv(out/'old_policy_horizon_bias.csv',rows)
    atomic_json(out/'summary.json',dict(rows=rows,actual_transitions=total,
        purpose='Replayed first-stage data construct historical second-step policies; no second-stage sampling.'))
    for method in ('dense','known_rank','adaptive_1'):
        selected=[r for r in rows if r['method']==method and r['horizon']==16]
        print(method,{k:float(np.median([r[k] for r in selected])) for k in
              ('F_operator','P_operator','G_finite_horizon_bias_fro2','Z_finite_horizon_bias_fro2')})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
