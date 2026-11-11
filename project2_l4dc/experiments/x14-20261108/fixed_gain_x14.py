"""X14c saved calibration and X14d fixed-gain observations using X6a estimators."""
import argparse
import ast
import io
import json
import math
import os
import resource
import tarfile
import time
from pathlib import Path

import numpy as np

import admit_x14 as admission
import analyze_saved as original
import estimation as collector
import frozen_engine as engine
from virtual_task_store_v2 import TaskStore, file_sha, verify_archive


SOURCE = Path(__file__).resolve().parent
ROOT = admission.ROOT
PLAN = SOURCE / 'inputs.json'
GRID = (2048, 8192, 32768, 131072, 524288, 2097152, 4194304)
STEIN_N, CE_N = 2**22, 2**19


def inputs():
    engine.require_compute()
    plan = admission.read(PLAN)
    assert all(file_sha(SOURCE / p) == sha for p, sha in plan['source_hashes'].items())
    assert file_sha(original.__file__) == plan['source_hashes']['analyze_saved.py']
    assert file_sha(collector.__file__) == plan['source_hashes']['estimation.py']
    assert file_sha(engine.__file__) == plan['source_hashes']['frozen_engine.py']
    return plan


def pilot_input(plan, system, seed):
    task = (system-9101)*4 + seed-9601
    folder = SOURCE / f'pilot/task-{task}'
    receipt = admission.read(folder/'DONE.json')
    assert receipt['status']=='COMPLETE' and (receipt['system'],receipt['seed'])==(system,seed)
    assert receipt['estimator_sha256']==plan['source_hashes']['estimation.py']
    assert receipt['engine_sha256']==plan['source_hashes']['frozen_engine.py']
    assert file_sha(folder/'model.npz')==receipt['model_sha256']
    return folder, receipt


def truth(path):
    with np.load(path,allow_pickle=False) as raw:
        model = {key:raw[key] for key in ('A','B','Q','R','W','K0','P0')}
    assert all(matrix.shape==(60,60) and np.isfinite(matrix).all() for matrix in model.values())
    assert not model['K0'].any()
    return model


def targets(model):
    b,p = model['B'],model['P0']
    f = model['A'] - b@model['K0']
    g,z = b.T@p@b,-b.T@p@f
    return z,np.concatenate((g,z),axis=1)


def finish(item, stage, files, **details):
    output = ROOT / f'x14{item}-{stage}'
    for name, rows in files.items():
        original.write_csv(output/name,rows)
    result = dict(status='COMPLETE',item=item,stage=stage,job=os.environ['SLURM_ARRAY_JOB_ID'],
                  plan_sha256=file_sha(PLAN), driver_sha256=file_sha(__file__),
                  files={p.name:file_sha(p) for p in sorted(output.iterdir())}, **details)
    admission.write(output/'REPORT_DONE.json',result)
    print(json.dumps(result),flush=True)


