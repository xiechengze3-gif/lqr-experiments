"""Deterministic quadrature identities plus trajectory and update regressions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from numpy.polynomial.hermite_e import hermegauss
from scipy.linalg import solve_discrete_lyapunov
from direct_stein_final import sufficient, combine, fit, correct, update, psd
from dense_scaling import pulse_chunk, targets
from npg_batched_collector import prepare, batched_chunk


class SteinTests(unittest.TestCase):
    def test_gaussian_identities_all_sigma(self):
        # Exact Gaussian product quadrature integrates all required polynomials.
        v,w=hermegauss(5);w=w/np.sqrt(2*np.pi)
        uu=np.array([[a,b] for a in v for b in v]); ww=np.outer(w,w).ravel()
        g=np.array([[2.,.3],[.3,.7]]); linear=np.array([.2,-.9])
        for sigma in (.3,1.,2.):
            e=sigma*uu;y=np.einsum('bi,ij,bj->b',e,g,e)+2*e@linear+7.
            z=-np.einsum('b,bi,b->i',ww,e,y)/(2*sigma**2)
            gh=(np.einsum('b,bi,bj,b->ij',ww,e,e,y)-sigma**2*np.dot(ww,y)*np.eye(2))/(2*sigma**4)
            np.testing.assert_allclose(z,-linear,atol=1e-12)
            np.testing.assert_allclose(gh,g,atol=1e-11)

    def test_horizon_target_and_transposes(self):
        rng=np.random.default_rng(8);n,m=3,2
        f=rng.normal(size=(n,n))*.1;b=rng.normal(size=(n,m));k=rng.normal(size=(m,n))*.1
        q=np.diag([1.,2.,3.]);r=np.diag([2.,4.]);s=dict(A=f+b@k,B=b,Q=q,R=r)
        p=solve_discrete_lyapunov(f.T,q+k.T@r@k)
        for h in (1,2,16):
            ph=sum(np.linalg.matrix_power(f,t).T@(q+k.T@r@k)@np.linalg.matrix_power(f,t) for t in range(h))
            t=targets(s,k,h,p)
            np.testing.assert_allclose(t['GH'],b.T@ph@b,atol=1e-12)
            np.testing.assert_allclose(t['ZH'],-b.T@ph@f,atol=1e-12)

    def test_continuous_block_and_initial_baseline(self):
        rng=np.random.default_rng(3);f=rng.normal(size=(3,3))*.1;b=rng.normal(size=(3,2))
        x=rng.normal(size=3);e=rng.normal(size=(31,2));w=rng.normal(size=(31,4,3))
        sequential=pulse_chunk(f,b,np.eye(3),x,e,w)
        batched=batched_chunk(f,b,np.eye(3),x,e,w,prepare(f,b,4))
        for a,c in zip(sequential,batched):np.testing.assert_allclose(a,c,atol=1e-12)
        _,starts,y=batched
        a=sufficient(starts,e,y,17.,1.)
        lo=sufficient(starts[:15],e[:15],y[:15],17.,1.)
        hi=sufficient(starts[15:],e[15:],y[15:],y[14],1.)
        for key in a:np.testing.assert_allclose(a[key],combine(lo,hi)[key],atol=1e-10)
        self.assertEqual(a['count'],31)
        for aa,bb in zip(fit(a)[:2],fit(combine(lo,hi))[:2]):np.testing.assert_allclose(aa,bb,atol=1e-10)

    def test_full_rank_identity_and_clipping(self):
        rng=np.random.default_rng(4);g=rng.normal(size=(4,4));z=rng.normal(size=(4,3))
        dense=correct(g,z,'dense');full=correct(g,z,'known_rank',known_rank=4)
        for a,b in zip(dense[:2],full[:2]):np.testing.assert_array_equal(a,b)
        self.assertGreaterEqual(np.linalg.eigvalsh(dense[0])[0],-1e-12)

    def test_exact_low_rank_joint_and_zero_rank(self):
        rng=np.random.default_rng(5);u=np.linalg.qr(rng.normal(size=(6,2)))[0]
        g=u@np.diag([2.,1.])@u.T;z=u@rng.normal(size=(2,3))
        gg,zz,_=correct(g,z,'known_rank',known_rank=2)
        np.testing.assert_allclose(gg,g,atol=1e-12);np.testing.assert_allclose(zz,z,atol=1e-12)
        gg,zz,info=correct(g,z,'adaptive',halves=((100*g,100*z),(-100*g,-100*z)))
        self.assertEqual(info['retained_rank'],0);self.assertEqual(np.linalg.norm(gg)+np.linalg.norm(zz),0)

    def test_RK_and_old_clipping_regression(self):
        k=np.array([[.3,.1],[.2,-.4]]);r=np.array([[2.,.2],[.2,1.]])
        g=np.diag([-2.,1.]);z=np.array([[.2,.4],[-.3,.8]]);gg=psd(g)
        new,_=update(k,r,gg,z,1.)
        np.testing.assert_allclose(new,np.linalg.solve(r+gg,gg@k-z),atol=1e-12)
        old=np.linalg.solve(r+gg,g@k-z)
        self.assertGreater(np.linalg.norm(old-new),.1)
        damped,_=update(k,r,gg,z,.25)
        np.testing.assert_allclose(damped,.75*k+.25*new,atol=1e-12)

    def test_bad_gram_preserves_failure(self):
        with self.assertRaises(np.linalg.LinAlgError):
            fit(dict(gram=np.zeros((2,2)),cross=np.ones((2,2)),curvature=np.eye(2),count=10))

    def test_collector_estimator_and_primitive_budget(self):
        from final_round import collect
        from adaptive_rank_run import direct_data
        rng=np.random.default_rng(33);n=6;k=np.eye(n)*.1
        s=dict(A=np.eye(n)*.45,B=rng.normal(size=(n,n))*.1,Q=np.eye(n),R=np.eye(n))
        x,full,halves,used=collect(s,k,np.zeros(n),1024,np.random.default_rng(89),h=4,burn=3)
        oldx,old,oldhalves,oldused=direct_data(s,k,np.zeros(n),1024,3,4,np.random.default_rng(89))
        self.assertEqual(used,3+1025*4);self.assertEqual(used,oldused)
        np.testing.assert_allclose(x,oldx,atol=1e-12)
        for a,b in zip(full[:2],(old[0],old[2])):np.testing.assert_allclose(a,b,atol=1e-11)
        for h1,h2 in zip(halves,oldhalves):
            for a,b in zip(h1,(h2[0],h2[2])):np.testing.assert_allclose(a,b,atol=1e-11)

    def test_interrupted_actor_resume(self):
        import tempfile
        import json
        from unittest.mock import patch
        import final_round as runner
        n=6;b=np.diag([.2,.2,0,0,0,0]);a=np.eye(n)*.5;k=np.eye(n)*.1
        from dense_scaling import dare
        ks,p=dare(a,b,np.eye(n),np.eye(n))
        p0=solve_discrete_lyapunov((a-b@k).T,np.eye(n)+k.T@k)
        s=dict(A=a,B=b,Q=np.eye(n),R=np.eye(n),K0=k,Jstar=float(np.trace(p)),initial_gap=float(np.trace(p0-p)))
        with tempfile.TemporaryDirectory() as temp,patch.object(runner,'make_system',return_value=s):
            root=Path(temp);whole=root/'whole';resumed=root/'resumed'
            runner.actor(whole,[1],[0],[512],.25,'debug',updates=2,n=n,rank=2)
            original=runner.collect;calls=[0]
            def interrupt(*args,**kwargs):
                calls[0]+=1
                if calls[0]==4:raise RuntimeError('Test interruption')
                return original(*args,**kwargs)
            with patch.object(runner,'collect',side_effect=interrupt):
                with self.assertRaisesRegex(RuntimeError,'Test interruption'):
                    runner.actor(resumed,[1],[0],[512],.25,'debug',updates=2,n=n,rank=2)
            runner.actor(resumed,[1],[0],[512],.25,'debug',updates=2,n=n,rank=2)
            for path in (whole/'debug').glob('n*.json'):
                self.assertEqual(json.loads(path.read_text()),json.loads((resumed/'debug'/path.name).read_text()))
                with np.load(path.with_suffix('.npz')) as full,np.load((resumed/'debug'/path.name).with_suffix('.npz')) as replay:
                    np.testing.assert_array_equal(full['K'],replay['K']);np.testing.assert_array_equal(full['x'],replay['x'])


if __name__=='__main__':unittest.main(verbosity=2)
