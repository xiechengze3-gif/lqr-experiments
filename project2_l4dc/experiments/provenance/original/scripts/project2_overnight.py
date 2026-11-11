"""Targeted v4 PI and one-stage Stein evidence; Slurm compute nodes only."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from scipy.linalg import cho_factor, cho_solve, eigvalsh, solve_discrete_lyapunov
from dense_scaling import (atomic_json, dare, evaluate, nominal_chunk, op, orth,
                           psd, pulse_chunk, require_compute, rng_for, system, targets, trunc)
from npg_batched_collector import batched_chunk, prepare
from direct_stein_final import correct as old_correct, fit, sufficient


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(path, rows):
    if not rows:
        return
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader(); writer.writerows(rows)


def add(a, b, sign=1):
    return {k: a[k]+sign*b[k] for k in a}


def make_system(spec):
    n, m, rank, seed = [spec[k] for k in ('n', 'm', 'r', 'seed')]
    if n == m and spec.get('family', 'isotropic') == 'isotropic':
        s = system(dict(n=n, m=m, r=rank, system_seed=seed,
                        family='coupled_unstable', stabilizer='isotropic',
                        tail=0., tail_shape='energy'))
    else:
        rng = rng_for(2026102051, n, rank, seed)
        u, v = orth(rng, n), orth(rng_for(2026102052, m, seed), m)
        latent = np.diag(np.r_[np.full(rank, 1.08), np.linspace(.2, .6, n-rank)])
        latent += .04*np.diag(np.ones(n-1), 1)
        singular = np.linspace(1.2, .9, rank)
        a = u@latent@u.T; b = (u[:, :rank]*singular)@v[:, :rank].T
        effective = (.4/singular)[:, None]*u[:, :rank].T
        null = rng.normal(size=(m-rank, n)); null *= .35/np.linalg.norm(null)
        k0 = v@np.vstack((effective, null))
        ks, pstar = dare(a, b, np.eye(n), np.eye(m))
        p0 = solve_discrete_lyapunov((a-b@k0).T, np.eye(n)+k0.T@k0)
        s = dict(A=a, B=b, Q=np.eye(n), R=np.eye(m), W=np.eye(n), K0=k0,
                 Kstar=ks, Jstar=float(np.trace(pstar)),
                 initial_gap=float(np.trace(p0-pstar)))
    q0, p0 = evaluate(s, s['K0'])
    assert q0['stable'] and s['initial_gap'] > 0
    s['P0'] = p0
    s['p0_actual'] = float(eigvalsh(p0)[-1])
    s['npg_eta'] = 1/(op(s['R'])+2*op(s['B'])**2*s['p0_actual'])
    return s


def quality(s, k):
    q, p = evaluate(s, k)
    q['g'] = q['gap']/s['initial_gap'] if p is not None else None
    q['P_relative_max'] = float(eigvalsh(p, s['P0'])[-1]) if p is not None else None
    q['K_rank'] = int(np.linalg.matrix_rank(k, tol=1e-9))
    return q


def v4_correct(g, z, method, rank, halves=None):
    gp = psd(g); matrix = np.concatenate((gp, z), axis=1)
    threshold = None
    if method == 'dense':
        retained = len(g)
    elif method == 'known_rank':
        retained = rank
    elif method == 'adaptive':
        mats = [np.concatenate((psd(a), b), axis=1) for a, b in halves]
        threshold = op(mats[0]-mats[1])/2
        retained = int(np.count_nonzero(np.linalg.svd(matrix, compute_uv=False)>threshold))
    else:
        raise ValueError(method)
    if retained == len(g):
        return gp, z.copy(), retained, threshold
    u = np.linalg.svd(matrix, full_matrices=False)[0][:, :retained]
    gg = u@(u.T@gp@u)@u.T
    return (gg+gg.T)/2, u@(u.T@z), retained, threshold


def greedy(k, r, g, z):
    lhs = r+g
    rhs = g@k-z
    candidate = cho_solve(cho_factor((lhs+lhs.T)/2), rhs)
    residual = np.linalg.norm(lhs@candidate-rhs)/max(1., np.linalg.norm(rhs))
    assert residual < 1e-9
    return candidate


def collect_prefixes(s, k, x, budgets, rng, h=16, burn=512, sigma=1.):
    """One continuous trajectory; exact common prefixes and half statistics."""
    n, m = k.shape[1], k.shape[0]
    f = np.ascontiguousarray(s['A']-s['B']@k)
    cost = np.ascontiguousarray(s['Q']+k.T@s['R']@k)
    x, _ = nominal_chunk(f, x, rng.normal(size=(burn, n)))
    x, _, y = pulse_chunk(f, s['B'], cost, x, sigma*rng.normal(size=(1, m)),
                           rng.normal(size=(1, h, n)))
    previous = float(y[-1]); prepared = prepare(f, s['B'], h)
    assert all(b%2 == 0 and b//2 >= n for b in budgets)
    stops = sorted(set(budgets)|{b//2 for b in budgets})
    done = 0; accum = None; saved = {}; weighted = np.zeros((n, n))
    ds = dss = 0.
    for stop in stops:
        while done < stop:
            size = min(256, stop-done)
            pulses = sigma*rng.normal(size=(size, m))
            noises = rng.normal(size=(size, h, n))
            x, starts, y = batched_chunk(f, s['B'], cost, x, pulses, noises, prepared)
            delta = np.diff(np.r_[previous, y])
            stats = sufficient(starts, pulses, y, previous, sigma)
            accum = stats if accum is None else add(accum, stats)
            weighted += (starts*delta[:, None]).T@(starts*delta[:, None])/(4*sigma**2)
            ds += float(delta.sum()); dss += float(delta@delta)
            previous = float(y[-1]); done += size
        saved[done] = {key: value.copy() if hasattr(value, 'copy') else value for key, value in accum.items()}
        if done in budgets:
            g, z, diag = fit(accum)
            halves = [fit(saved[done//2])[:2], fit(add(accum, saved[done//2], -1))[:2]]
            yield dict(N=done, x=x.copy(), G=g, Z=z, halves=halves, stats=saved[done],
                       Gamma=weighted.copy(), delta_variance=dss/done-(ds/done)**2,
                       transitions=burn+(done+1)*h, **diag)


def pulse_covariance(s, k, h, sigma=1.):
    f = s['A']-s['B']@k
    power = np.eye(len(f)); innovation = np.zeros_like(f)
    for _ in range(h):
        innovation += power@s['W']@power.T
        last = power; power = power@f
    innovation += sigma**2*last@s['B']@s['B'].T@last.T
    cov = solve_discrete_lyapunov(power, innovation)
    assert np.linalg.norm(cov-power@cov@power.T-innovation) < 1e-7*max(1., np.linalg.norm(cov))
    return cov


def one_step_rows(s, k, data, rank):
    g, z, halves = data['G'], data['Z'], data['halves']
    h = data['H']; truth = targets(s, k, h)
    rows = []
    for method in ('dense', 'known_rank', 'adaptive'):
        gg, zz, retained, threshold = v4_correct(g, z, method, rank, halves)
        q = quality(s, greedy(k, s['R'], gg, zz))
        rows.append(dict(algorithm='v4_PI', method=method, retained_rank=retained,
                         threshold=threshold, G_error_fro2=float(np.sum((gg-truth['G'])**2)),
                         Z_error_fro2=float(np.sum((zz-truth['Z'])**2)), **q))
    for method in ('known_rank',):
        gg, zz, info = old_correct(g, z, method, halves, rank)
        q = quality(s, greedy(k, s['R'], gg, zz))
        rows.append(dict(algorithm='old_GZ_PI', method=method, **q))
        rawc = g@k-z
        u = np.linalg.svd(np.concatenate((g, rawc), axis=1), full_matrices=False)[0][:, :rank]
        oldg, oldc = u@psd(u.T@g@u)@u.T, u@(u.T@rawc)
        oldk = np.linalg.solve(s['R']+oldg, oldc)
        rows.append(dict(algorithm='old_GC_PI', method=method, **quality(s, oldk)))
    step = s['npg_eta']
    for method, zz in [('dense', z), ('known_rank', trunc(z, rank))]:
        q = quality(s, k-step*(s['R']@k+zz))
        rows.append(dict(algorithm='NPG', method=method, eta=step,
                         Z_error_fro2=float(np.sum((zz-truth['Z'])**2)), **q))
    return rows


def actor_task(spec, out, identity):
    dest = out/'actor'/f"{spec['tag']}-{spec['id']:04d}.json"
    if dest.exists():
        assert json.loads(dest.read_text())['identity'] == identity
        return
    begin = time.monotonic(); s = make_system(spec)
    k, x, total = s['K0'].copy(), np.zeros(spec['n']), 0
    rows = [dict(stage=0, transitions=0, **quality(s, k))]
    status = 'completed'; start_stage = 1
    checkpoint = dest.with_suffix('.npz')
    if checkpoint.exists():
        with np.load(checkpoint, allow_pickle=False) as a:
            assert str(a['identity']) == identity
            k, x, total = a['K'].copy(), a['x'].copy(), int(a['total'])
            rows = json.loads(str(a['rows'])); start_stage = int(a['next_stage'])
            status = str(a['status'])
    for stage in range(start_stage, spec['updates']+1):
        if status != 'completed':
            break
        used = spec['burn']+(spec['N']+1)*spec['H']
        try:
            result = list(collect_prefixes(s, k, x, [spec['N']],
                rng_for(2026102061, spec['n'], spec['r'], spec['seed'], spec['trial'], stage),
                spec['H'], spec['burn']))[-1]
            x = result['x']; total += result['transitions']
            gg, zz, retained, threshold = v4_correct(result['G'], result['Z'], spec['method'],
                                                    spec['r'], result['halves'])
            candidate = greedy(k, s['R'], gg, zz)
            q = quality(s, candidate)
            rows.append(dict(stage=stage, transitions=total, retained_rank=retained,
                             threshold=threshold, **q))
            k = candidate
            if not q['stable']:
                status = 'controller_instability'
        except (ArithmeticError, ValueError, np.linalg.LinAlgError) as e:
            if total < stage*used:
                total += used
            status = 'numerical_failure'
            rows.append(dict(stage=stage, transitions=total, stable=False, gap=None, g=None,
                             detail=str(e), failure=status))
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        temp = checkpoint.with_suffix('.tmp')
        with temp.open('wb') as stream:
            np.savez(stream, K=k, x=x, total=total, rows=json.dumps(rows),
                     next_stage=stage+1, status=status, identity=identity)
        temp.replace(checkpoint)
    atomic_json(dest, dict(identity=identity, spec=spec, status=status, rows=rows,
        seconds=time.monotonic()-begin, actual_transitions=total,
        planned_transitions=spec['updates']*(spec['burn']+(spec['N']+1)*spec['H']),
        job=os.environ['SLURM_JOB_ID'], host=socket.gethostname()))
    print(json.dumps(dict(actor=spec, status=status, seconds=time.monotonic()-begin, final=rows[-1])), flush=True)


def mechanism_task(spec, out, identity):
    dest = out/'mechanism'/f"task-{spec['id']:04d}.json"
    if dest.exists():
        assert json.loads(dest.read_text())['identity'] == identity
        return
    begin = time.monotonic(); s = make_system(spec)
    k = s['Kstar'] if spec['policy'] == 'Kstar' else s['K0']
    truth = targets(s, k, spec['H'])
    ub = np.linalg.svd(s['B'].T, full_matrices=True)[0]
    null = ub[:, spec['r']:]; n, m, rank = spec['n'], spec['m'], spec['r']
    cov = pulse_covariance(s, k, spec['H'])
    rows = []; noise_rows = []
    for data in collect_prefixes(s, k, np.zeros(n), spec['budgets'],
            rng_for(2026102062, n, m, rank, spec['seed'], spec['trial'], spec['H'],
                    0 if spec['policy']=='Kstar' else 1), spec['H'], spec['burn']):
        data['H'] = spec['H']; count = data['N']
        meta = dict(N=count, transitions=data['transitions'])
        for row in one_step_rows(s, k, data, rank):
            rows.append(dict(meta, **row))
        gram, gamma = data['stats']['gram'], data['Gamma']
        inv = np.linalg.inv(gram)
        expected = (m-rank)*float(np.trace(inv@gamma@inv))
        null_error = float(np.sum((null.T@data['Z'])**2))
        eig = eigvalsh(gamma); trace = float(np.sum(eig)); top = float(eig[-1])
        knownz = np.linalg.solve(cov, (data['stats']['cross']/count).T).T
        knownnull = float(np.sum((null.T@knownz)**2))
        matrix = np.concatenate((psd(data['G']), data['Z']), axis=1)
        true_joint = np.concatenate((truth['G'], truth['Z']), axis=1)
        mats = [np.concatenate((psd(a), b), axis=1) for a, b in data['halves']]
        threshold = op(mats[0]-mats[1])/2
        record = dict(meta, null_Z_fro2=null_error, null_conditional_expected_fro2=expected,
            null_to_conditional_mean=null_error/expected,
            null_normalized=count*null_error/((m-rank)*spec['H']*n*n),
            known_cov_null_fro2=knownnull,
            known_cov_null_normalized=count*knownnull/((m-rank)*spec['H']*n*n),
            Gamma_trace=trace, Gamma_op=top, Gamma_effective_rank=trace/top,
            conditional_A_half_mean_bound=math.exp(-(m-rank)*trace/(16*top)),
            null_cross_to_conditional_mean=float(np.sum((null.T@data['stats']['cross'])**2))/((m-rank)*trace),
            delta_variance=data['delta_variance'], gram_condition=data['gram_condition'],
            Gram_population_relative_fro=float(np.linalg.norm(gram/count-cov)/np.linalg.norm(cov)),
            G_finite_H_bias_fro2=float(np.sum((truth['G']-truth['GH'])**2)),
            Z_finite_H_bias_fro2=float(np.sum((truth['Z']-truth['ZH'])**2)),
            joint_total_op=op(matrix-true_joint), adaptive_threshold=threshold,
            threshold_covers_total=bool(op(matrix-true_joint)<=threshold),
            effective_dimension=(m-rank)*n,
            dimension_over_log5=(m-rank)*n/math.log(100*count/.05)**5)
        for method, zz in [('dense', knownz), ('known_rank', trunc(knownz, rank))]:
            q = quality(s, k-s['npg_eta']*(s['R']@k+zz))
            rows.append(dict(meta, algorithm='known_cov_NPG', method=method, eta=s['npg_eta'], **q))
        noise_rows.append(record)
    atomic_json(dest, dict(identity=identity, spec=spec, rows=rows, noise=noise_rows,
        seconds=time.monotonic()-begin, physical_transitions=spec['burn']+(max(spec['budgets'])+1)*spec['H'],
        initial_gap=s['initial_gap'], p0_actual=s['p0_actual'], eta=s['npg_eta'],
        job=os.environ['SLURM_JOB_ID'], host=socket.gethostname()))
    print(json.dumps(dict(mechanism=spec['id'], seconds=time.monotonic()-begin)), flush=True)


def saved_evidence(out, identity):
    rows = []; certificates = []
    inputs = ROOT/'inputs'
    for dest in sorted((inputs/'estimates').glob('*.npz')):
        archived = json.loads(dest.with_suffix('.json').read_text())
        spec = archived['meta']; n, rank, seed = spec['n'], spec['r'], spec['system_seed']
        if rank == n:
            continue
        s = system(dict(n=n, m=n, r=rank, system_seed=seed, family='coupled_unstable',
                        stabilizer='isotropic', tail=spec['tau'], tail_shape='energy'))
        _, p0 = evaluate(s, s['K0']); s['P0'] = p0
        s['p0_actual'] = float(eigvalsh(p0)[-1])
        s['npg_eta'] = 1/(op(s['R'])+2*op(s['B'])**2*s['p0_actual'])
        with np.load(dest, allow_pickle=False) as a:
            data = dict(G=a['G'].copy(), Z=a['Z'].copy(), H=16,
                        halves=[(a['G_half1'].copy(), a['Z_half1'].copy()),
                                (a['G_half2'].copy(), a['Z_half2'].copy())])
        for row in one_step_rows(s, s['K0'], data, rank):
            rows.append(dict(source=dest.name, n=n, r=rank, seed=seed,
                             N=spec['blocks'], tau=spec['tau'], **row))
    for dest in sorted((inputs/'policies').glob('*.npz')):
        archived = json.loads(dest.with_suffix('.json').read_text()); meta = archived['meta']
        system_path = inputs/'systems'/f"n{meta['n']}-r{meta['r']}-s{meta['system_seed']}.npz"
        with np.load(system_path, allow_pickle=False) as a:
            s = {key: a[key].copy() for key in a.files}
            s['Jstar'] = float(s['Jstar']); s['initial_gap'] = float(s['initial_gap'])
        _, p0 = evaluate(s, s['K0']); s['P0'] = p0
        with np.load(dest, allow_pickle=False) as a:
            q = quality(s, a['K'])
        np.testing.assert_allclose(q['gap'], archived['rows'][-1]['gap'], rtol=2e-8, atol=1e-7)
        certificates.append(dict(source=dest.name, **meta, **q))
    write_csv(out/'saved'/'postprocessing.csv', rows)
    write_csv(out/'saved'/'terminal_certificates.csv', certificates)
    atomic_json(out/'saved'/'receipt.json', dict(identity=identity, one_step_rows=len(rows),
        terminal_policies=len(certificates), source='uploaded frozen saved arrays; zero new sampled transitions',
        job=os.environ['SLURM_JOB_ID']))


def verify(out, identity):
    begin = time.monotonic(); checks = []
    s = make_system(dict(n=12, m=12, r=2, seed=2799))
    truth = targets(s, s['K0'], 16)
    exact = np.linalg.solve(s['R']+truth['G'], truth['C'])
    for method, rank in [('dense', 12), ('known_rank', 2)]:
        gg, zz, _, _ = v4_correct(truth['G'], truth['Z'], method, rank)
        np.testing.assert_allclose(greedy(s['K0'], s['R'], gg, zz), exact, atol=2e-11)
        checks.append('population greedy identity '+method)
    gg, zz, _, _ = v4_correct(truth['G'], truth['Z'], 'known_rank', 2)
    assert np.linalg.matrix_rank(greedy(s['K0'], s['R'], gg, zz), tol=1e-9) <= 2
    checks.append('general R rank bound')
    rng = rng_for(99); f=s['A']-s['B']@s['K0']; cost=s['Q']+s['K0'].T@s['R']@s['K0']
    pulses=rng.normal(size=(13,12)); noises=rng.normal(size=(13,8,12)); x=rng.normal(size=12)
    original=pulse_chunk(f,s['B'],cost,x,pulses,noises)
    batched=batched_chunk(f,s['B'],cost,x,pulses,noises,prepare(f,s['B'],8))
    for a,b in zip(original,batched):
        np.testing.assert_allclose(a,b,rtol=1e-11,atol=1e-10)
    checks.append('continuous collector equality')
    vals=list(collect_prefixes(s,s['K0'],np.zeros(12),[256,1024],rng_for(1234),8))
    for d in vals:
        full=d['stats']; halves=[d['halves'][0],d['halves'][1]]
        assert d['transitions']==512+(d['N']+1)*8
        assert all(np.all(np.isfinite(a)) for a in (d['G'],d['Z'],d['Gamma']))
        assert eigvalsh(d['Gamma'])[0] > 0
    checks += ['prefix and primitive accounting', 'positive conditional covariance']
    # Dense and rank-m paths share the exact clipping and solve code.
    d=vals[-1]
    for a,b in zip(v4_correct(d['G'],d['Z'],'dense',12)[:2],v4_correct(d['G'],d['Z'],'known_rank',12)[:2]):
        np.testing.assert_array_equal(a,b)
    checks.append('full rank identity')
    timings=[]
    for n in (50,100):
        plant=make_system(dict(n=n,m=n,r=4,seed=2798)); start=time.monotonic()
        list(collect_prefixes(plant,plant['Kstar'],np.zeros(n),[8192],rng_for(444,n),16))
        timings.append(dict(n=n,N=8192,H=16,seconds=time.monotonic()-start))
    atomic_json(out/'verification.json',dict(status='PASS',identity=identity,checks=checks,
        benchmarks=timings,seconds=time.monotonic()-begin,job=os.environ['SLURM_JOB_ID'],
        environment={key:os.environ.get(key) for key in ('TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','OPENBLAS_NUM_THREADS')}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['verify','pilot','actor','mechanism','saved'])
    parser.add_argument('--index',type=int,default=0)
    parser.add_argument('--manifest',type=Path,required=True)
    args=parser.parse_args(); require_compute()
    cfg=json.loads(args.manifest.read_text()); out=Path(cfg['output']); out.mkdir(parents=True,exist_ok=True)
    identity=sha(args.manifest)+'|'+sha(__file__)
    if args.mode=='verify':
        verify(out,identity)
    elif args.mode=='saved':
        saved_evidence(out,identity)
    elif args.mode in ('pilot','actor'):
        actor_task(cfg[args.mode+'_tasks'][args.index],out,identity)
    else:
        mechanism_task(cfg['mechanism_tasks'][args.index],out,identity)


if __name__=='__main__':
    main()
