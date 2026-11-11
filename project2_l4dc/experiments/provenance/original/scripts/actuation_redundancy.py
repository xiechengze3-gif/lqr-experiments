"""Fixed effective LQR, rectangular post-pulse Direct-Stein NPG experiment."""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_discrete_lyapunov
from threadpoolctl import threadpool_limits, threadpool_info
from dense_scaling import (atomic_json, rng_for, orth, dare, evaluate, trunc,
                           nominal_chunk, pulse_chunk)
from npg_batched_collector import prepare, batched_chunk

SOURCES = ['scripts/actuation_redundancy.py', 'scripts/actuation_redundancy_report.py',
           'scripts/npg_batched_collector.py', 'scripts/direct_stein_final.py',
           'dense_scaling.py', 'docs/ACTUATION_REDUNDANCY_PROTOCOL_20261016.md']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def schedule(cfg):
    return [n for n, length in cfg['schedule_segments'] for _ in range(length)]


def identity(manifest):
    return dict(manifest_sha256=sha(manifest), sources={p: sha(ROOT/p) for p in SOURCES})


def base_system(cfg):
    n, rank = cfg['n'], cfg['rank']
    rng = rng_for(cfg['system_seed'])
    u = orth(rng, n)
    latent = np.diag(np.r_[np.full(rank, 1.08), np.linspace(.2, .6, n-rank)])
    latent += .04*np.diag(np.ones(n-1), 1)
    singular = np.linspace(1.2, .9, rank)
    a = u@latent@u.T
    b = u[:, :rank]*singular
    kbar = (.4/singular)[:, None]*u[:, :rank].T
    h = rng.normal(size=n); h *= .35/np.linalg.norm(h)
    ks, ps = dare(a, b, np.eye(n), np.eye(rank))
    f0 = a-b@kbar
    p0 = solve_discrete_lyapunov(f0.T, np.eye(n)+kbar.T@kbar+np.outer(h, h))
    return dict(A=a, Beff=b, Kbar=kbar, h=h, F0=f0, P0=p0,
                Kstar_eff=ks, Pstar=ps, Jstar=float(np.trace(ps)),
                initial_gap=float(np.trace(p0-ps)))


def make_system(cfg, m):
    base = base_system(cfg); n, rank = cfg['n'], cfg['rank']
    rng = rng_for(cfg['rotation_seed'], m)
    o = orth(rng, m); v = rng.normal(size=m-rank); v /= np.linalg.norm(v)
    b = base['Beff']@o[:, :rank].T
    k0 = o@np.vstack((base['Kbar'], np.outer(v, base['h'])))
    return dict(A=base['A'], B=b, Q=np.eye(n), R=np.eye(m), W=np.eye(n),
                K0=k0, Kstar=o[:, :rank]@base['Kstar_eff'], Jstar=base['Jstar'],
                initial_gap=base['initial_gap']), dict(base, O=o, v=v)


def learner(k, zhat, method, step, rank):
    """Observation-only boundary: no plant, projection, evaluator or RNG."""
    z = zhat if method == 'dense' else trunc(zhat, rank)
    return k-step*(k+z)


def collect(s, k, x, count, pulse_rng, noise_rng, cfg, sequential=False):
    """Same first-order estimator, arbitrary m, no curvature computation."""
    n, m = k.shape[1], k.shape[0]
    horizon, burn, sigma = cfg['horizon'], cfg['burn'], cfg['sigma']
    f = np.ascontiguousarray(s['A']-s['B']@k)
    cost = np.ascontiguousarray(s['Q']+k.T@k)
    prepared = prepare(f, s['B'], horizon)
    x, _ = nominal_chunk(f, x, noise_rng.normal(size=(burn, n)))
    pulse = sigma*pulse_rng.normal(size=(1, m))
    x, _, values = pulse_chunk(f, s['B'], cost, x, pulse,
                               noise_rng.normal(size=(1, horizon, n)))
    previous = values[-1]
    gram, cross = np.zeros((n, n)), np.zeros((m, n))
    totals = np.zeros(7)
    for lo in range(0, count, cfg['chunk_size']):
        size = min(cfg['chunk_size'], count-lo)
        pulses = sigma*pulse_rng.normal(size=(size, m))
        noise = noise_rng.normal(size=(size, horizon, n))
        if sequential:
            x, starts, values = pulse_chunk(f, s['B'], cost, x, pulses, noise)
        else:
            x, starts, values = batched_chunk(f, s['B'], cost, x, pulses, noise, prepared)
        delta = np.diff(np.r_[previous, values]); previous = values[-1]
        labels = -pulses*delta[:, None]/(2*sigma**2)
        gram += starts.T@starts; cross += labels.T@starts
        energy = np.einsum('ij,ij->i', pulses, pulses)
        physical_action = pulses-starts@k.T
        action_cost = np.einsum('ij,ij->i', physical_action, physical_action)
        totals += [energy.sum(), np.sum(energy**2), values.sum(), np.sum(values**2),
                   action_cost.sum(), np.sum(action_cost**2), size]
    if not np.all(np.isfinite(cross)):
        raise FloatingPointError('Nonfinite first-order sufficient statistics')
    zhat = cho_solve(cho_factor((gram+gram.T)/2), cross.T).T
    info = dict(gram_condition=float(np.linalg.cond(gram)),
                critic_relative_residual=float(np.linalg.norm(zhat@gram-cross)/max(np.linalg.norm(cross), 1e-30)))
    for label, offset in [('pulse_energy', 0), ('postpulse_return', 2), ('injection_action_cost', 4)]:
        avg = totals[offset]/count
        info[label+'_mean'] = float(avg)
        info[label+'_variance'] = float(max(0., totals[offset+1]/count-avg**2))
    return x, zhat, burn+(count+1)*horizon, info


