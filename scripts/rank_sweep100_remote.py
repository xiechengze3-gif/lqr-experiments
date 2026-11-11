"""Slurm-only entrypoint; exact frozen system artifacts from the local preflight."""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
# Preserve the project environment first; use existing cluster packages only
# for missing pure-Python/runtime modules (the established Numba fallback).
if os.environ.get('LQR_NUMBA_SITE'):
    sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from threadpoolctl import threadpool_limits
import rank_sweep100 as e


def load_system(cfg,rank):
    path=e.ROOT/'system_inputs'/f'r{rank:03d}.npz'
    assert e.sha(path)==cfg['system_artifact_sha256'][str(rank)]
    with np.load(path,allow_pickle=False) as a:
        private={name:a[name].copy() for name in ('U','V','F0','P0','T')}
        s={name:(float(a[name]) if a[name].ndim==0 else a[name].copy()) for name in a.files if name not in private}
    return s,private


def bootstrap(cfg,manifest):
    assert os.environ.get('SLURM_JOB_ID'),'Remote numerical work requires a real Slurm compute allocation'
    for name,path in [('NUMBA_CACHE_DIR',str(Path(cfg['cache'])/'numba')),
                      ('MPLCONFIGDIR',str(Path(cfg['cache'])/'matplotlib')),('TMPDIR',cfg['temp'])]:
        assert os.environ.get(name)==path,(name,path)
        Path(path).mkdir(parents=True,exist_ok=True)
    e.SOURCES+=['scripts/rank_sweep100_remote.py']
    e.system=load_system
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    ident=e.identity(cfg)
    return out,ident


def freeze(cfg,manifest,out,ident):
    frozen=out/'frozen';frozen.mkdir(exist_ok=True)
    if (frozen/'identity.json').exists():assert e.read(frozen/'identity.json')==ident
    else:
        for source in e.SOURCES+['scripts/rank_sweep100_report.py']:
            dest=frozen/source;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(e.ROOT/source,dest)
        shutil.copytree(e.ROOT/'system_inputs',frozen/'system_inputs',dirs_exist_ok=True)
        shutil.copyfile(manifest,frozen/'config.json');e.atomic_json(frozen/'identity.json',ident)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['verify','benchmark','task','report'])
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--phase',default='pilot',choices=['pilot','confirm'])
    p.add_argument('--task-id',type=int);p.add_argument('--route',default='npg',choices=['ce','npg'])
    a=p.parse_args();cfg=e.read(a.manifest);out,ident=bootstrap(cfg,a.manifest)
    with threadpool_limits(limits=1):
        if a.mode=='verify':
            freeze(cfg,a.manifest,out,ident);e.verify(cfg,out,ident)
        elif a.mode=='benchmark':
            s,_=load_system(cfg,100); start=time.monotonic()
            sample=e.stein_collect(s,s['K0'],np.zeros(cfg['n']),cfg['benchmark_blocks'],*e.innovations(cfg,0,9001),cfg)
            estimate_seconds=time.monotonic()-start
            true=e.targets(s,s['K0'],cfg['horizon'])['ZH']
            err=float(np.linalg.norm(sample[1]-true)**2)
            start=time.monotonic();f=np.ascontiguousarray(s['A']-s['B']@s['K0'])
            p_rng,n_rng=e.innovations(cfg,1,9001)
            e.ce_chunk(f,s['B'],s['K0'],np.zeros(cfg['n']),p_rng.normal(size=(32768,cfg['n'])),n_rng.normal(size=(32768,cfg['n'])))
            import resource
            result=dict(status='PASS',npg_blocks=cfg['benchmark_blocks'],npg_seconds=estimate_seconds,
                        npg_Z_error_fro2=err,ce_transitions=32768,ce_seconds=time.monotonic()-start,
                        peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        slurm_job_id=os.environ['SLURM_JOB_ID'],config=cfg)
            e.atomic_json(out/'remote_benchmark.json',result);print(json.dumps(result),flush=True)
        elif a.mode=='task':
            assert e.read(out/'verification.json')['identity']==ident
            seeds=cfg[a.phase+'_seeds'];jobs=[(rank,seed) for seed in seeds for rank in cfg['ranks']]
            rank,seed=jobs[a.task_id]
            result=e.worker(cfg,rank,seed,str(out),ident,a.route)
            e.atomic_json(out/'task_receipts'/f'{a.phase}-{a.route}-{a.task_id:03d}.json',
                          dict(result,slurm_job_id=os.environ['SLURM_JOB_ID'],task_id=a.task_id,phase=a.phase))
            print(json.dumps(result),flush=True)
        else:
            import rank_sweep100_report as report
            report.make_report(cfg,a.phase)


if __name__=='__main__':main()
