"""Preparation shared by the independent unstable A/B comparison studies."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import time

import numpy as np
from scipy.linalg import solve_discrete_lyapunov

from independent_ab_stabilizer import draw_plant, initial_gain


def ce_prepare(cfg, ident, e, engine):
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    if (out/'preflight.json').exists():
        assert e.read(out/'preflight.json')['identity']==ident;return
    source=Path(cfg['construction_output']);proof=e.read(source/'construction.json')
    assert proof['status']=='PASS'
    checks=[];hashes={};common=None
    for rank in cfg['ranks']:
        meta=next(r for r in proof['systems'] if r['n']==cfg['n'] and r['rank']==rank)
        path=Path(meta['system_file']);assert e.sha(path)==meta['system_sha256']
        with np.load(path,allow_pickle=False) as arr:
            s={k:arr[k].item() if not arr[k].ndim else arr[k].copy() for k in arr.files}
        a,b,k0=s['A'],s['B'],s['K0']
        if common is None:common=a.copy()
        np.testing.assert_array_equal(a,common)
        q,_=e.evaluate(s,k0)
        assert q['stable'] and meta['rho_A']>1 and not meta['uses_Kstar']
        dest=out/'systems'/f'r{rank:03d}.npz';e.save_npz(dest,**s);hashes[str(rank)]=e.sha(dest)
        checks.append(dict(meta,rho_K0=q['rho'],J0=q['cost']))
    e.atomic_json(out/'verification.json',dict(status='PASS',identity=ident,systems=checks,
        system_hashes=hashes,A_is_common_across_ranks=True,A_independent_of_B_by_construction=True,
        initialization='stability-only Schur pole placement after drawing independent A/B'))
    e.atomic_json(out/'resolved_config.json',dict(cfg,identity=ident))
    benchmarks=[];began=time.monotonic()
    for rank in (cfg['ranks'][0],cfg['n']):
        before=time.monotonic();folder=out/'diagnostics'/f'benchmark-r{rank:03d}'
        result=engine.task(cfg,ident,rank,9000,cfg['preflight_budgets'],folder)
        raw=e.read(folder/'raw'/f'ce-r{rank:03d}-s9000.json')
        benchmarks.append(dict(rank=rank,seconds=time.monotonic()-before,
            physical_transitions=result['physical_transitions'],timings=raw['timings_this_invocation']))
    rank=cfg['ranks'][0]
    for label,budgets in (('continuous',[2048,8192]),('resumed',[2048]),('resumed',[2048,8192])):
        engine.task(cfg,ident,rank,9001,budgets,out/'diagnostics'/label)
    aa=e.read(out/'diagnostics/continuous/raw'/f'ce-r{rank:03d}-s9001.json')
    bb=e.read(out/'diagnostics/resumed/raw'/f'ce-r{rank:03d}-s9001.json')
    assert aa['records']==bb['records']
    with np.load(out/'diagnostics/continuous/checkpoints'/f'ce-r{rank:03d}-s9001.npz') as x, np.load(out/'diagnostics/resumed/checkpoints'/f'ce-r{rank:03d}-s9001.npz') as y:
        for name in ('x','gram','cross'):np.testing.assert_array_equal(x[name],y[name])
    e.atomic_json(out/'preflight.json',dict(status='PASS',identity=ident,benchmarks=benchmarks,
        stable_initialization_checks=checks,checkpoint_resume_bitwise=True,
        benchmark_maximum_budget=max(cfg['preflight_budgets']),seconds=time.monotonic()-began,
        peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,job=os.environ['SLURM_JOB_ID']))


def stein_prepare(cfg,ident,core,plant_path):
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    if (out/'preflight.json').exists():
        assert json.loads((out/'preflight.json').read_text())['identity']==ident;return
    source=Path(cfg['construction_output']);proof=json.loads((source/'construction.json').read_text())
    assert proof['status']=='PASS';systems=[]
    for n in cfg['dimensions']:
        for seed in cfg['pilot_system_seeds']+cfg['confirm_system_seeds']:
            path=plant_path(out,n,seed);path.parent.mkdir(exist_ok=True)
            if path.exists():
                meta=json.loads(path.with_suffix('.json').read_text());assert meta['identity']==ident
                assert meta['sha256']==core.sha(path);systems.append(meta);continue
            saved=next((r for r in proof['systems'] if r['n']==n and r['rank']==cfg['rank'] and r['seed']==seed),None)
            if saved:
                source_path=Path(saved['system_file']);assert core.sha(source_path)==saved['system_sha256']
                shutil.copyfile(source_path,path);meta=dict(saved)
            else:
                a,b=draw_plant(n,cfg['rank'],seed,cfg['A_radius'])
                k0,meta=initial_gain(a,b,cfg['rank'],seed)
                ks,ps=core.dare(a,b,np.eye(n),np.eye(n));f=a-b@k0
                p0=solve_discrete_lyapunov(f.T,np.eye(n)+k0.T@k0)
                gap=float(np.trace(p0-ps));assert gap>0
                with path.open('wb') as handle:
                    np.savez(handle,A=a,B=b,Q=np.eye(n),R=np.eye(n),W=np.eye(n),K0=k0,
                        Kstar=ks,Pstar=ps,Jstar=float(np.trace(ps)),P0=p0,initial_gap=gap)
                meta.update(n=n,rank=cfg['rank'],seed=seed,initial_gap=gap,
                    A_array_sha256=hashlib.sha256(a.tobytes()).hexdigest(),
                    B_array_sha256=hashlib.sha256(b.tobytes()).hexdigest())
            with np.load(path,allow_pickle=False) as stored:
                f=stored['A']-stored['B']@stored['K0'];p0=stored['P0']
                fh=np.linalg.matrix_power(f,cfg['H'])
                tail=float(np.linalg.norm(fh.T@p0@fh,2)/np.linalg.norm(p0,2))
            meta.update(identity=ident,sha256=core.sha(path),finite_H_value_tail=tail,H=cfg['H'])
            core.atomic_json(path.with_suffix('.json'),meta);systems.append(meta)
    benchmarks=[]
    for n in cfg['dimensions']:
        with np.load(plant_path(out,n,cfg['pilot_system_seeds'][0]),allow_pickle=False) as data:
            s={k:data[k].item() if not data[k].ndim else data[k].copy() for k in data.files}
        start=time.monotonic();count=8192
        d=list(core.collect_prefixes(s,s['K0'],np.zeros(n),[count],core.rng_for(2026102297,n),cfg['H'],cfg['burn'],cfg['sigma']))[-1]
        elapsed=time.monotonic()-start;before=time.monotonic()
        for method in cfg['methods']:
            g,z,_,_=core.v4_correct(d['G'],d['Z'],method,cfg['rank'],d['halves'])
            core.quality(s,core.greedy(s['K0'],s['R'],g,z))
        benchmarks.append(dict(n=n,N=count,collector_seconds=elapsed,
            seconds_per_block=elapsed/count,postprocess_seconds_for_methods=time.monotonic()-before))
    core.atomic_json(out/'preflight.json',dict(status='PASS',identity=ident,systems=systems,
        benchmarks=benchmarks,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        job=os.environ['SLURM_JOB_ID']))
    core.atomic_json(out/'resolved_config.json',dict(cfg,identity=ident))