def diagnostics(s, private, k):
    quality, p = evaluate(s, k)
    if not quality['stable']:
        return dict(quality, redundant_loss=None, effective_loss=None,
                    decomposition_residual=None, performance_identity_residual=None)
    rank = private['Beff'].shape[1]
    basis = private['O'][:, :rank]
    ke = basis@(basis.T@k); kn = k-ke
    f = s['A']-s['B']@k
    cov = solve_discrete_lyapunov(f, s['W'])
    redundant = float(np.trace(kn@cov@kn.T))
    pe = solve_discrete_lyapunov(f.T, s['Q']+ke.T@ke)
    effective = float(np.trace(pe)-s['Jstar'])
    error = k-s['Kstar']
    weight = s['R']+s['B'].T@private['Pstar']@s['B']
    identity_gap = float(np.trace(weight@error@cov@error.T))
    residual = quality['gap']-redundant-effective
    residual2 = quality['gap']-identity_gap
    tol = 2e-8*max(1., quality['cost'])
    if abs(residual) > tol or abs(residual2) > tol or min(redundant, effective) < -tol:
        raise ArithmeticError('Offline loss decomposition failed')
    return dict(quality, redundant_loss=redundant, effective_loss=effective,
                decomposition_residual=residual, performance_identity_residual=residual2)


def seeds(cfg, seed, stage, m):
    return (rng_for(811671, seed, stage, m, 0), rng_for(811671, seed, stage, 1))


