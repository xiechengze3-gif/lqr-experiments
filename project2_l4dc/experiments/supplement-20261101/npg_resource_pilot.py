"""Bounded largest-batch timing and required multi-order equivalence pilot."""
import json,os,resource,time
from pathlib import Path
import numpy as np
import engine as e
import npg_multi

def equivalence():
    cfg=dict(nu=1.,H=32,burn_blocks=16,eta=.005,npg_batches=[64,96])
    s=e.plant(12,12,12,9005,spectrum='smooth');spec=dict(experiment='X3',n=12,m=12,r=2,system=9005,trial=7005,spectrum='smooth',null_scale=0.)
    dest=e.OUT/'X3/pilot-npg-resource';dest.mkdir(parents=True,exist_ok=True)
    reference=[];original=e.assess
    def capture(plant,gain):
        reference.append(gain.copy());return original(plant,gain)
    e.assess=capture
    try:ref=e.actor_run(s,spec,cfg,'NPG',dest/'engine-pair-reference.json')
    finally:e.assess=original
    actual=npg_multi.execute(s,spec,cfg,[2],dest/'multi-pair-equivalence.json')
    with np.load(dest/'multi-pair-equivalence.npz') as z:
        assert len(reference)==len([k for k in z if k.startswith('K_')])
        assert all(np.array_equal(g,z['K_'+str(i)]) for i,g in enumerate(reference))
    for a,b in zip(ref['records'],actual['records']):
        assert a['stable']==b['stable'] and a.get('gap')==b.get('gap') and a['transitions']==b['transitions']
    return dict(status='PASS_BITWISE',assessed_policies=len(reference),transitions=actual['actual_transitions'],
      notes='Two retained orders reproduce original paired engine, including state/RNG and burn/baseline counts')

def main():
    e.require_compute();out=e.OUT/'budget/NPG_resource_pilot_v1.json';assert not out.exists()
    eq=equivalence();rows=[]
    for n in [12,24,48]:
        s=e.plant(n,n,2,9003,null_scale=.25);cfg=dict(nu=1.,H=32,burn_blocks=16)
        for factor in [1,16]:
            batch=2048*(n*n//144)*factor
            start=time.monotonic()
            x,g,z=e.collect(s,s['K0'],np.zeros(n),batch,e.rng(20,n,n,9003,7003,factor),cfg)
            seconds=time.monotonic()-start
            assert np.isfinite(g).all() and np.isfinite(z).all() and np.isfinite(x).all()
            rows.append(dict(n=n,batch=batch,factor=factor,seconds=seconds,transitions=(17+batch)*32,
              max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
            e.save(out,dict(status='PARTIAL',equivalence=eq,rows=rows,job=os.environ['SLURM_JOB_ID']))
            print(json.dumps(rows[-1]),flush=True)
    e.save(out,dict(status='COMPLETE',scope='TIMING_ONLY_NOT_DENSE_QUALIFICATION',equivalence=eq,rows=rows,
      measured_at_supplied_K0=True,engine_sha256=e.sha(e.__file__),source_sha256=e.sha(__file__),
      multi_source_sha256=e.sha(npg_multi.__file__),job=os.environ['SLURM_JOB_ID']))

if __name__=='__main__':main()
