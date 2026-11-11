"""300-dimensional feasibility: dense controls, references, collector cost on Slurm."""
import argparse
import hashlib
import json
import os
import socket
import time
from pathlib import Path
import numpy as np
from dense_scaling import require_compute, evaluate, targets, eta, trunc, rng_for, atomic_json, pulse_moments
from npg_budget_system import system
from npg_batched_collector import collect


def run(out,reference_cache=None,cache_sha256=None):
    require_compute()
    out = Path(out)
    begin = time.monotonic()
    report = dict(status='RUNNING',job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),
        purpose='Feasibility and calibration only; not a replicated actor scaling study.',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependencies={Path(f.__code__.co_filename).name:
                      hashlib.sha256(Path(f.__code__.co_filename).read_bytes()).hexdigest()
                      for f in (system,collect,evaluate)},
        blas_threads=os.environ.get('OPENBLAS_NUM_THREADS'),systems=[],references=[],benchmarks=[])
    cached=None
    if reference_cache:
        cache=Path(reference_cache)
        assert cache_sha256 and hashlib.sha256(cache.read_bytes()).hexdigest()==cache_sha256
        cached=json.loads(cache.read_text())
        assert cached['source_sha256']=='4928c8848726bb931b4c9be7864c57cb9929e7f858b137ddd5ab25cad5b6bb03'
        assert cached['dependencies']==report['dependencies']
        assert len(cached['references'])==6
        assert all(r['stages']==256 and r['endpoint']['stable'] for r in cached['references'])
        assert all(r['reference_margin_pass'] and r['reference_gap_difference_pass']
                   for r in cached['references'] if r['finite_horizon'])
        report['references']=cached['references']
        report['reference_cache']=dict(path=str(cache),sha256=cache_sha256,
            original_job_id=cached['job_id'],original_source_sha256=cached['source_sha256'],
            reason='Only collector equivalence prefixes changed from 256/1024 to 1024/2048; reference algorithm unchanged.')

    def checkpoint():
        report['elapsed_seconds']=time.monotonic()-begin
        atomic_json(out/'feasibility.json',report)

    # Rank-invariant dense controls and reference margins at the requested dimension.
    systems = {}
    common = None
    previous_b = None
    for rank in (1,4,16,64,300):
        task=dict(n=300,m=300,r=rank,system_seed=0,trial_seed=0)
        started=time.monotonic()
        s=system(task)
        hashes={key:s['diagnostics']['hashes'][key] for key in ('A','Q','R','K0')}
        if common is None:common=hashes
        else:assert hashes==common
        assert all(d>.999 for d in s['diagnostics']['density'].values())
        singular=np.linalg.svd(s['B'],compute_uv=False)
        np.testing.assert_allclose(singular[:rank],1.2,atol=1e-12,rtol=1e-12)
        np.testing.assert_allclose(singular[rank:],0.,atol=1e-12)
        if previous_b is not None:
            np.testing.assert_allclose(previous_b.T@(s['B']-previous_b),0.,atol=1e-12)
        previous_b=s['B'];systems[rank]=s
        if cached:
            original=next(r for r in cached['systems'] if r['r']==rank)
            assert original['hashes']==s['diagnostics']['hashes']
        report['systems'].append(dict(**task,seconds=time.monotonic()-started,**s['diagnostics']))
        checkpoint()
        print(f'DENSE_SYSTEM_PASS n=300 rank={rank}',flush=True)

    for rank in (() if cached else (1,16,300)):
        s=systems[rank]
        endpoints={}
        for finite in (False,True):
            started=time.monotonic();k=s['K0'].copy();trace=[]
            for stage in range(257):
                quality,p=evaluate(s,k)
                assert quality['stable'],(rank,finite,stage)
                if stage%16==0:
                    trace.append(dict(stage=stage,**quality))
                    print(f'REFERENCE n=300 rank={rank} finite={finite} stage={stage} gap={quality["gap"]:.8g}',flush=True)
                if stage<256:
                    t=targets(s,k,16,p)
                    k-=2*eta(s)*(s['R']@k+t['ZH' if finite else 'Z'])
            endpoints[str(finite)]=quality['gap']
            report['references'].append(dict(n=300,r=rank,finite_horizon=finite,stages=256,
                seconds=time.monotonic()-started,endpoint=quality,trace=trace))
            checkpoint()
        report['references'][-1]['reference_margin_pass']=max(endpoints.values())<.125/20
        report['references'][-1]['reference_gap_difference_pass']=abs(endpoints['True']-endpoints['False'])<.125/50
        checkpoint()

    # Verify the same trajectory implementation on a small 300d prefix.
    s=systems[4];outputs=[]
    for collector in (pulse_moments,collect):
        outputs.append(list(collector(s,s['K0'],np.zeros(300),[1024,2048],16,1.,
                                      rng_for(9400300),burn=1024)))
    for old,new in zip(*outputs):
        assert old[0]==new[0] and old[-1]==new[-1]
        for index in (1,2,4):
            np.testing.assert_allclose(old[index],new[index],rtol=2e-10,atol=2e-10)
    report['collector_equivalence']='PASS';checkpoint()

    # SAME fixed policy and trajectory prefixes for raw and truncation diagnostics.
    # This tests one-update stability, not a complete actor learning trajectory.
    for n in (50,100,300):
        s=systems[4] if n==300 else system(dict(n=n,m=n,r=4,system_seed=0,trial_seed=0))
        k=s['K0'].copy();quality,p=evaluate(s,k);true=targets(s,k,16,p)
        started=time.monotonic()
        for count,x,z,_,gram,used in collect(s,k,np.zeros(n),[4096,16384,65536],16,1.,
                                           rng_for(9450300,n),burn=1024):
            elapsed=time.monotonic()-started
            records=[]
            for method,estimate in (('raw',z),('truncated',trunc(z,4))):
                updated=k-2*eta(s)*(s['R']@k+estimate)
                result,_=evaluate(s,updated)
                error=estimate-true['Z']
                records.append(dict(method=method,critic_error_fro2=float(np.sum(error*error)),
                    critic_error_op=float(np.linalg.norm(error,2)),one_update=result))
            report['benchmarks'].append(dict(n=n,r=4,system_seed=0,N=count,
                primitive_transitions=used,elapsed_prefix_seconds=elapsed,
                collector_only_prefix_seconds=elapsed,
                gram_condition=float(np.linalg.cond(gram)),methods=records))
            checkpoint()
            print(f'COLLECTOR n={n} N={count} prefix_seconds={elapsed:.3f}',flush=True)
            # Exclude diagnostic/evaluation time from the subsequent prefix timer.
            started+=time.monotonic()-started-elapsed
    margins=[r['reference_margin_pass'] and r['reference_gap_difference_pass']
             for r in report['references'] if r['finite_horizon']]
    report['all_reference_margins_pass']=all(margins)
    report['status']='PASS' if all(margins) else 'REFERENCE_MARGIN_NOT_MET'
    report['caveats']=['One calibration system; does not assess cross-system or trajectory variability.',
        'No complete sampled actor run; low-budget one-update failures remain recorded.',
        'Fixed eight BLAS threads for cost measurements; runtime is not a sample-complexity exponent.',
        'Formal replicated design must be frozen independently after calibration.']
    checkpoint()
    print(f'FEASIBILITY_STATUS {report["status"]}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    p.add_argument('--reference-cache');p.add_argument('--cache-sha256')
    args=p.parse_args();run(args.output,args.reference_cache,args.cache_sha256)
