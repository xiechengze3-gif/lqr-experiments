"""Prepare the already verified common-certificate family; benchmark CE."""
import json
import os
from pathlib import Path
import resource
import time

import numpy as np


def prepare(cfg,ident,e,engine):
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    assert cfg['sigma']==cfg['supplied_common_bounds']['nu']==2.
    if (out/'preflight.json').exists():
        assert e.read(out/'preflight.json')['identity']==ident;return
    source=Path(cfg['construction_output']);proof_path=source/'verification.json'
    assert e.sha(proof_path)==cfg['construction_verification_sha256']
    proof=e.read(proof_path);assert proof['status']=='PASS'
    assert proof['A_drawn_independently_of_B'] and proof['K0_F0_P0_common_across_all_ranks']
    assert not proof['initialization_uses_Kstar'] and not proof['initial_gap_matching']
    common=None;checks=[];hashes={}
    for rank in cfg['ranks']:
        meta=next(r for r in proof['rows'] if r['rank']==rank)
        p=source/'systems'/f'r{rank:03d}.npz';assert e.sha(p)==meta['system_sha256']
        with np.load(p,allow_pickle=False) as data:
            s={k:data[k].copy() for k in ('A','B','Q','R','W','K0','F0','P0')}
        for name in ('Q','R','W'):np.testing.assert_array_equal(s[name],np.eye(cfg['n']))
        if common is None:common={k:s[k].copy() for k in ('A','Q','R','W','K0','F0','P0')}
        for k in common:np.testing.assert_array_equal(s[k],common[k])
        assert np.linalg.eigvalsh(s['P0'])[-1]<cfg['supplied_common_bounds']['p_0']
        np.testing.assert_allclose(s['A']-s['B']@s['K0'],s['F0'],atol=1e-12,rtol=0)
        # The initial controller is fixed and hashed before the task optimum enters.
        ks,ps=e.dare(s['A'],s['B'],s['Q'],s['R'])
        s.update(Kstar=ks,Pstar=ps,Jstar=float(np.trace(s['W']@ps)),
            initial_gap=float(np.trace(s['W']@(s['P0']-ps))))
        assert s['initial_gap']>0
        q,_=e.evaluate(s,s['K0']);assert q['stable']
        independent=engine.performance_gap(s,s['K0'])[0]
        assert abs(independent-s['initial_gap'])<2e-7*max(1.,s['initial_gap'])
        dest=out/'systems'/f'r{rank:03d}.npz';e.save_npz(dest,**s);hashes[str(rank)]=e.sha(dest)
        checks.append(dict(meta,initial_gap=s['initial_gap'],J0=q['cost'],Jstar=s['Jstar'],
            supplied_p0=cfg['supplied_common_bounds']['p_0'],source_system_sha256=e.sha(p)))
    e.atomic_json(out/'verification.json',dict(status='PASS',identity=ident,systems=checks,system_hashes=hashes,
        supplied_common_bounds=cfg['supplied_common_bounds'],shared_matrices=list(common),
        A_independent_of_B=True,source_verification_sha256=e.sha(proof_path),initialization_uses_Kstar=False))
    e.atomic_json(out/'resolved_config.json',dict(cfg,identity=ident))
    # Validate the joint regression label in a fully excited, noiseless diagnostic.
    full=engine.load_system(cfg,cfg['n']);n=cfg['n'];pulse,_=engine.rngs(cfg,9900)
    f=np.ascontiguousarray(full['A']-full['B']@full['K0'])
    _,design,response=e.ce_chunk(f,full['B'],full['K0'],np.zeros(n),
        cfg['sigma']*pulse.normal(size=(2048,n)),np.zeros((2048,n)))
    theta=np.concatenate((full['A'],full['B']),axis=1)
    fitted=np.linalg.lstsq(design,response,rcond=None)[0].T
    label_error=float(np.max(np.abs(design@theta.T-response)))
    fit_error=float(np.max(np.abs(fitted-theta)));assert label_error<1e-11 and fit_error<1e-10
    benchmarks=[];began=time.monotonic()
    for rank in (cfg['ranks'][0],cfg['n']):
        before=time.monotonic();folder=out/'diagnostics'/f'benchmark-r{rank:03d}'
        result=engine.task(cfg,ident,rank,9900,cfg['preflight_budgets'],folder)
        raw=e.read(folder/'raw'/f'ce-r{rank:03d}-s9900.json')
        benchmarks.append(dict(rank=rank,seconds=time.monotonic()-before,
            physical_transitions=result['physical_transitions'],timings=raw['timings_this_invocation']))
    rank=cfg['ranks'][0]
    for label,budgets in (('continuous',[2048,8192]),('resumed',[2048]),('resumed',[2048,8192])):
        engine.task(cfg,ident,rank,9901,budgets,out/'diagnostics'/label)
    aa=e.read(out/'diagnostics/continuous/raw'/f'ce-r{rank:03d}-s9901.json')
    bb=e.read(out/'diagnostics/resumed/raw'/f'ce-r{rank:03d}-s9901.json')
    assert aa['records']==bb['records']
    with np.load(out/'diagnostics/continuous/checkpoints'/f'ce-r{rank:03d}-s9901.npz') as x,np.load(out/'diagnostics/resumed/checkpoints'/f'ce-r{rank:03d}-s9901.npz') as y:
        for name in ('x','gram','cross'):np.testing.assert_array_equal(x[name],y[name])
    e.atomic_json(out/'preflight.json',dict(status='PASS',identity=ident,benchmarks=benchmarks,
        common_initialization_checks=checks,checkpoint_resume_bitwise=True,
        noiseless_label_max_error=label_error,noiseless_model_max_error=fit_error,
        benchmark_maximum_budget=max(cfg['preflight_budgets']),seconds=time.monotonic()-began,
        peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,job=os.environ['SLURM_JOB_ID'],
        paths={k:os.environ.get(k) for k in ('TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR')}))
    print(json.dumps(dict(status='PASS',benchmarks=benchmarks,noiseless_fit_error=fit_error)),flush=True)
