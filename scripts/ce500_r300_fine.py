"""Resolve the small rank300 CE sample advantage on a prospective fine grid."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['task','report']);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--phase',choices=['pilot','confirm'],required=True);p.add_argument('--task-id',type=int,default=0);a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    fine=json.loads(a.manifest.read_text());base_release=Path(fine['base_release']);sys.path[:0]=[str(base_release),str(base_release/'scripts')]
    import ce500_rank_extension as ext
    import numpy as np
    core=ext.core;e=core.e;engine=core.engine
    cfg=e.read(base_release/'configs/ce500_rank_extension_20261023.json');base_ident=ext.identity(cfg)
    assert e.read(Path(cfg['output'])/'preflight.json')['identity']==base_ident
    ident=dict(base_identity=base_ident,fine_config_sha256=hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
               fine_driver_sha256=e.sha(Path(__file__)),rank=300)
    out=Path(fine['output']);out.mkdir(parents=True,exist_ok=True)
    seeds=fine[a.phase+'_seeds']
    with core.threadpool_limits(1):
        if a.mode=='task':
            seed=seeds[a.task_id];engine.task(cfg,ident,300,seed,fine['budgets'],out)
            return
        s=engine.load_system(cfg,300);data=[];checked=ols=overlap=0;worst=0.
        for seed in seeds:
            stem=f'ce-r300-s{seed:04d}';raw=e.read(out/'raw'/(stem+'.json'))
            assert raw['identity']==ident and raw['budgets']==fine['budgets']
            assert raw['physical_transitions']==fine['budgets'][-1]+cfg['burn']
            for n in fine['budgets']:
                pair=[r for r in raw['records'] if r['ols_samples']==n]
                assert [r['method'] for r in pair]==['dense','truncated']
                path=out/pair[0]['policy_file'];assert e.sha(path)==pair[0]['policy_sha256']==pair[1]['policy_sha256']
                with np.load(path) as d: ks=[d['dense'],d['truncated']]
                for row,k in zip(pair,ks):
                    gap=engine.performance_gap(s,k)[0] if np.isfinite(k).all() else np.inf
                    assert bool(np.isfinite(gap))==row['stable']
                    if row['stable']:
                        err=abs(gap-row['gap']);worst=max(worst,err);assert err<2e-7*max(1.,gap)
                    checked+=1
                original=Path(cfg['output'])/'policies'/stem/f'n{n:09d}.npz'
                if original.exists():
                    with np.load(original) as d:
                        for name,k in zip(['dense','truncated'],ks):np.testing.assert_allclose(k,d[name],atol=1e-10,rtol=1e-10)
                    overlap+=1
            with np.load(out/'checkpoints'/(stem+'.npz')) as d:
                theta=np.linalg.solve((d['gram']+d['gram'].T)/2,d['cross'].T).T
            with np.load(out/'estimates'/(stem+'.npz')) as d:
                np.testing.assert_allclose(theta,np.concatenate([d['Ahat'],d['Bhat']],axis=1),atol=1e-12,rtol=0)
            ols+=1;data.append(raw)
        rows=[];requirements=[]
        for method in ['dense','truncated']:
            successes=[]
            for n in fine['budgets']:
                records=[next(r for r in d['records'] if r['method']==method and r['ols_samples']==n) for d in data]
                count=sum(r['stable'] and r['gap']<=.1 for r in records);successes.append(count)
                rows.append(dict(method=method,ols_samples=n,transitions=n+cfg['burn'],successes=count,seeds=len(seeds)))
            hits=[j for j in range(len(successes)) if all(x/len(seeds)>=.9 for x in successes[j:])]
            j=hits[0] if hits else None
            requirements.append(dict(method=method,sample_count=fine['budgets'][j]+cfg['burn'] if j is not None else None,
                lower_measured_budget=fine['budgets'][j-1]+cfg['burn'] if j else (0 if j==0 else fine['budgets'][-1]+cfg['burn']),
                censoring='right' if j is None else ('left' if j==0 else 'interval')))
        nd,nt=[r['sample_count'] for r in requirements]
        dest=out/('report-'+a.phase);dest.mkdir(exist_ok=True)
        core.write_csv(dest/'success_by_budget.csv',rows);core.write_csv(dest/'sample_complexity.csv',requirements)
        summary=dict(status='PASS',phase=a.phase,rank=300,absolute_target=.1,seeds=seeds,budgets=fine['budgets'],identity=ident,
                     audited_policies=checked,audited_OLS_fits=ols,maximum_gap_error=worst,matching_original_prefixes=overlap,
                     dense_samples=nd,truncated_samples=nt,sample_gain=nd/nt if nd and nt else None,requirements=requirements,
                     design='Fine grid chosen from pilot700/701; confirm800-829 fixed before fine sampling; same raw-coordinate engine and innovations')
        e.atomic_json(dest/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
