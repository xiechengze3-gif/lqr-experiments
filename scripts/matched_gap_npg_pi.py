"""Matched-gap experiment adapter. Existing NPG and full LSTD PI are unchanged."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from threadpoolctl import threadpool_limits,threadpool_info
import rank_sweep100 as e
import rank_sweep100_pi as pi

SOURCES=list(dict.fromkeys(pi.SOURCES+['scripts/matched_gap_npg_pi.py']))


def load(cfg,rank):
    return pi.load_system(cfg,rank),{}


def options(parent,route):
    c={k:v for k,v in parent.items() if k not in ('npg','pi','resources')}
    c.update(parent[route]);c.update(output=parent['output']+'/'+route,
        cache=parent['cache'],temp=parent['temp']+'/'+route)
    return c


def identity(cfg):
    return dict(config_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        sources={name:e.sha(ROOT/name) for name in SOURCES},
        matched_initial_gap=1.0,whitening=False)


def prepare(parent,manifest):
    out=Path(parent['output']);out.mkdir(parents=True,exist_ok=True)
    ident=identity(parent)
    if (out/'system_verification.json').exists():
        assert e.read(out/'system_verification.json')['identity']==ident;return
    shutil.copytree(ROOT,out/'frozen/release',ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
    checks=[];oracle=[]
    for rank in parent['ranks']:
        s,_=load(parent,rank);q,p=e.evaluate(s,s['K0'])
        assert q['stable'] and abs(q['gap']-1)<1e-10
        assert np.linalg.matrix_rank(s['B'],tol=1e-10)==rank
        f=s['A']-s['B']@s['K0']
        cert=float(np.max(abs(p-f.T@p@f-s['Q']-s['K0'].T@s['R']@s['K0'])))
        assert cert<1e-10
        checks.append(dict(rank=rank,**q,certificate_max_error=cert,
            system_sha256=parent['system_artifact_sha256'][str(rank)]))
        for kind in ('exact_npg','finite_H_npg','exact_pi'):
            k=s['K0'].copy();c=options(parent,'npg' if 'npg' in kind else 'pi')
            for stage in range(c['oracle_updates']+1):
                q,p=e.evaluate(s,k);assert q['stable']
                oracle.append(dict(rank=rank,kind=kind,stage=stage,**q))
                if kind=='exact_pi':
                    k=pi.update(s['B'].T@p@s['B'],s['B'].T@p@s['A'],s['R'],'dense',rank)
                else:
                    z=e.targets(s,k,c['horizon'],p)['Z' if kind=='exact_npg' else 'ZH']
                    kd=e.npg_update(k,z,'dense',c['eta'],rank)
                    np.testing.assert_allclose(kd,e.npg_update(k,z,'truncated',c['eta'],rank),atol=2e-12)
                    k=kd
            needed=len(e.schedule(c)) if 'npg' in kind else len(c['batch_schedule'])
            e.atomic_json(out/'oracle_progress.json',dict(status='in_progress',records=oracle))
            assert next(v for v in oracle if v['rank']==rank and v['kind']==kind and v['stage']==needed)['gap']<.025
    e.atomic_json(out/'oracle.json',dict(status='PASS',records=oracle))
    e.atomic_json(out/'system_verification.json',dict(status='PASS',identity=ident,checks=checks,
        matched_CE_source=parent['ce_source'],systems_copied_without_reserialization=True))
    for route in ('npg','pi'):
        c=options(parent,route);folder=Path(c['output']);folder.mkdir(exist_ok=True)
        e.atomic_json(folder/'resolved_config.json',dict(c,identity=identity(c)))
    e.atomic_json(out/'resolved_config.json',dict(parent,identity=ident,slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS',checks=checks)),flush=True)


def npg_preflight(parent):
    cfg=options(parent,'npg');out=Path(cfg['output']);ident=identity(cfg)
    proof=out/'verification.json'
    if proof.exists():assert e.read(proof)['identity']==ident;return
    s,_=load(cfg,8);mini=dict(cfg,burn=7)
    old=e.stein_collect(s,s['K0'],np.zeros(100),256,*e.innovations(cfg,0,9901),mini,True)
    new=e.stein_collect(s,s['K0'],np.zeros(100),256,*e.innovations(cfg,0,9901),mini,False)
    for i in (0,1):np.testing.assert_allclose(old[i],new[i],atol=2e-10,rtol=2e-10)
    assert old[2]==new[2]==1035
    small=dict(cfg,burn=7,schedule_segments=[[1024,1],[2048,1]],eta=.005)
    reference=out/'diagnostics/uninterrupted';resumed=out/'diagnostics/resumed'
    e.npg_task(small,8,9902,reference,ident)
    saved=e.save_npz;interrupted=[False]
    def fault(path,**items):
        saved(path,**items)
        if Path(path).parent.name=='checkpoints' and not interrupted[0]:
            interrupted[0]=True;raise RuntimeError('Injected checkpoint interruption')
    e.save_npz=fault
    try:e.npg_task(small,8,9902,resumed,ident)
    except RuntimeError as error:assert str(error)=='Injected checkpoint interruption'
    finally:e.save_npz=saved
    assert interrupted[0];e.npg_task(small,8,9902,resumed,ident)
    a=e.read(next((reference/'raw').glob('*.json')));b=e.read(next((resumed/'raw').glob('*.json')))
    for key in ('records','physical_transitions','algorithm_actual_transitions'):assert a[key]==b[key]
    with np.load(next((reference/'policies').glob('*.npz'))) as a1,np.load(next((resumed/'policies').glob('*.npz'))) as b1:
        for key in a1.files:np.testing.assert_array_equal(a1[key],b1[key])
    bench=[]
    for rank in (2,100):
        s,_=load(cfg,rank);start=time.monotonic()
        endpoint,z,used,diag=e.stein_collect(s,s['K0'],np.zeros(100),max(e.schedule(cfg)),*e.innovations(cfg,0,9903),cfg)
        kd=e.npg_update(s['K0'],z,'dense',cfg['eta'],rank)
        kt=e.npg_update(s['K0'],z,'truncated',cfg['eta'],rank)
        if rank==100:np.testing.assert_array_equal(kd,kt)
        bench.append(dict(rank=rank,seconds=time.monotonic()-start,primitive_transitions=used,**diag))
    e.atomic_json(proof,dict(status='PASS',identity=ident,benchmark=bench,
        sequential_batched_agreement=True,checkpoint_resume_bitwise=True,
        full_rank_update_bitwise=True,peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        diagnostic_primitive_transitions=2070+a['physical_transitions']+b['physical_transitions']+sum(v['primitive_transitions'] for v in bench),
        slurm_job_id=os.environ['SLURM_JOB_ID'],threadpools=threadpool_info()))
    print(json.dumps(e.read(proof)),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','npg-preflight','pi-preflight','task','report'])
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--route',choices=['npg','pi'],default='npg')
    p.add_argument('--phase',choices=['pilot','confirm'],default='pilot');p.add_argument('--task-id',type=int)
    a=p.parse_args();parent=e.read(a.manifest)
    assert os.environ.get('SLURM_JOB_ID'),'Numerical work requires a real Grace compute allocation'
    for key,wanted in [('TMPDIR',parent['temp']),('NUMBA_CACHE_DIR',parent['cache']+'/numba'),('MPLCONFIGDIR',parent['cache']+'/matplotlib')]:
        assert os.environ.get(key)==wanted;(Path(wanted)).mkdir(parents=True,exist_ok=True)
    e.system=load
    with threadpool_limits(1):
        if a.mode=='prepare':prepare(parent,a.manifest)
        elif a.mode=='npg-preflight':npg_preflight(parent)
        elif a.mode=='pi-preflight':
            cfg=options(parent,'pi');out=Path(cfg['output']);ident=identity(cfg)
            if not (out/'verification.json').exists():pi.verify_runtime(cfg,out,ident)
            else:assert e.read(out/'verification.json')['identity']==ident
            if not (out/'maximum_memory_verification.json').exists():pi.verify_maximum_memory(cfg,out,ident)
            else:assert e.read(out/'maximum_memory_verification.json')['identity']==ident
        elif a.mode=='task':
            cfg=options(parent,a.route);out=Path(cfg['output']);ident=identity(cfg)
            assert e.read(out/'verification.json')['status']=='PASS'
            if a.route=='pi':assert e.read(out/'maximum_memory_verification.json')['status']=='PASS'
            jobs=[(rank,seed) for seed in cfg[a.phase+'_seeds'] for rank in cfg['ranks']]
            rank,seed=jobs[a.task_id]
            result=(e.npg_task if a.route=='npg' else pi.task)(cfg,rank,seed,out,ident)
            e.atomic_json(out/'task_receipts'/f'{a.phase}-{a.task_id:03d}.json',dict(result,route=a.route,
                rank=rank,seed=seed,phase=a.phase,slurm_job_id=os.environ['SLURM_JOB_ID']))
            print(json.dumps(result),flush=True)
        else:
            from matched_gap_npg_pi_report import report
            report(parent,a.phase)


if __name__=='__main__':main()