def calibrate(plan):
    start=time.monotonic()
    out = ROOT/'x14c-pilot'
    out.mkdir()
    rows = []
    for system in (9101,9102):
        for seed in range(9601,9605):
            folder,receipt=pilot_input(plan,system,seed)
            z,joint=targets(truth(folder/'model.npz'))
            hashes={a['path']:a['sha256'] for a in receipt['artifacts']}
            assert set(hashes)=={f'Stein-{n}.npz' for n in GRID}
            prior={row['N']:row['rho_op'] for row in receipt['rows']}
            for N in GRID:
                path=folder/f'Stein-{N}.npz'
                assert file_sha(path)==hashes[path.name]
                with np.load(path,allow_pickle=False) as data:
                    g,estimate=data['G'],data['Z']
                psd,_=original.pi_pair(g,estimate)
                for alg,actual,target in [('NPG',estimate,z),('PI',psd,joint),
                                          ('PI_raw',np.concatenate((g,estimate),axis=1),joint)]:
                    result=original.metrics(actual,target)
                    assert result['identifiable'] and math.isfinite(result['rho_op'])
                    if alg=='NPG':
                        assert math.isclose(result['rho_op'],prior[N],rel_tol=1e-12,abs_tol=1e-12)
                    rows.append(dict(role='calibration',family='S',n=60,system=system,seed=seed,
                                     N=N,algorithm=alg,arm='dense',**result))
    systems,summary=original.summarize(rows)
    module=ast.parse(Path(original.__file__).read_bytes())
    function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='analyze')
    rule,= [n for n in ast.walk(function) if isinstance(n,ast.For) and ast.unparse(n.target)=='algorithm']
    calibration=[]
    context=dict(family='S',n=60,summary=summary,calibration=calibration,
                 config=dict(stein_blocks_by_n={'60':GRID},calibration_systems={'S':[9101,9102]}))
    exec(compile(ast.Module(body=[rule],type_ignores=[]),original.__file__,'exec'),context)
    assert {r['algorithm'] for r in calibration}=={'NPG','PI','PI_raw'}
    assert next(r for r in calibration if r['algorithm']=='NPG')['smallest_N']==2**21
    result=[dict(r,X12_N_cal=2**21,exceeds_X12_N_cal=(r['smallest_N'] or max(GRID))>2**21)
            for r in calibration if r['algorithm']!='NPG']
    finish('c','pilot',{'PI_calibration_n60.csv':result,'observations.csv':rows,
                       'system_summaries.csv':systems,'grid_summary.csv':summary},
           input_stein_estimates=56,observation_transitions=0,body_seconds=time.monotonic()-start,
           peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def spec_at(stage,index):
    system,seed=(9101+index,9601+index) if stage=='pilot' else (301+index//4,1701+index%4)
    return dict(role='timing' if stage=='pilot' else 'formal',family='S',n=60,system=system,seed=seed)


def observe(plan,stage,index):
    assert index==int(os.environ['SLURM_ARRAY_TASK_ID'])
    spec=spec_at(stage,index)
    system,seed=spec['system'],spec['seed']
    if stage=='pilot':
        folder,receipt=pilot_input(plan,system,seed)
        path=folder/'model.npz'
        model_sha=receipt['model_sha256']
    else:
        path=SOURCE/f'formal-models/n60-s{system}.npz'
        model_sha=plan['formal_models'][path.name]
    assert file_sha(path)==model_sha
    model=truth(path)
    prefix=f'x14d-{stage}-{index:03d}'
    store=TaskStore(ROOT/(prefix+'.tar'),ROOT/(prefix+'.jsonl'),ROOT/'virtual-fixed'/prefix,4*2**20)
    header=dict(spec,index=index,job=os.environ['SLURM_ARRAY_JOB_ID'],plan_sha256=file_sha(PLAN),
                source_sha256=file_sha(__file__),model_sha256=model_sha)
    store.save_json(store.root/'BEGIN.json',header)
    config=dict(H=16,nu=1,burn_blocks=16,ce_burn=512)
    start=time.monotonic()
    try:
        stein,=collector.stein_prefixes(model,[STEIN_N],engine.rng(20,60,60,system,seed,1),config)
        ce,=collector.ce_prefixes(model,[CE_N],engine.rng(10,60,60,system,seed),config)
        assert stein['N']==STEIN_N and ce['N']==CE_N
        assert all(np.isfinite(a).all() for a in (stein['Z'],stein['G'],ce['Bhat']))
        store.save_npz(store.root/'Stein.npz',**stein)
        store.save_npz(store.root/'CE.npz',**ce)
        store.save_npz(store.root/'model.npz',**model)
        cache=Path(os.environ['TMPDIR'])
        cache_paths=list(cache.rglob('*'))
        assert len(cache_paths)+1<=21 and sum(p.stat().st_size for p in cache_paths if p.is_file())<=64*2**20
        final=dict(header,status='COMPLETE',body_seconds=time.monotonic()-start,
                   peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   observation_transitions=(STEIN_N+17)*16+CE_N+512,automatic_retries=0)
        store.save_json(store.root/'TASK_DONE.json',final)
    finally:
        proof=store.close()
    if stage=='pilot':
        verify_archive(store.archive,proof['members'])
    proof.pop('journal_sha256')
    with store.journal.open('ab') as f:
        f.write((json.dumps(dict(proof,kind='TASK_FINAL',**final))+'\n').encode())
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(final),flush=True)


def read_estimate(tf,name):
    with np.load(io.BytesIO(tf.extractfile(name).read()),allow_pickle=False) as arrays:
        return {key:arrays[key] for key in arrays.files}


def estimate_report(plan):
    out=ROOT/'x14d-report'
    out.mkdir()
    rows=[]
    equivalence=[]
    for index in range(32):
        spec=spec_at('formal',index)
        prefix=ROOT/f'x14d-formal-{index:03d}'
        archive=prefix.with_suffix('.tar')
        final=json.loads(prefix.with_suffix('.jsonl').read_bytes().splitlines()[-1])
        assert final['status']=='COMPLETE' and final['kind']=='TASK_FINAL'
        assert all(final[k]==v for k,v in spec.items()) and final['index']==index
        assert file_sha(archive)==final['archive_sha256'] and final['plan_sha256']==file_sha(PLAN)
        assert final['model_sha256']==plan['formal_models'][f'n60-s{spec["system"]}.npz']
        verify_archive(archive,final['members'])
        with tarfile.open(archive,'r') as tf:
            model=read_estimate(tf,'model.npz')
            stein=read_estimate(tf,'Stein.npz')
            ce=read_estimate(tf,'CE.npz')
        k,r=model['K0'],model['R']
        z,joint=targets(model)
        g,estimate=stein['G'],stein['Z']
        dense_pi,trunc_pi=original.pi_pair(g,estimate)
        reference=engine.actor_learner(k,r,g,estimate,'truncated',2,'PI',0.)
        candidate=np.linalg.solve(r+trunc_pi[:,:60],trunc_pi[:,:60]@k-trunc_pi[:,60:])
        error=float(np.linalg.norm(reference-candidate)/max(1.,np.linalg.norm(reference)))
        assert error<1e-10
        equivalence.append(error)
        b=ce['Bhat']
        pairs=[('NPG',estimate,engine.trunc(estimate,2),z,STEIN_N),
               ('PI',dense_pi,trunc_pi,joint,STEIN_N),
               ('CE',b,engine.trunc(b,2),model['B'],CE_N)]
        for alg,dense,truncated,target,N in pairs:
            d,t=original.metrics(dense,target),original.metrics(truncated,target)
            ratio=d['relative_error']/t['relative_error'] if t['relative_error'] else math.inf
            for arm,result in [('dense',d),('truncated',t)]:
                rows.append(dict(spec,N=N,algorithm=alg,arm=arm,paired_error_ratio=ratio,
                                 actual_transitions=(N+17)*16 if alg!='CE' else N+512,**result))
    systems,summary=original.summarize(rows)
    assert len(summary)==6 and len(rows)==192 and all(r['finite_observations']==32 for r in summary)
    finish('d','report',{'estimate_accuracy_n60.csv':summary,'observations.csv':rows,'system_summaries.csv':systems},
           observation_transitions=0,formal_pairs=32,max_actor_PI_processing_difference=max(equivalence))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['calibration','pilot','formal','report'])
    args=parser.parse_args()
    plan=inputs()
    if args.mode=='calibration':
        calibrate(plan)
    elif args.mode=='report':
        estimate_report(plan)
    else:
        observe(plan,args.mode,int(os.environ['SLURM_ARRAY_TASK_ID']))
