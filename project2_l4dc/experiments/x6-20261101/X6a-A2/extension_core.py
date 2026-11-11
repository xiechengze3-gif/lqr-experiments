"""Proposed pilot-only design calibration. Do not run before Claude ACCEPTED.

No noisy actor, truncated estimate, formal-system performance or CE readout is
used. S/n36 continues exact X6a sufficient statistics/RNG, without reburning.
The population R2 check consumes zero simulated transitions.
"""
from __future__ import annotations
import argparse
import json
import os
import time
from pathlib import Path
import numpy as np
import frozen_engine as e
import estimation

BASE=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101')


def resume(s,snapshot,random,old_N,prefixes,H=16):
    n=s['B'].shape[0];k=s['K0'];nu=1.
    f=np.ascontiguousarray(s['A']-s['B']@k)
    cost=s['Q']+k.T@s['R']@k;prepared=e.prepare(f,s['B'],H)
    x=snapshot['x'].copy();previous=float(snapshot['previous'])
    gram=snapshot['gram'].copy();cross=snapshot['cross'].copy()
    curvature=snapshot['curvature'].copy();done=old_N
    for stop in prefixes:
        assert stop>done and stop%256==0
        while done<stop:
            count=min(256,stop-done)
            pulses=nu*random.normal(size=(count,n));noise=random.normal(size=(count,H,n))
            x,starts,ys=e.pulse_batch(f,s['B'],cost,x,pulses,noise,prepared)
            delta=np.diff(np.r_[previous,ys]);previous=ys[-1]
            labels=-pulses*delta[:,None]/(2*nu**2)
            gram+=starts.T@starts;cross+=labels.T@starts
            curvature+=((pulses*delta[:,None]).T@pulses
                         -nu**2*delta.sum()*np.eye(n))/(2*nu**4)
            done+=count
        g=curvature/done
        yield dict(N=done,x=x.copy(),G=(g+g.T)/2,Z=e.fit_model(gram,cross),
            gram=gram.copy(),cross=cross.copy(),curvature=curvature.copy(),
            previous=np.array(previous),rng_state=json.dumps(random.bit_generator.state,sort_keys=True))


def resume_equivalence():
    s=estimation.model('S',36,9101)
    random=e.rng(20,36,36,9101,9703,1)
    first=next(estimation.stein_prefixes(s,[1024],random,dict(H=16,nu=1.,burn_blocks=16)))
    restored=e.rng(20,36,36,9101,9703,1)
    restored.bit_generator.state=json.loads(first['rng_state'])
    item=next(resume(s,first,restored,1024,[2048]))
    other=e.rng(20,36,36,9101,9703,1)
    x,g,z=e.collect(s,s['K0'],np.zeros(36),2048,other,dict(H=16,nu=1.,burn_blocks=16))
    assert np.array_equal(x,item['x']) and np.array_equal(g,item['G']) and np.array_equal(z,item['Z'])
    assert item['rng_state']==json.dumps(other.bit_generator.state,sort_keys=True)
    return dict(status='PASS_BITWISE',old_N=1024,new_N=2048,
                additional_validation_transitions=66080)


def extend_n36(config,out):
    rows=[];additional=0
    for index in range(32,40):
        folder=BASE/'X6a/formal'/('task-'+str(index))/'S-n36'
        receipt=json.loads((folder/'receipt.json').read_text())
        spec=receipt['spec']
        assert spec['role']=='calibration' and spec['family']=='S' and spec['n']==36
        assert spec['system'] in [9101,9102] and spec['seed'] in [9601,9602,9603,9604]
        assert receipt['source_sha256']==e.sha(estimation.__file__)
        assert receipt['engine_sha256']==e.sha(e.__file__)
        assert receipt['config_sha256']==config['X6a_config_sha256']
        artifact=next(a for a in receipt['artifacts'] if a['path']=='Stein-524288.npz')
        path=folder/artifact['path'];assert e.sha(path)==artifact['sha256']
        assert e.sha(folder/'model.npz')==receipt['model_sha256']
        with np.load(folder/'model.npz') as truth:
            s={key:truth[key].copy() for key in ['A','B','Q','R','W','K0','P0']}
        with np.load(path) as archive:snapshot={key:archive[key].copy() for key in archive.files}
        random=e.rng(20,36,36,spec['system'],spec['seed'],1)
        random.bit_generator.state=json.loads(artifact['rng_state'])
        target=-s['B'].T@s['P0']@(s['A']-s['B']@s['K0'])
        sigma2=float(np.linalg.svd(target,compute_uv=False)[1])
        for item in resume(s,snapshot,random,524288,config['n36_extension_grid']):
            N=item.pop('N');rng_state=item.pop('rng_state')
            dest=out/('s'+str(spec['system'])+'-seed'+str(spec['seed'])+'-N'+str(N)+'.npz')
            np.savez_compressed(dest,**item)
            rows.append(dict(system=spec['system'],seed=spec['seed'],N=N,
                rho_op=float(np.linalg.norm(item['Z']-target,2)/sigma2),
                source_prefix_sha256=artifact['sha256'],archive_sha256=e.sha(dest),
                archive=dest.name,rng_state=rng_state,
                additional_transitions=(N-524288)*16))
        additional+=(max(config['n36_extension_grid'])-524288)*16
    summary=[]
    for N in config['n36_extension_grid']:
        medians=[float(np.median([r['rho_op'] for r in rows if r['system']==system and r['N']==N]))
                 for system in [9101,9102]]
        assert all(sum(r['system']==system and r['N']==N for r in rows)==4 for system in [9101,9102])
        summary.append(dict(N=N,rho_op_median=float(np.median(medians)),system_seed_medians=medians))
    selected=next((r['N'] for r in summary if r['rho_op_median']<=1),None)
    return dict(rows=rows,summary=summary,selected_base=selected,
                additional_transitions=additional,
                criterion='median_of_two_pilot_system_seed_medians<=1',
                formal_data_used=False,truncated_readout=False)

