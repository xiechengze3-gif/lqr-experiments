"""Oracle sensitivity diagnostic with identical isotropic model errors across ranks.

No learning transitions or replacement CE algorithms. This separates plant/control
geometry from differences in trajectory-derived OLS error distributions.
"""
import argparse
import csv
from pathlib import Path
import os
import sys
import time
if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from threadpoolctl import threadpool_limits
import rank_sweep100 as e
from matched_gap_npg_pi import load


def csv_write(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def run(cfg):
    assert os.environ.get('SLURM_JOB_ID')
    out=Path(cfg['output'])/'ce-common-error-diagnostic-v2';out.mkdir(exist_ok=True)
    rows=[];solves=0;new_solves=0;reused=0;started=time.monotonic()
    source_hash=e.sha(Path(__file__))
    tag=dict(source_sha256=source_hash,system_hashes=cfg['system_artifact_sha256'],rng_seed=2026101903,scales=[.01,.02])
    systems={rank:load(cfg,rank)[0] for rank in cfg['ranks']}
    for seed in range(30):
        checkpoint=out/'checkpoints'/f's{seed:03d}.json'
        if checkpoint.exists():
            saved=e.read(checkpoint);assert saved['identity']==tag
            assert len(saved['records'])==30
            rows+=saved['records'];solves+=saved['Riccati_solves'];reused+=1;continue
        first=len(rows);before=solves
        rng=e.rng_for(2026101903,seed);ea=rng.normal(size=(100,100));eb=rng.normal(size=(100,100))
        ea/=np.linalg.norm(ea);eb/=np.linalg.norm(eb)
        for rank in cfg['ranks']:
            s=systems[rank]
            for scale in (.01,.02):
                variants={'A_only':(s['A']+scale*ea,s['B']),
                    'B_dense_only':(s['A'],s['B']+scale*eb),
                    'B_truncated_only':(s['A'],e.corrected(s['B']+scale*eb,'truncated',rank))}
                cache=[]
                for variant,(a,b) in variants.items():
                    existing=next((v[2] for v in cache if np.array_equal(v[0],a) and np.array_equal(v[1],b)),None)
                    if existing is None:
                        k,_=e.dare(a,b,s['Q'],s['R']);solves+=1;new_solves+=1
                        f=s['A']-s['B']@k;rho=float(max(abs(np.linalg.eigvals(f))));assert rho<1
                        cov=solve_discrete_lyapunov(f,s['W']);delta=k-s['Kstar']
                        gap=float(np.trace(cov@delta.T@(s['R']+s['B'].T@s['Pstar']@s['B'])@delta))
                        existing=dict(gap=gap,rho=rho);cache.append((a,b,existing))
                    error=float(np.sum((a-s['A'])**2)+np.sum((b-s['B'])**2))
                    rows.append(dict(rank=rank,seed=seed,variant=variant,raw_error_scale=scale,
                        postprocessing_model_error_fro2=error,control_gap=existing['gap'],rho=existing['rho'],
                        gap_per_raw_error_fro2=existing['gap']/scale**2,
                        gap_per_postprocessed_error_fro2=existing['gap']/error))
        e.atomic_json(checkpoint,dict(identity=tag,records=rows[first:],Riccati_solves=solves-before,
            slurm_job_id=os.environ['SLURM_JOB_ID']))
        print(f'Common-error diagnostic committed {seed+1}/30 directions',flush=True)
    assert len(rows)==900
    summary=[]
    for rank in cfg['ranks']:
        for variant in ('A_only','B_dense_only','B_truncated_only'):
            for scale in (.01,.02):
                rr=[q for q in rows if q['rank']==rank and q['variant']==variant and q['raw_error_scale']==scale]
                summary.append(dict(rank=rank,variant=variant,scale=scale,seeds=len(rr),
                    gap_median=float(np.median([q['control_gap'] for q in rr])),
                    model_error_fro2_median=float(np.median([q['postprocessing_model_error_fro2'] for q in rr])),
                    gap_per_raw_error_fro2_median=float(np.median([q['gap_per_raw_error_fro2'] for q in rr])),
                    gap_per_postprocessed_error_fro2_median=float(np.median([q['gap_per_postprocessed_error_fro2'] for q in rr]))))
    csv_write(out/'all_directions.csv',rows);csv_write(out/'summary.csv',summary)
    e.atomic_json(out/'diagnostic.json',dict(status='complete',summary=summary,seeds=30,raw_model_error_scales=[.01,.02],
        paired_identical_isotropic_error_directions_across_ranks=True,physical_primitive_transitions=0,
        total_unique_Riccati_solves=solves,new_Riccati_solves_this_invocation=new_solves,reused_direction_seeds=reused,
        seconds=time.monotonic()-started,
        source_sha256=source_hash,slurm_job_id=os.environ['SLURM_JOB_ID'],
        scope='Oracle model-perturbation sensitivity only. Not a learning algorithm, sample-complexity estimate, or a new trajectory experiment.'))
    print('Common-model-error diagnostic complete',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    with threadpool_limits(1):run(e.read(a.manifest))