def verify(cfg, output, ident):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    checks = []; reference = base_system(cfg)
    for m in cfg['action_dimensions']:
        s, private = make_system(cfg, m)
        full_ks, full_ps = dare(s['A'], s['B'], s['Q'], s['R'])
        q = diagnostics(s, private, s['K0'])
        expected_cost = np.eye(cfg['n'])+reference['Kbar'].T@reference['Kbar']+np.outer(reference['h'], reference['h'])
        _, actual_p = evaluate(s, s['K0'])
        differences = dict(
            closed_loop=float(np.max(np.abs(s['A']-s['B']@s['K0']-reference['F0']))),
            initial_stage_cost=float(np.max(np.abs(s['Q']+s['K0'].T@s['K0']-expected_cost))),
            P0=float(np.max(np.abs(actual_p-reference['P0']))),
            Pstar=float(np.max(np.abs(full_ps-reference['Pstar']))),
            Kstar=float(np.max(np.abs(full_ks-s['Kstar']))),
            J0=abs(q['cost']-float(np.trace(reference['P0']))),
            Jstar=abs(float(np.trace(full_ps))-reference['Jstar']),
            initial_gap=abs(q['gap']-reference['initial_gap']))
        assert max(differences.values()) < 1e-8
        null_norm = float(np.linalg.norm(s['K0']-private['O'][:, :cfg['rank']]@(private['O'][:, :cfg['rank']].T@s['K0'])))
        np.testing.assert_allclose(null_norm, .35, atol=1e-12)
        assert np.linalg.matrix_rank(s['B']) == cfg['rank'] and q['stable']
        np.testing.assert_allclose(s['B']@s['B'].T, reference['Beff']@reference['Beff'].T, atol=1e-12)
        path = output/'systems'/f'm{m:03d}.npz'; path.parent.mkdir(exist_ok=True)
        np.savez_compressed(path, **s, **{key: value for key, value in private.items() if key not in s})
        checks.append(dict(m=m, differences=differences, K0_null_fro=null_norm, J0=q['cost'],
                           Jstar=s['Jstar'], initial_gap=s['initial_gap'], rho=q['rho'],
                           initial_redundant_loss=q['redundant_loss'], initial_effective_loss=q['effective_loss']))
    # Validate rectangular arithmetic against the original sequential trajectory.
    small = dict(cfg, burn=7, chunk_size=256)
    for m in (8, 32, 128):
        s, private = make_system(cfg, m); outputs = []
        for seq in (False, True):
            outputs.append(collect(s, s['K0'], np.zeros(cfg['n']), 512,
                                   *seeds(cfg, 9001, 0, m), small, sequential=seq))
        assert outputs[0][2] == 7+513*cfg['horizon'] == outputs[1][2]
        for i in (0, 1):
            np.testing.assert_allclose(outputs[0][i], outputs[1][i], atol=3e-10, rtol=3e-10)
    # Original sufficient()/fit() uses identical first-order statistics.
    from direct_stein_final import sufficient, fit
    from numpy.polynomial.hermite_e import hermegauss
    rng = rng_for(99101); starts = rng.normal(size=(100, 30)); pulses = rng.normal(size=(100, 8)); values = rng.normal(size=100)
    st = sufficient(starts, pulses, values, 17., cfg['sigma'])
    ours = cho_solve(cho_factor(starts.T@starts), (-pulses*np.diff(np.r_[17., values])[:, None]/2).T.__matmul__(starts).T).T
    np.testing.assert_allclose(ours, fit(st)[1], atol=1e-12)
    # Post-pulse first-order identity by exact product Gaussian quadrature.
    f=np.array([[.4,.1],[0.,.3]]); b=np.array([[.8,0.,0.],[.2,.7,0.]])
    cost=np.array([[1.2,.1],[.1,1.4]]); start=np.array([.3,-.4]); h=4
    nodes, weights=hermegauss(5); weights=weights/np.sqrt(2*np.pi)
    label=np.zeros(3)
    for i in range(5):
        for j in range(5):
            for l in range(5):
                pulse=np.array([nodes[i],nodes[j],nodes[l]])
                _,_,y=pulse_chunk(f,b,cost,start.copy(),pulse[None,:],np.zeros((1,h,2)))
                label+=weights[i]*weights[j]*weights[l]*(-pulse*(y[0]-17.)/2)
    ph=sum(np.linalg.matrix_power(f,t).T@cost@np.linalg.matrix_power(f,t) for t in range(h))
    np.testing.assert_allclose(label,-b.T@ph@f@start,atol=1e-12)
    # Known K term survives truncation, including its null component.
    k=rng.normal(size=(8,30)); z=rng.normal(size=(8,30))
    np.testing.assert_allclose(learner(k,z,'truncated',.05,4), .95*k-.05*trunc(z,4),atol=1e-13)
    # Exact finite-H reference is diagnostic only; dense/truncated must agree.
    from dense_scaling import targets
    s, private=make_system(cfg,32); k=s['K0'].copy()
    exact=[]
    for stage in range(len(schedule(cfg))+1):
        q=diagnostics(s,private,k); exact.append(dict(stage=stage,**q))
        z=targets(s,k,cfg['horizon'])['ZH']
        np.testing.assert_allclose(learner(k,z,'dense',cfg['eta'],cfg['rank']),
                                   learner(k,z,'truncated',cfg['eta'],cfg['rank']),atol=1e-12)
        k=learner(k,z,'dense',cfg['eta'],cfg['rank'])
    s,_=make_system(cfg,128); start_time=time.monotonic()
    result=collect(s,s['K0'],np.zeros(cfg['n']),max(schedule(cfg)),*seeds(cfg,9001,1,128),cfg)
    elapsed=time.monotonic()-start_time
    uses=[cfg['burn']+(n+1)*cfg['horizon'] for n in schedule(cfg)]
    report=dict(status='PASS', identity=ident, invariants=checks, exact_finite_H_reference=exact,
                tests=['all-m invariant F0/P0/J0/Pstar/Jstar/gap', 'K0 outside effective space',
                       'rectangular sequential/batched equivalence', 'first-order original sufficient/fit identity',
                       'Gaussian post-pulse label identity', 'known K retained', 'two offline loss identities',
                       'exact finite-H dense/truncated identity', 'primitive burn/baseline accounting'],
                benchmark=dict(seed=9001,m=128,blocks=max(schedule(cfg)),seconds=elapsed,
                               transitions=result[2],threadpools=threadpool_info()),
                assigned_transitions_per_trajectory=sum(uses),
                planned_trajectories=len(cfg['action_dimensions'])*len(cfg['trial_seeds'])*2)
    atomic_json(output/'verification.json',report)
    print(json.dumps(dict(verification='PASS', benchmark_seconds=elapsed, assigned_transitions=sum(uses))),flush=True)


