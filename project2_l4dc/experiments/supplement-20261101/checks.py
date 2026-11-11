"""Small compute-node checks of observations, pulse returns and learner formulas."""
import json, os
from pathlib import Path
import numpy as np
import engine as e

def main():
    e.require_compute();random=e.rng(999,1);n,m,h,count=5,3,7,11
    f=.45*np.eye(n);b=random.normal(size=(n,m))/3;k=random.normal(size=(m,n))/5
    cost=np.eye(n)+k.T@k;x0=random.normal(size=n)
    pulses=random.normal(size=(count,m));noise=random.normal(size=(count,h,n))
    final,starts,returns=e.pulse_batch(f,b,cost,x0,pulses,noise,e.prepare(f,b,h))
    x=x0.copy();manual_starts=[];manual_returns=[]
    for i in range(count):
        manual_starts.append(x.copy());value=0.
        for t in range(h):
            x=f@x+noise[i,t]
            if t==0:x+=b@pulses[i]
            value+=x@cost@x
        manual_returns.append(value)
    np.testing.assert_allclose(final,x,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(starts,manual_starts,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(returns,manual_returns,rtol=1e-12,atol=1e-12)
    ce_noise=random.normal(size=(count,n));final,z,y=e.ce_chunk(f,b,k,x0,pulses,ce_noise)
    x=x0.copy()
    for i in range(count):
        u=-k@x+pulses[i];np.testing.assert_allclose(z[i],np.r_[x,u])
        x=(f+b@k)@x+b@u+ce_noise[i];np.testing.assert_allclose(y[i],x)
    np.testing.assert_allclose(final,x)
    g=random.normal(size=(m,m));g=(g+g.T)/2;zz=random.normal(size=(m,n))
    for alg in ('NPG','PI'):
        a=e.actor_learner(k,np.eye(m),g,zz,'dense',m,alg,.01)
        bb=e.actor_learner(k,np.eye(m),g,zz,'truncated',m,alg,.01)
        np.testing.assert_array_equal(a,bb)
    s=e.plant(12,12,2,9001,null_scale=.25)
    assert s['certificate']['rho_A']>1 and s['certificate']['rho_F0']<1
    result=dict(status='PASS',checks=['sequential pulse endpoint','all block-start states',
      'postpulse returns','observed CE state/action/next-state triples','full-rank NPG identity',
      'full-rank v4 PI identity','unstable independent factory and stability-only initialization'],job=os.environ['SLURM_JOB_ID'])
    e.save(e.OUT/'X1/pilot/implementation_checks.json',result);print(json.dumps(result))

if __name__=='__main__':main()
