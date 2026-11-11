"""Evaluate the fixed X12 pilot streams at the newly registered B* point."""
import argparse
import io
import json
import os
import resource
import tarfile
import time

import numpy as np

import fixed_gain_x14 as fixed
from virtual_task_store_v2 import TaskStore, file_sha, verify_archive


R=fixed.ROOT
B=3276800
REFERENCE=2**21


def collect(plan,index):
    assert index==int(os.environ['SLURM_ARRAY_TASK_ID']) and 0<=index<8
    system,seed=9101+index//4,9601+index%4
    folder,receipt=fixed.pilot_input(plan,system,seed)
    model=fixed.truth(folder/'model.npz')
    prefix=R/f'x14c-bstar-{index:03d}'
    store=TaskStore(prefix.with_suffix('.tar'),prefix.with_suffix('.jsonl'),R/'virtual-bstar'/prefix.name,4*2**20)
    header=dict(system=system,seed=seed,index=index,job=os.environ['SLURM_ARRAY_JOB_ID'],
                driver_sha256=file_sha(__file__),prior_model_sha256=receipt['model_sha256'])
    store.save_json(store.root/'BEGIN.json',header)
    start=time.monotonic()
    try:
        original,new=fixed.collector.stein_prefixes(model,[REFERENCE,B],fixed.engine.rng(20,60,60,system,seed,1),
                                                    dict(H=16,nu=1,burn_blocks=16))
        old=folder/f'Stein-{REFERENCE}.npz'
        expected=next(a['sha256'] for a in receipt['artifacts'] if a['path']==old.name)
        assert file_sha(old)==expected and original['N']==REFERENCE and new['N']==B
        with np.load(old,allow_pickle=False) as saved:
            for name in ('x','G','Z','gram','cross','curvature','previous'):
                assert np.allclose(original[name],saved[name],rtol=1e-12,atol=1e-12),name
            assert original['rng_state']==str(saved['rng_state'])
        store.save_npz(store.root/'Stein-Bstar.npz',**new)
        final=dict(header,status='COMPLETE',body_seconds=time.monotonic()-start,
                   observation_transitions=(B+17)*16,existing_rng_stream=True,
                   peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,automatic_retries=0)
        assert final['peak_RSS_KiB']<=.8*2*1024**2
        store.save_json(store.root/'DONE.json',final)
    finally:
        proof=store.close()
    proof.pop('journal_sha256')
    with store.journal.open('ab') as f:
        f.write((json.dumps(dict(proof,kind='TASK_FINAL',**final))+'\n').encode())
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(final),flush=True)


def readout(plan):
    import csv

    out=R/'x14c-report'
    out.mkdir()
    rows=[]
    for i in range(8):
        system,seed=9101+i//4,9601+i%4
        prefix=R/f'x14c-bstar-{i:03d}'
        proof=json.loads(prefix.with_suffix('.jsonl').read_bytes().splitlines()[-1])
        archive=prefix.with_suffix('.tar')
        assert proof['kind']=='TASK_FINAL' and proof['status']=='COMPLETE'
        assert proof['existing_rng_stream'] and (proof['system'],proof['seed'],proof['index'])==(system,seed,i)
        assert file_sha(archive)==proof['archive_sha256']
        verify_archive(archive,proof['members'])
        folder,receipt=fixed.pilot_input(plan,system,seed)
        assert receipt['model_sha256']==proof['prior_model_sha256']
        z,joint=fixed.targets(fixed.truth(folder/'model.npz'))
        with tarfile.open(archive,'r') as tf:
            with np.load(io.BytesIO(tf.extractfile('Stein-Bstar.npz').read()),allow_pickle=False) as data:
                assert int(data['N'])==B
                g,estimate=data['G'],data['Z']
        psd,_=fixed.original.pi_pair(g,estimate)
        for alg,actual,target in [('NPG',estimate,z),('PI',psd,joint),
                                  ('PI_raw',np.concatenate((g,estimate),axis=1),joint)]:
            metric=fixed.original.metrics(actual,target)
            assert metric['identifiable'] and np.isfinite(metric['rho_op'])
            rows.append(dict(role='calibration',family='S',n=60,system=system,seed=seed,N=B,
                             algorithm=alg,arm='dense',**metric))
    per_system,summary=fixed.original.summarize(rows)
    old=R/'x14c-pilot'
    prior=json.loads((old/'REPORT_DONE.json').read_bytes())
    path=old/'PI_calibration_n60.csv'
    assert file_sha(path)==prior['files'][path.name]
    with path.open(newline='',encoding='utf-8') as f:
        selected=list(csv.DictReader(f))
    selected.append(dict(selected[0],algorithm='NPG',smallest_N=REFERENCE,status='QUALIFIED',censored_above_N='',
                         exceeds_X12_N_cal=False))
    result=[]
    for original in selected:
        row,=[r for r in summary if r['algorithm']==original['algorithm']]
        assert row['rho_op_systems']==2 and row['full_observations']==8
        rho=row['rho_op_median']
        result.append(dict(original,Bstar_blocks=B,Bstar_rho_op_median=rho,Bstar_qualifies=rho<=1))
    fixed.finish('c','report',{'PI_calibration_n60.csv':result,'Bstar_observations.csv':rows,
                               'Bstar_system_summaries.csv':per_system},observation_transitions=0,
                 original_PI_rule_report=prior['job'],Bstar_pilot_streams=8)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['bstar','report'])
    args=parser.parse_args()
    inputs=fixed.inputs()
    if args.stage=='bstar':
        collect(inputs,int(os.environ['SLURM_ARRAY_TASK_ID']))
    else:
        readout(inputs)
