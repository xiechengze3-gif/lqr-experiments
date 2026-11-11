"""Post-hoc exact-gradient continuation, separate from empirical sample counts.

Starts at saved noisy endpoints; never changes the reported learning trajectories
or Nhat. Uses true dynamics exclusively as an offline optimization diagnostic.
"""
import argparse
import csv
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
import rank_sweep100 as e
from rank_sweep100_report import csv_write, wilson


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--updates',type=int,default=16)
    p.add_argument('--reuse-checkpoints',action='store_true')
    a=p.parse_args();out=a.output
    cfg=e.read(out/'resolved_config.json');verification=e.read(out/'verification.json')
    epsilon=verification['epsilon'];rows=[];systems={}
    if a.reuse_checkpoints:
        with (out/'report-confirm'/'endpoint_oracle_all_checkpoints.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows=list(csv.DictReader(stream))
        for r in rows:
            for key in ('rank','seed','extra_exact_updates'):r[key]=int(r[key])
            for key in ('gap','rho'):r[key]=float(r[key])
            r['stable']=r['stable']=='True'
        observed={(r['rank'],r['seed'],r['source_method'],r['extra_exact_updates']) for r in rows}
        planned={(rank,seed,method,step) for rank in cfg['ranks'] for seed in cfg['confirm_seeds']
                 for method in ('dense','truncated') for step in range(a.updates+1)}
        assert observed==planned and len(rows)==len(planned) and all(r['stable'] for r in rows)
    for rank in ([] if a.reuse_checkpoints else cfg['ranks']):
        with np.load(out/'systems'/f'r{rank:03d}.npz',allow_pickle=False) as z:
            systems[rank]={key:z[key].copy() for key in ('A','B','Q','R','W','K0','Kstar','Jstar','initial_gap')}
        for seed in cfg['confirm_seeds']:
            raw=e.read(out/'raw'/f'npg-r{rank:03d}-s{seed:04d}.json')
            path=out/'policies'/f'npg-r{rank:03d}-s{seed:04d}.npz'
            assert e.sha(path)==raw['policy_sha256']
            with np.load(path,allow_pickle=False) as arrays:
                endpoints={method:arrays[method][-1].copy() for method in ('dense','truncated')}
            for method,k in endpoints.items():
                s=systems[rank]
                for step in range(a.updates+1):
                    q,pvalue=e.evaluate(s,k)
                    assert q['stable'],'Offline exact continuation became unstable'
                    if step==0:
                        saved=next(r for r in raw['records'] if r['method']==method and r['stage']==len(e.schedule(cfg)))
                        np.testing.assert_allclose(q['gap'],saved['gap'],atol=2e-8)
                    rows.append(dict(rank=rank,seed=seed,source_method=method,extra_exact_updates=step,
                                     gap=q['gap'],stable=q['stable'],rho=q['rho']))
                    if step<a.updates:
                        z=-s['B'].T@pvalue@(s['A']-s['B']@k)
                        k=e.npg_update(k,z,'dense',cfg['eta'],rank)
        print(f'Endpoint oracle rank {rank} complete',flush=True)
    summary=[]
    for rank in cfg['ranks']:
        for method in ('dense','truncated'):
            for eps in (epsilon,epsilon/2):
                group=[r for r in rows if r['rank']==rank and r['source_method']==method]
                for step in range(a.updates+1):
                    current=[r for r in group if r['extra_exact_updates']==step]
                    count=int(sum(r['gap']<=eps for r in current));n=len(current)
                    lo,hi=wilson(count,n)
                    summary.append(dict(rank=rank,source_method=method,epsilon=eps,extra_exact_updates=step,
                        successes=count,seeds=n,success_rate=count/n,success_ci95_low=lo,success_ci95_high=hi,
                        gap_median=float(np.median([r['gap'] for r in current]))))
    csv_write(out/'report-confirm'/'endpoint_oracle_all_checkpoints.csv',rows)
    csv_write(out/'report-confirm'/'endpoint_oracle_success.csv',summary)
    thresholds=[]
    for rank in cfg['ranks']:
        for method in ('dense','truncated'):
            for eps in (epsilon,epsilon/2):
                group=[r for r in summary if r['rank']==rank and r['source_method']==method and r['epsilon']==eps]
                hit=next((r['extra_exact_updates'] for r in group if r['success_rate']>=.9),None)
                thresholds.append(dict(rank=rank,source_method=method,epsilon=eps,
                    extra_exact_updates_90=hit,max_extra_exact_updates=a.updates,
                    endpoint_successes=group[-1]['successes'],seeds=group[-1]['seeds']))
    csv_write(out/'report-confirm'/'endpoint_oracle_thresholds.csv',thresholds)
    e.atomic_json(out/'endpoint_oracle_diagnostic.json',dict(status='PASS',post_hoc=True,
        new_learning_primitive_transitions=0,changes_empirical_Nhat=False,eta=cfg['eta'],
        source_sha256=e.sha(__file__),updates=a.updates,thresholds=thresholds,
        reused_saved_diagnostic_checkpoints=a.reuse_checkpoints,
        note='True-model exact-gradient continuation from every fresh-seed saved noisy NPG endpoint. This separates deterministic local cleanup from continued stochastic learning; it is not a sampled-algorithm attainment claim.'))


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
