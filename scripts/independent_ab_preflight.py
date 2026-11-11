"""Compute-node validation of the independent unstable A/B construction."""
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

if os.environ.get('LQR_NUMBA_SITE'):
    sys.path.append(os.environ['LQR_NUMBA_SITE'])

import numpy as np
from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov
from threadpoolctl import threadpool_limits

from independent_ab_stabilizer import draw_plant, initial_gain


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def atomic(p, obj):
    temp = p.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, indent=2)+'\n')
    temp.replace(p)


def main():
    assert os.environ.get('SLURM_JOB_ID'), 'Numerics require a real compute allocation'
    out = Path(sys.argv[1]); (out/'systems').mkdir(parents=True, exist_ok=True)
    specs = [(n,4,seed) for n in (50,100) for seed in (5001,5002)]
    specs += [(500,r,5001) for r in (2,4,8,32,500)]
    rows=[]
    for n,rank,seed in specs:
        began=time.monotonic();stem=f'n{n:03d}-r{rank:03d}-s{seed}'
        try:
            a,b=draw_plant(n,rank,seed)
            k0,meta=initial_gain(a,b,rank,seed)
            # Task costs and optimum first enter AFTER the stabilizer is fixed.
            f0=a-b@k0;q=np.eye(n);cost=q+k0.T@k0
            p0=solve_discrete_lyapunov(f0.T,cost)
            pstar=solve_discrete_are(a,b,q,q)
            kstar=np.linalg.solve(q+b.T@pstar@b,b.T@pstar@a)
            residual=np.linalg.norm(p0-f0.T@p0@f0-cost)/np.linalg.norm(p0)
            assert residual<1e-8 and np.linalg.eigvalsh(p0)[0]>0
            gap=float(np.trace(p0-pstar));assert gap>0
            tails={}
            for h in (16,32,64,128,256):
                fh=np.linalg.matrix_power(f0,h)
                tails[str(h)]=float(np.linalg.norm(fh.T@p0@fh,2)/np.linalg.norm(p0,2))
            path=out/'systems'/(stem+'.npz')
            with path.open('wb') as handle:
                np.savez(handle,A=a,B=b,Q=q,R=q,W=q,K0=k0,F0=f0,P0=p0,
                         Pstar=pstar,Kstar=kstar,Jstar=float(np.trace(pstar)),initial_gap=gap)
            row=dict(n=n,rank=rank,seed=seed,status='PASS',**meta,
                     initial_gap=gap,J0=float(np.trace(p0)),Jstar=float(np.trace(pstar)),
                     lyapunov_relative_residual=float(residual),finite_H_value_tail=tails,
                     source_sha256=sha(Path(__file__).with_name('independent_ab_stabilizer.py')),
                     A_array_sha256=hashlib.sha256(a.tobytes()).hexdigest(),
                     B_array_sha256=hashlib.sha256(b.tobytes()).hexdigest(),
                     system_sha256=sha(path),system_file=str(path),
                     A_B_independent_by_construction=True,seconds=time.monotonic()-began)
        except Exception as err:
            row=dict(n=n,rank=rank,seed=seed,status='FAIL',error=repr(err),seconds=time.monotonic()-began)
        rows.append(row)
        atomic(out/'construction.json',dict(status='RUNNING',systems=rows,
               job=os.environ['SLURM_JOB_ID'],host=os.uname().nodename))
        print(json.dumps(row),flush=True)
    atomic(out/'construction.json',dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',
           systems=rows,job=os.environ['SLURM_JOB_ID'],host=os.uname().nodename,
           peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           paths={k:os.environ.get(k) for k in ('TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR')}))


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
