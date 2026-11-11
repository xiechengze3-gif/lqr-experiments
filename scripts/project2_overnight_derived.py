"""Saved-data dimension fits and matrix-region checks of the archived NPG."""
import csv
import json
import os
from pathlib import Path
import sys
import time

BASE=Path('/scratch/user/changze/lqr_experiments')
ROOT=BASE/'releases/project2-overnight-20261020'
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
import numpy as np
from scipy.linalg import eigvalsh,solve_discrete_lyapunov
import project2_overnight as science

OUT=BASE/'results/project2-overnight-20261020'


def read_csv(path):
    with path.open(newline='') as stream:return list(csv.DictReader(stream))


def main():
    science.require_compute();begin=time.monotonic();dest=OUT/'derived';dest.mkdir(exist_ok=True)
    results=read_csv(OUT/'report/one_step_outputs.csv')
    noise=read_csv(OUT/'report/null_noise.csv')
    delta={tuple(int(r[k]) for k in ('n','m','r','H','seed','trial','N')):float(r['delta_variance']) for r in noise}
    points=[];fits=[]
    for variable in ('n','r'):
        for method in ('dense','known_rank'):
            selected=[r for r in results if r['algorithm']=='NPG' and r['method']==method and r['policy']=='Kstar'
                and int(r['N'])==131072 and int(r['H'])==16 and int(r['trial'])<10
                and int(r['n'])==int(r['m']) and (int(r['r'])==4 if variable=='n' else int(r['n'])==50)]
            grouped={}
            for row in selected:grouped.setdefault(int(row[variable]),[]).append(row)
            current=[]
            for value,rows in sorted(grouped.items()):
                errors=[float(r['Z_error_fro2']) for r in rows]
                normalized=[float(r['Z_error_fro2'])/delta[tuple(int(r[k]) for k in ('n','m','r','H','seed','trial','N'))] for r in rows]
                record=dict(variable=variable,method=method,value=value,repetitions=len(rows),
                    Z_error_fro2_median=float(np.median(errors)),
                    Z_error_over_delta_variance_median=float(np.median(normalized)))
                points.append(record);current.append(record)
            for metric in ('Z_error_fro2_median','Z_error_over_delta_variance_median'):
                fits.append(dict(variable=variable,method=method,metric=metric,
                    slope=float(np.polyfit(np.log([r['value'] for r in current]),np.log([r[metric] for r in current]),1)[0])))
    science.write_csv(dest/'fixed_policy_dimension_rank_points.csv',points)
    science.atomic_json(dest/'fixed_policy_fits.json',dict(fits=fits,definition='same N,H; all four plants x first ten trials at every cell'))
    legacy=BASE/'results/matched-gap-npg-pi-v2-20261019'
    ce=BASE/'results/ce-matched-initial-gap-20261018'
    certificates=[];sources=[]
    for rank in (2,8,32,64,100):
        path=ce/'systems'/f'r{rank:03d}.npz'
        with np.load(path,allow_pickle=False) as a:s={k:a[k].copy() for k in a.files}
        f0=s['A']-s['B']@s['K0']
        p0=solve_discrete_lyapunov(f0.T,s['Q']+s['K0'].T@s['R']@s['K0'])
        for seed in range(300,330):
            policy=legacy/'npg/policies'/f'npg-r{rank:03d}-s{seed:04d}.npz'
            raw=legacy/'npg/raw'/f'npg-r{rank:03d}-s{seed:04d}.json'
            archived=json.loads(raw.read_text());assert science.sha(policy)==archived['policy_sha256']
            sources.append(dict(path=str(policy),sha256=archived['policy_sha256']))
            with np.load(policy,allow_pickle=False) as saved:
                for method in ('dense','truncated'):
                    assert len(saved[method])==45
                    for stage,k in enumerate(saved[method]):
                        f=s['A']-s['B']@k
                        p=solve_discrete_lyapunov(f.T,s['Q']+k.T@s['R']@k)
                        relative=eigvalsh(p,p0)
                        minimum=float(relative[0]);maximum=float(relative[-1])
                        assert minimum>0
                        certificates.append(dict(rank=rank,seed=seed,method=method,stage=stage,
                            P_relative_min=minimum,P_relative_max=maximum,in_region=bool(maximum<=2+1e-9)))
            science.atomic_json(dest/'progress.json',dict(rank=rank,seed=seed,checked=len(certificates)))
    science.write_csv(dest/'archived_npg_matrix_region.csv',certificates)
    summaries=[]
    for rank in (2,8,32,64,100):
        for method in ('dense','truncated'):
            rr=[r for r in certificates if r['rank']==rank and r['method']==method]
            prefix=[r for r in rr if r['stage']==43]
            summaries.append(dict(rank=rank,method=method,all_stage_policies=len(rr),
                policies_in_region=sum(r['in_region'] for r in rr),
                whole_paths_in_region=sum(all(r['in_region'] for r in rr if r['seed']==seed) for seed in range(300,330)),
                terminal_prefix_in_region=sum(r['in_region'] for r in prefix),
                maximum_relative_P=max(r['P_relative_max'] for r in rr),
                terminal_prefix_maximum_relative_P=max(r['P_relative_max'] for r in prefix)))
    science.write_csv(dest/'archived_npg_matrix_region_summary.csv',summaries)
    science.atomic_json(dest/'source_policy_hashes.json',sources)
    science.atomic_json(dest/'summary.json',dict(status='PASS',new_learning_transitions=0,
        checked_policies=len(certificates),checked_paths=300,terminal_prefix_stage=43,
        matrix_region=summaries,fixed_policy_fits=fits,seconds=time.monotonic()-begin,
        job=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS',checked_policies=len(certificates),matrix_region=summaries,
        fixed_policy_fits=fits,seconds=time.monotonic()-begin)),flush=True)


if __name__=='__main__':main()