def task(cfg, m, seed, out, ident):
    out=Path(out); path=out/'raw'/f'm{m:03d}-seed{seed:02d}.json'
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8')); assert old['identity']==ident
        return dict(m=m,seed=seed,reused=True)
    s,private=make_system(cfg,m); counts=schedule(cfg)
    uses=np.array([cfg['burn']+(n+1)*cfg['horizon'] for n in counts]); grid=np.r_[0,np.cumsum(uses)]
    all_rows=[]; archives={}; began=time.monotonic()
    for method in cfg['methods']:
        cp=out/'checkpoints'/f'm{m:03d}-seed{seed:02d}-{method}.npz'; cp.parent.mkdir(exist_ok=True)
        k=s['K0'].copy(); x=np.zeros(cfg['n']); actual=0; failed=False; next_stage=0
        rows=[dict(method=method,stage=0,transitions=0,actual_transitions=0,observed=True,
                   failure=None,**diagnostics(s,private,k))]; policies=[k.copy()]
        if cp.exists():
            with np.load(cp,allow_pickle=False) as a:
                assert json.loads(str(a['identity']))==ident
                k=a['K'].copy(); x=a['x'].copy(); actual=int(a['actual']); next_stage=int(a['next_stage'])
                failed=bool(a['failed']); rows=json.loads(str(a['rows'])); policies=list(a['policies'])
        for stage in range(next_stage,len(counts)):
            row=dict(method=method,stage=stage+1,transitions=int(grid[stage+1]),
                     blocks=counts[stage],observed=not failed)
            if failed:
                row.update(stable=False,cost=None,gap=None,relative_gap=None,redundant_loss=None,
                           effective_loss=None,failure='prior_failure')
            else:
                actual+=int(uses[stage])
                try:
                    x,z,used,info=collect(s,k,x,counts[stage],*seeds(cfg,seed,stage,m),cfg)
                    assert used==int(uses[stage])
                    k=learner(k,z,method,cfg['eta'],cfg['rank'])
                    row.update(info,**diagnostics(s,private,k),failure=None)
                    failed=not row['stable']
                    if failed: row['failure']='controller_instability'
                except (np.linalg.LinAlgError,FloatingPointError) as error:
                    failed=True; row.update(stable=False,cost=None,gap=None,relative_gap=None,
                                            redundant_loss=None,effective_loss=None,
                                            failure='numerical_failure',failure_detail=str(error))
            row['actual_transitions']=actual; rows.append(row); policies.append(k.copy())
            temp=cp.with_suffix('.tmp')
            with temp.open('wb') as stream:
                np.savez_compressed(stream,identity=np.array(json.dumps(ident,sort_keys=True)),K=k,x=x,
                                    actual=actual,next_stage=stage+1,failed=failed,
                                    rows=np.array(json.dumps(rows,allow_nan=False)),policies=np.array(policies))
            os.replace(temp,cp)
        all_rows.extend(rows); archives[method+'_K']=np.array(policies)
        archives[method+'_final_state']=x
    policy_path=out/'policies'/path.with_suffix('.npz').name; policy_path.parent.mkdir(exist_ok=True)
    np.savez_compressed(policy_path,**archives)
    # Both algorithms see exactly the same initial samples, before any divergence.
    a,b=(next(r for r in all_rows if r['method']==method and r['stage']==1) for method in cfg['methods'])
    for key in ('pulse_energy_mean','postpulse_return_mean','postpulse_return_variance','gram_condition'):
        assert a[key]==b[key],(m,seed,key)
    atomic_json(path,dict(m=m,seed=seed,identity=ident,records=all_rows,
                         assigned_budget=int(grid[-1]),policy_sha256=sha(policy_path),
                         seconds=time.monotonic()-began))
    return dict(m=m,seed=seed,seconds=time.monotonic()-began,
                finals=[{key:r.get(key) for key in ('method','stable','gap','relative_gap')} for r in all_rows if r['stage']==len(counts)])


def worker(cfg,m,seed,out,ident):
    with threadpool_limits(limits=cfg['blas_threads_per_worker']):
        return task(cfg,m,seed,out,ident)


