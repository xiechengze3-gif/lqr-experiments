"""X6a fixed-gain estimation; all numerical execution requires a compute node.

Prefix collectors preserve the frozen engine's random draws, chunk boundaries,
state continuity, burn-in and baseline. Evaluation is a separate post-process.
"""
from __future__ import annotations
import argparse
import json
import os
import resource
import socket
import time
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov
import frozen_engine as e

ROOT = Path(__file__).resolve().parent


def model(family, n, system):
    if family == 'U':
        return e.plant(n, n, 2, system, null_scale=0.)
    if family != 'S':
        raise ValueError(family)
    random = e.rng(1, n, system)
    rotation = e.haar(random, n)
    eigenvalues = random.uniform(.15, .60, n)
    a = (rotation * eigenvalues) @ rotation.T
    u = e.haar(e.rng(2, n, system), n)
    v = e.haar(e.rng(3, n, n, system), n)
    b = u[:, :2] @ v[:, :2].T
    eye = np.eye(n)
    k0 = np.zeros((n, n))
    p0 = solve_discrete_lyapunov(a.T, eye)
    ps = solve_discrete_are(a, b, eye, eye)
    ks = np.linalg.solve(eye + b.T @ ps @ b, b.T @ ps @ a)
    cert = dict(family='S', n=n, m=n, r=2, system=system,
                rho_A=float(np.max(np.abs(eigenvalues))),
                rho_F0=float(np.max(np.abs(eigenvalues))),
                P0_op=float(np.linalg.norm(p0, 2)),
                initial_gap=float(np.trace(p0-ps)), J0=float(np.trace(p0)),
                Jstar=float(np.trace(ps)), A_B_independent_streams=True,
                K0_action_energy_overlap=None,
                K0_action_column_subspace_overlap=None,
                K0_overlap_note='Zero gain: normalized overlaps are undefined.',
                initializer_uses_Q_R_Kstar_cost=False,
                A_eigenvalues=eigenvalues.tolist(), null_scale=0.)
    assert cert['P0_op'] <= 1.5625 + 1e-10
    return dict(A=a, B=b, Q=eye, R=eye, W=eye, K0=k0, P0=p0,
                Kstar=ks, Pstar=ps, basis=v[:, :2], certificate=cert)


def stein_prefixes(s, prefixes, random, config):
    """Same 256-block summation order as collect; no resampling at snapshots."""
    n, m = s['B'].shape
    k = s['K0']; h = config['H']; nu = config['nu']
    f = np.ascontiguousarray(s['A'] - s['B'] @ k)
    cost = s['Q'] + k.T @ s['R'] @ k
    prepared = e.prepare(f, s['B'], h)
    x = np.zeros(n); burn = config['burn_blocks']
    if burn:
        x, _, _ = e.pulse_batch(f, s['B'], cost, x,
            nu*random.normal(size=(burn,m)), random.normal(size=(burn,h,n)), prepared)
    x, _, ys = e.pulse_batch(f, s['B'], cost, x,
        nu*random.normal(size=(1,m)), random.normal(size=(1,h,n)), prepared)
    previous = ys[-1]
    gram = np.zeros((n,n)); cross = np.zeros((m,n)); curvature = np.zeros((m,m))
    done = 0
    for stop in prefixes:
        assert stop % 256 == 0 and stop > done
        while done < stop:
            count = min(256, stop-done)
            pulses = nu*random.normal(size=(count,m))
            noise = random.normal(size=(count,h,n))
            x, starts, ys = e.pulse_batch(f,s['B'],cost,x,pulses,noise,prepared)
            delta = np.diff(np.r_[previous,ys]); previous = ys[-1]
            labels = -pulses*delta[:,None]/(2*nu**2)
            gram += starts.T @ starts
            cross += labels.T @ starts
            curvature += ((pulses*delta[:,None]).T @ pulses
                          - nu**2*delta.sum()*np.eye(m))/(2*nu**4)
            done += count
        z = e.fit_model(gram,cross); g = curvature/done
        yield dict(N=done, x=x.copy(), G=(g+g.T)/2, Z=z,
                   gram=gram.copy(), cross=cross.copy(), curvature=curvature.copy(),
                   previous=np.array(previous),
                   rng_state=json.dumps(random.bit_generator.state,sort_keys=True))


