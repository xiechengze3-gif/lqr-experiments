"""Fixed-check local pilot/formal driver. No implicit retries or outcome selection."""
import argparse, concurrent.futures, ctypes, datetime, hashlib, json, os, shutil, sys, time, traceback
from pathlib import Path
R=Path(__file__).resolve().parent; C=R.parents[1]
sys.path.insert(0,str(R/'src-v1'))
import numpy as np
import core, rectangular, s_ce_original

def preflight():
    cfg=json.loads((R/'config-v1.json').read_text())
    assert cfg['driver_sha256']==core.sha(Path(__file__))
    for name,digest in cfg['sources'].items():assert core.sha(R/'src-v1'/name)==digest
    assert not os.environ.get('SLURM_JOB_ID')
    for key in ['TEMP','TMP','TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR']:
        p=Path(os.environ[key]);assert p.drive.upper()=='E:' and p.is_dir()
    for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:assert os.environ[key]=='1'
    from threadpoolctl import threadpool_info
    pools=threadpool_info();assert all(x['num_threads']==1 for x in pools)
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(x,ctypes.c_ulonglong) for x in ['total','available','page','availpage','virtual','availvirtual','extended']]
    mem=Memory();mem.length=ctypes.sizeof(mem);assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
    assert mem.available>4*2**30 and shutil.disk_usage(R).free>5*2**30
    return cfg,dict(threadpools=pools,available_memory=mem.available,total_memory=mem.total,cpu_count=os.cpu_count(),free_disk=shutil.disk_usage(R).free)

def one(cell,system,seed,folder):
    cfg,_=preflight()
    n,m=cell['n'],cell['m'];s=rectangular.model('S',n,system,m)
    spec=dict(part='rectangular',config=f'n{n}-m{m}',system=system,seed=seed)
    dest=Path(folder)/spec['config']/f's{system}-t{seed}'
    actual,_=core.run_shared_ce(s,spec,cell['prefixes'],dest)
    assert core.peak_memory_bytes()<2*2**30
    return dict(path=str(dest.relative_to(Path(folder))),done_sha256=core.sha(dest/'DONE.json'),physical_transitions=actual['primitive_transitions'])

def pilot(cfg,resources):
    d=R/'pilot-v1';d.mkdir();start=time.monotonic();checks=[]
    # All model checks use disjoint pilot ids, never formal ids.
    for cell in cfg['cells']:
        n,m=cell['n'],cell['m'];s=rectangular.model('S',n,9914,m)
        assert s['A'].shape==(n,n) and s['B'].shape==(n,m) and s['K0'].shape==(m,n) and s['R'].shape==(m,m)
        singular=np.linalg.svd(s['B'],compute_uv=False)
        assert np.allclose(singular[:2],1,rtol=0,atol=1e-12) and np.max(singular[2:])<1e-12
        assert s['certificate']['P0_op']<=1.5625+1e-10
    for n in [16,48,96]:
        left=s_ce_original.model('S',n,9914);right=rectangular.model('S',n,9914,n)
        assert left['certificate']==right['certificate']
        for key in left:
            if key!='certificate':assert np.array_equal(left[key],right[key]),key
    # Fix n/system: state streams must be exactly shared across m.
    states=[rectangular.model('S',48,9914,m) for m in [4,6,8,12,16,24,32]]
    assert all(np.array_equal(states[0]['A'],s['A']) for s in states)
    for i,case in enumerate(cfg['pilot_cases']):
        s=rectangular.model('S',case['n'],case['system'],case['m'])
        spec=dict(part='pilot',config=f"n{case['n']}-m{case['m']}",system=case['system'],seed=case['seed'])
        dest=d/str(i);actual,fits=core.run_shared_ce(s,spec,case['prefixes'],dest)
        equal=core.equivalence(s,spec,case['prefixes'],actual,fits,dest)
        checks.append(dict(case=case,equality=equal,seconds=actual['seconds'],physical_transitions=2*actual['primitive_transitions']))
    peak=core.peak_memory_bytes();assert peak<2*2**30
    receipt=dict(status='PASS_ALL_FIXED_CHECKS',checks=checks,square_model_bitwise=True,all_rectangular_shapes_rank_certificate=True,
        fixed_n_A_stream_bitwise=True,resources=resources,peak_working_set_bytes=peak,seconds=time.monotonic()-start,
        physical_transitions=sum(x['physical_transitions'] for x in checks),formal_trajectories=0,no_outcome_based_selection=True,
        config_sha256=core.sha(R/'config-v1.json'),Grace_SU=0,Slurm_job_id=None)
    core.save_new(d/'PILOT_DONE.json',receipt)
    with (C/'CODEX_REPLY.md').open('a',encoding='utf-8') as f:
        f.write('\n## X11 PILOT\n\nAll fixed checks PASS: square model byte equality, rectangular dimensions/rank/P0 certificate, fixed-n A stream equality, original generic CE fits/gains/metrics/RNG/counts bitwise, one thread, memory/disk limits. Disjoint pilot cases only; no outcome selection. Full proof experiments/x11-20261106/pilot-v1/PILOT_DONE.json. GraceSU0.\nSTATUS: PILOT DONE X11\n')
    print(json.dumps(receipt),flush=True)

def formal(cfg,resources):
    proof=json.loads((R/'pilot-v1/PILOT_DONE.json').read_text());assert proof['status']=='PASS_ALL_FIXED_CHECKS' and proof['config_sha256']==core.sha(R/'config-v1.json')
    assert hashlib.sha256((C/'CLAUDE_TASK.md').read_bytes()).hexdigest()==os.environ['X11_ADVANCE_REVIEW_SHA256']
    d=R/'formal-v1';d.mkdir();start=time.monotonic();paths=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=cfg['workers']) as pool:
        futures={pool.submit(one,cell,system,seed,str(d)):(cell,system,seed) for cell in cfg['cells'] for system in cfg['systems'] for seed in cfg['seeds']}
        for future in concurrent.futures.as_completed(futures):
            paths.append(future.result())
            if len(paths)%16==0:print(json.dumps(dict(completed=len(paths),total=cfg['formal_paths'],elapsed=time.monotonic()-start)),flush=True)
    assert len(paths)==cfg['formal_paths'] and sum(x['physical_transitions'] for x in paths)==cfg['formal_transitions']
    receipt=dict(status='COMPLETE_FORMAL_NEW_CONFIGURATIONS_ONLY',paths=sorted(paths,key=lambda x:x['path']),
        physical_transitions=cfg['formal_transitions'],seconds=time.monotonic()-start,config_sha256=core.sha(R/'config-v1.json'),
        workers=cfg['workers'],resources=resources,Grace_SU=0,Slurm_job_id=None)
    core.save_new(d/'FORMAL_DONE.json',receipt)
    with (C/'CODEX_REPLY.md').open('a',encoding='utf-8') as f:
        f.write('\n## X11 FORMAL\n\nAll352 new physical paths complete,184729600transitions; 11 unique rectangular cells x8systems x4seeds, five nested prefixes, both arms on the same fit. Raw files and SHA receipts on E. No old configuration rerun, no failure discarded, 4local workers/one thread; GraceSU0. REPORT pending.\nSTATUS: FORMAL DONE X11\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['paths','resources']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['pilot','formal']);a=p.parse_args()
    try:
        cfg,res=preflight();(pilot if a.mode=='pilot' else formal)(cfg,res)
    except BaseException:
        failure=R/(a.mode+'-HARD_FAILURE-'+datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S')+'.json')
        core.save_new(failure,dict(error=traceback.format_exc(),Grace_SU=0));raise