def freeze(cfg,manifest,out,ident):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    frozen=out/'frozen'; frozen.mkdir(exist_ok=True)
    identity_path=frozen/'identity.json'
    if identity_path.exists():
        old=json.loads(identity_path.read_text(encoding='utf-8'))
        if old==ident:return
        assert not list((out/'raw').glob('*.json')) and not list((out/'checkpoints').glob('*.npz')), 'Cannot mix changed sources with existing results'
        # Preserve superseded preflight artifacts before any formal sampling.
        archived=out/('superseded-preflight-'+sha(identity_path)[:12])
        assert frozen.resolve().parent==out.resolve() and archived.resolve().parent==out.resolve()
        frozen.rename(archived); frozen.mkdir()
        if (out/'verification.json').exists():
            (out/'verification.json').rename(archived/'verification.json')
    for p in SOURCES+[str(Path(manifest).resolve().relative_to(ROOT)).replace('\\','/')]:
        dest=frozen/p; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(ROOT/p,dest)
    atomic_json(identity_path,ident)
    atomic_json(out/'resolved_config.json',dict(cfg,schedule=schedule(cfg),identity=ident,
                execution=dict(backend='local',python=sys.executable,output=str(out.resolve()),
                               cache=os.environ.get('NUMBA_CACHE_DIR'),temp=os.environ.get('TEMP'),
                               matplotlib_cache=os.environ.get('MPLCONFIGDIR'))))


def main():
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['verify','run','audit'])
    p.add_argument('--manifest',type=Path,default=ROOT/'configs/actuation_redundancy_20261016.json')
    args=p.parse_args(); cfg=json.loads(args.manifest.read_text(encoding='utf-8')); out=Path(cfg['output'])
    # Require explicit E: cache/temp configuration; never implicitly fill C:.
    required={'NUMBA_CACHE_DIR':str(Path(cfg['cache'])/'numba'), 'MPLCONFIGDIR':str(Path(cfg['cache'])/'matplotlib'),
              'TEMP':cfg['temp'],'TMP':cfg['temp']}
    for key,path in required.items():
        assert os.path.normcase(os.path.abspath(os.environ.get(key,'')))==os.path.normcase(os.path.abspath(path)),(key,path)
        Path(path).mkdir(parents=True,exist_ok=True)
    ident=identity(args.manifest)
    with threadpool_limits(limits=cfg['blas_threads_per_worker']):
        if args.mode=='verify':
            freeze(cfg,args.manifest,out,ident); verify(cfg,out,ident)
        elif args.mode=='run':
            freeze(cfg,args.manifest,out,ident)
            verified=json.loads((out/'verification.json').read_text(encoding='utf-8'))
            assert verified['status']=='PASS' and verified['identity']==ident
            start=time.monotonic(); tasks=[(m,seed) for m in cfg['action_dimensions'] for seed in cfg['trial_seeds']]
            with ProcessPoolExecutor(max_workers=cfg['workers']) as pool:
                futures=[pool.submit(worker,cfg,m,seed,str(out),ident) for m,seed in tasks]
                for done,future in enumerate(as_completed(futures),1):
                    result=future.result(); print(json.dumps(dict(complete=done,total=len(tasks),**result)),flush=True)
                    atomic_json(out/'progress.json',dict(complete=done,total=len(tasks),elapsed_seconds=time.monotonic()-start,last=result))
            atomic_json(out/'completion.json',dict(status='complete',paired_tasks=len(tasks),trajectories=2*len(tasks),
                                                 wall_seconds=time.monotonic()-start,identity=ident))
        else:
            maximum=0.; checked=0
            for path in (out/'raw').glob('*.json'):
                data=json.loads(path.read_text(encoding='utf-8')); assert data['identity']==ident
                policy_path=out/'policies'/path.with_suffix('.npz').name; assert sha(policy_path)==data['policy_sha256']
                s,private=make_system(cfg,data['m'])
                with np.load(policy_path) as archive:
                    for row in data['records']:
                        if not row['observed'] or not row['stable']:continue
                        q=diagnostics(s,private,archive[row['method']+'_K'][row['stage']])
                        for key in ('gap','relative_gap','redundant_loss','effective_loss'):
                            diff=abs(q[key]-row[key]);maximum=max(maximum,diff)
                            assert np.isclose(q[key],row[key],rtol=1e-9,atol=1e-9)
                        checked+=1
            atomic_json(out/'audit.json',dict(status='PASS',checked_stable_policies=checked,max_absolute_difference=maximum,
                                             identity=ident))
            print(json.dumps(dict(audit='PASS',checked=checked,maximum=maximum)),flush=True)


if __name__=='__main__':
    main()
