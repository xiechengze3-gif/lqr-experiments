"""Population NPG diagnostics: distinguish finite-update error from noise.

True quantities are used only in this separately labeled reference, never by
the sampled learner to choose step size, rank, schedule, or output.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from adaptive_rank_run import make_system, identity, atomic_json
from dense_scaling import evaluate, targets, trunc


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    cfg=json.loads(a.manifest.read_text())
    rows=[]
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        for task in cfg['tasks']:
            if task['trial_seed']!=0: continue
            s,sysdiag=make_system(task,cfg)
            for finite in (False,True):
                for method in ('dense','known_rank'):
                    k=s['K0'].copy()
                    for stage in range(257):
                        quality,pvalue=evaluate(s,k)
                        if stage <= len(cfg['schedule']) or stage in (32,64,128,256):
                            rows.append(dict(task,finite_horizon=finite,method=method,
                                stage=stage,eta=cfg['npg_eta'],**quality))
                        if not quality['stable'] or stage==256: break
                        truth=targets(s,k,cfg['horizon'],pvalue)
                        z=truth['ZH' if finite else 'Z']
                        if method=='known_rank': z=trunc(z,task['r'])
                        k=k-cfg['npg_eta']*(s['R']@k+z)
    atomic_json(a.output,dict(identity=identity(a.manifest),records=rows,
        diagnostic_only=True,sampled_learner_access=False,
        description='Exact/finite-H reference at matching six updates and longer fixed iterations.'))
    print(json.dumps(dict(status='COMPLETE',records=len(rows),output=str(a.output))))


if __name__=='__main__':
    main()
