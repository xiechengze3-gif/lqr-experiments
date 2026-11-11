"""Replay the actual four-task 50d snapshot, with labelled diagnostic hybrids."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from dense_scaling import atomic_json,rng_for,evaluate,targets
from adaptive_rank_run import direct_data
from adaptive_rank import pi_update,noise_proxy
from direct_stein_final import correct,update
from final_npg_audit import write_csv


def run(out):
    archive=Path('E:/ChatGPT/Results/LQR_experiments/adaptive50-20261012')
    rows=[];replays=[]
    for tid in range(4):
        old=json.loads((archive/'DIRECT_PI/raw'/f'task-{tid:03d}.json').read_text());t=old['task']
        with np.load(archive/'systems'/f'system-{tid:03d}.npz') as d:
            s={k:d[k].copy() for k in d.files}
        for method in ('dense','known_rank','adaptive_1'):
            k=s['K0'].copy();x=np.zeros(50)
            for stage in (1,2):
                # Exact historical innovation seed, baseline, burn and continuous endpoint.
                rng=rng_for(202610123,50,t['system_seed'],t['policy_seed'],t['trial_seed'],stage)
                x,full,halves,used=direct_data(s,k,x,65536,1024,16,rng)
                g,c,z=full;scale=noise_proxy(np.concatenate(halves[0][:2],axis=1),np.concatenate(halves[1][:2],axis=1))
                old_k,old_g,old_c,info=pi_update(g,c,s['R'],method,scale,4 if method=='known_rank' else None)
                q,_=evaluate(s,old_k)
                saved=next(r for r in old['records'] if r.get('stage')==stage and r['method']==method)
                np.testing.assert_allclose(q['rho'],saved['rho'],rtol=1e-7,atol=1e-8)
                replays.append(dict(task=tid,method=method,stage=stage,rho=q['rho'],
                                    archived_rho=saved['rho'],stable=q['stable']))
                _,p=evaluate(s,k);truth=targets(s,k,16,p)
                newmethod='adaptive' if method=='adaptive_1' else method
                gg,zz,newinfo=correct(g,z,newmethod,[(a[0],a[2]) for a in halves],4 if method=='known_rank' else None)
                for label,g1,z1 in [('exact_GZ',truth['G'],truth['Z']),('exact_G_estimated_Z',truth['G'],zz),
                                   ('estimated_G_exact_Z',gg,truth['Z']),('both_estimated',gg,zz)]:
                    for step in (1.,.25):
                        candidate,diag=update(k,s['R'],g1,z1,step);after,_=evaluate(s,candidate)
                        rows.append(dict(task=tid,method=method,stage=stage,eta=step,ablation=label,
                            diagnostic_only=True,transitions=used,before_gap=float(np.trace(p)-s['Jstar']),
                            G_raw_error_fro2=float(np.sum((g-truth['G'])**2)),
                            Z_raw_error_fro2=float(np.sum((z-truth['Z'])**2)),
                            clipping_mismatch_K_fro=float(np.linalg.norm((old_g-g)@k)),
                            normalized_gap=after['gap']/float(s['initial_gap']) if after['gap'] is not None else None,
                            **after,**diag,**newinfo))
                k=old_k
                if not q['stable']:break
        print(json.dumps(dict(old_task_replayed=tid)),flush=True)
    out.mkdir(parents=True,exist_ok=True);write_csv(out/'hybrids.csv',rows)
    atomic_json(out/'summary.json',dict(replay='PASS',replays=replays,rows=rows,
        note='Stage2 policies follow the failed historical trajectories. All hybrids are offline diagnostics.'))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