def ce_prefixes(s, prefixes, random, config):
    """Exact 512-transition chunks and half-prefix stops of frozen ce_run."""
    n,m = s['B'].shape; k=s['K0']; nu=config['nu']; burn=config['ce_burn']
    f=np.ascontiguousarray(s['A']-s['B']@k); x=np.zeros(n)
    x,_,_=e.ce_chunk(f,s['B'],k,x,nu*random.normal(size=(burn,m)),
                    random.normal(size=(burn,n)))
    gram=np.zeros((n+m,n+m)); cross=np.zeros((n,n+m)); done=0
    for stop in sorted(set(prefixes)|{v//2 for v in prefixes}):
        while done<stop:
            count=min(512,stop-done)
            x,z,y=e.ce_chunk(f,s['B'],k,x,nu*random.normal(size=(count,m)),
                             random.normal(size=(count,n)))
            gram+=z.T@z; cross+=y.T@z; done+=count
        if done in prefixes:
            theta=e.fit_model(gram,cross)
            yield dict(N=done,x=x.copy(),Ahat=theta[:,:n],Bhat=theta[:,n:],
                       gram=gram.copy(),cross=cross.copy(),
                       rng_state=json.dumps(random.bit_generator.state,sort_keys=True))


def equivalence():
    """Resource-only numerical equivalence, never calibration/performance selection."""
    checks=[]
    for family,h,system in [('S',16,9101),('U',32,9201)]:
        s=model(family,24,system); cfg=dict(H=h,nu=1.,burn_blocks=16)
        for item in stein_prefixes(s,[256,1024],e.rng(20,24,24,system,9701,1),cfg):
            random=e.rng(20,24,24,system,9701,1)
            x,g,z=e.collect(s,s['K0'],np.zeros(24),item['N'],random,cfg)
            assert np.array_equal(x,item['x'])
            assert np.array_equal(g,item['G']) and np.array_equal(z,item['Z'])
            assert json.dumps(random.bit_generator.state,sort_keys=True)==item['rng_state']
            checks.append(dict(family=family,H=h,N=item['N'],status='PASS_BITWISE'))
        cfg['ce_burn']=512
        actual={item['N']:item for item in ce_prefixes(
            s,[2048,8192],e.rng(10,24,24,system,9701),cfg)}
        random=e.rng(10,24,24,system,9701)
        k=s['K0']; f=np.ascontiguousarray(s['A']-s['B']@k); b=s['B']
        x=np.zeros(24); gram=np.zeros((48,48)); cross=np.zeros((24,48))
        done=0
        # Independent scalar-time reference; draw chunks match ce_run exactly.
        for stop in [0,1024,2048,4096,8192]:
            count=512 if stop==0 else min(512,stop-done)
            while count:
                pulses=random.normal(size=(count,24)); noise=random.normal(size=(count,24))
                zs=[]; ys=[]
                for pulse,w in zip(pulses,noise):
                    state=x.copy(); action=-k@state+pulse
                    x=f@state+b@pulse+w
                    zs.append(np.r_[state,action]); ys.append(x.copy())
                if stop:
                    zs=np.array(zs); ys=np.array(ys)
                    gram+=zs.T@zs; cross+=ys.T@zs; done+=count
                    count=min(512,stop-done)
                else:
                    count=0
            if stop in actual:
                theta=e.fit_model(gram,cross)
                fitted=np.concatenate((actual[stop]['Ahat'],actual[stop]['Bhat']),axis=1)
                for reference,observed in [(theta,fitted),(x,actual[stop]['x']),
                                            (gram,actual[stop]['gram']),
                                            (cross,actual[stop]['cross'])]:
                    assert np.allclose(reference,observed,rtol=1e-11,atol=1e-11)
                assert json.dumps(random.bit_generator.state,sort_keys=True)==actual[stop]['rng_state']
                checks.append(dict(family=family,algorithm='CE',N=stop,
                                   status='PASS_RTOL_ATOL_1e-11_RNG_BITWISE'))
    return checks


def run_cell(spec, config, destination, timing_only=False):
    start=time.monotonic()
    family=spec['family']; n=spec['n']; system=spec['system']; seed=spec['seed']
    s=model(family,n,system)
    cfg=dict(config,H=config['horizon'][family])
    prefixes=config['blocks']; rows=[]; artifacts=[]
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    if not timing_only:
        np.savez_compressed(destination/'model.npz', **{k:s[k] for k in
            ['A','B','Q','R','W','K0','P0','Kstar','Pstar','basis']})
    setup_seconds=time.monotonic()-start
    for algorithm,collector,random in [
        ('Stein',stein_prefixes,e.rng(20,n,n,system,seed,1)),
        ('CE',ce_prefixes,e.rng(10,n,n,system,seed))]:
        clock=time.monotonic()
        for item in collector(s,prefixes,random,cfg):
            stop=item.pop('N')
            row=dict(algorithm=algorithm,N=stop,elapsed_seconds=time.monotonic()-clock,
                     actual_transitions=(stop+17)*cfg['H'] if algorithm=='Stein'
                     else stop+cfg['ce_burn'])
            rows.append(row)
            if not timing_only:
                rng_state=item.pop('rng_state')
                path=destination/(algorithm+'-'+str(stop)+'.npz')
                np.savez_compressed(path,**item)
                artifacts.append(dict(path=path.name,sha256=e.sha(path),rng_state=rng_state))
        if not timing_only:
            e.save(destination/('checkpoint-'+algorithm+'.json'),dict(status='COMPLETE',
                   rows=[r for r in rows if r['algorithm']==algorithm]))
    data=dict(status='COMPLETE',spec=spec,timing_only=timing_only,rows=rows,
              seconds=time.monotonic()-start,setup_seconds=setup_seconds,
              max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              artifacts=artifacts,job=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),
              source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),
              config_sha256=config['_config_sha256'])
    if not timing_only:
        data['certificate']=s['certificate']
        data['model_sha256']=e.sha(destination/'model.npz')
    e.save(destination/'receipt.json',data)
    return data


def main():
    e.require_compute()
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['resource','formal'])
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--index',type=int,required=True)
    args=p.parse_args()
    allowed=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101')
    if not args.out.resolve().is_relative_to(allowed):
        raise ValueError('Output outside X6 namespace')
    config=json.loads(args.config.read_text(encoding='utf-8-sig'))
    config['_config_sha256']=e.sha(args.config)
    tasks=config['resource_tasks'] if args.mode=='resource' else config['formal_tasks']
    task=tasks[args.index]
    dest=args.out/args.mode/('task-'+str(args.index))
    if dest.exists():
        raise FileExistsError('No implicit retries: '+str(dest))
    dest.mkdir(parents=True)
    if args.mode=='resource' and args.index==0:
        e.save(dest/'equivalence.json',dict(status='PASS_BITWISE',checks=equivalence()))
    for cell in task['cells']:
        result=run_cell(cell,config,dest/(cell['family']+'-n'+str(cell['n'])),
                        timing_only=args.mode=='resource')
        print(json.dumps(dict(index=args.index,spec=cell,seconds=result['seconds'],
                              max_rss_KiB=result['max_rss_KiB'])),flush=True)
    e.save(dest/'DONE.json',dict(status='COMPLETE',task=task,job=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':
    main()
