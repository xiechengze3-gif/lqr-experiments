"""Bounded local unknown-rank study: fixed policy and full learning.

Explicit local entrypoint; does not modify historic engines or fake Slurm IDs.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import (atomic_json, orth, rng_for, dare, evaluate, targets,
                           ce_chunk, nominal_chunk, pulse_chunk, pi_gain)
from full_lstd import solve
from npg_batched_collector import batched_chunk, prepare
from adaptive_rank import noise_proxy, select, ce_update, pi_update


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(manifest):
    sources = [Path(__file__), ROOT/'scripts/adaptive_rank.py', ROOT/'dense_scaling.py',
        ROOT/'scripts/full_lstd.py', ROOT/'scripts/npg_batched_collector.py']
    return dict(manifest_sha256=digest(manifest),
                sources={str(p.relative_to(ROOT)): digest(p) for p in sources})


def make_system(task, cfg):
    n, r = task['n'], task['r']
    rng = rng_for(202610112, n, task['system_seed'])
    o, u, v = orth(rng, n), orth(rng, n), orth(rng, n)
    singular = np.ones(n)
    if task['spectrum'] == 'exact':
        singular[r:] = 0.
    elif task['spectrum'] == 'gap':
        singular[r:] = .05
    elif task['spectrum'] == 'decay':
        singular[:] = np.arange(1, n+1, dtype=float)**(-.7)
    elif task['spectrum'] != 'flat':
        raise ValueError(task['spectrum'])
    a, b = cfg['alpha']*o, (u*singular)@v.T
    q, rr, k0 = np.eye(n), np.eye(n), np.zeros((n, n))
    ks, p = dare(a, b, q, rr)
    s = dict(A=a, B=b, Q=q, R=rr, W=np.eye(n), K0=k0, Kstar=ks,
             Jstar=float(np.trace(p)), initial_gap=n/(1-cfg['alpha']**2)-float(np.trace(p)))
    return s, dict(B_singular=singular.tolist(), p0=1/(1-cfg['alpha']**2),
        matrix_sha256={key: hashlib.sha256(s[key].tobytes()).hexdigest()
                       for key in ('A', 'B', 'Q', 'R', 'K0')})


def model_fit(z, y):
    return np.linalg.lstsq(z, y, rcond=None)[0].T


def transition_data(s, k, x, count, burn, rng):
    n = len(x)
    f = np.ascontiguousarray(s['A']-s['B']@k)
    x, _ = nominal_chunk(f, x, rng.normal(size=(burn, n)))
    z, y = np.empty((count, 2*n)), np.empty((count, n))
    for lo in range(0, count, 256):
        size = min(256, count-lo)
        x, zz, yy = ce_chunk(f, s['B'], k, x, rng.normal(size=(size, n)),
                             rng.normal(size=(size, n)))
        z[lo:lo+size], y[lo:lo+size] = zz, yy
    return x, z, y


def lstd_fit(z, y, k, q, r, cfg):
    n = len(k)
    nxt = np.concatenate((y, -y@k.T), axis=1)
    costs = np.einsum('ij,ij->i', z[:, :n]@q, z[:, :n])
    costs += np.einsum('ij,ij->i', z[:, n:]@r, z[:, n:])
    h, diag = solve(z, nxt, costs, rtol=cfg['solver_rtol'], restart=40, maxiter=10)
    if not diag['converged']:
        return None, diag
    return (h[n:, n:]-r, h[n:, :n]), diag


def direct_data(s, k, x, count, burn, horizon, rng):
    """Original adjacent labels, also retain half-batch sufficient statistics."""
    n = len(x)
    f = np.ascontiguousarray(s['A']-s['B']@k)
    cost = np.ascontiguousarray(s['Q']+k.T@s['R']@k)
    x, _ = nominal_chunk(f, x, rng.normal(size=(burn, n)))
    x, _, value = pulse_chunk(f, s['B'], cost, x, rng.normal(size=(1, n)),
                             rng.normal(size=(1, horizon, n)))
    previous = value[-1]
    stats = [dict(gram=np.zeros((n,n)), cross=np.zeros((n,n)), g=np.zeros((n,n)), count=0)
             for _ in range(2)]
    prepared = prepare(f, s['B'], horizon)
    # Chunk boundary matches the half boundary; never reset the state/baseline.
    for half in range(2):
        st = stats[half]
        for lo in range(0, count//2, 256):
            size = min(256, count//2-lo)
            pulses, noises = rng.normal(size=(size,n)), rng.normal(size=(size,horizon,n))
            x, starts, values = batched_chunk(f, s['B'], cost, x, pulses, noises, prepared)
            delta = np.empty(size)
            delta[0], delta[1:] = values[0]-previous, values[1:]-values[:-1]
            previous = values[-1]
            st['gram'] += starts.T@starts
            st['cross'] += (-pulses*delta[:,None]/2).T@starts
            st['g'] += ((pulses*delta[:,None]).T@pulses-delta.sum()*np.eye(n))/2
            st['count'] += size

    def estimate(st):
        z = np.linalg.solve(st['gram'], st['cross'].T).T
        g = st['g']/st['count']
        return g, g@k-z, z
    full = {key: stats[0][key]+stats[1][key] for key in stats[0]}
    return x, estimate(full), [estimate(st) for st in stats], burn+(count+1)*horizon


def estimate(s, k, x, algorithm, count, cfg, rng):
    diagnostics = {}
    if algorithm in ('DIRECT_PI', 'NPG'):
        x, full, halves, used = direct_data(s, k, x, count, cfg['burn'], cfg['horizon'], rng)
        raw = full[2] if algorithm == 'NPG' else np.concatenate(full[:2], axis=1)
        split = [part[2] if algorithm == 'NPG' else np.concatenate(part[:2], axis=1) for part in halves]
        return x, full, noise_proxy(*split), used, diagnostics
    x, z, y = transition_data(s, k, x, count, cfg['burn'], rng)
    mid = count//2
    if algorithm == 'CE':
        full = model_fit(z, y)
        split = [model_fit(z[:mid], y[:mid]), model_fit(z[mid:], y[mid:])]
        raw, halves = full[:, len(k):], [part[:, len(k):] for part in split]
        return x, full, noise_proxy(*halves), count+cfg['burn'], diagnostics
    full, diag = lstd_fit(z, y, k, s['Q'], s['R'], cfg)
    diagnostics['full_solver'] = diag
    if full is None:
        return x, None, None, count+cfg['burn'], diagnostics
    halves, diags = [], []
    for zz, yy in ((z[:mid], y[:mid]), (z[mid:], y[mid:])):
        part, diag = lstd_fit(zz, yy, k, s['Q'], s['R'], cfg)
        halves.append(part); diags.append(diag)
    diagnostics['split_solvers'] = diags
    scale = None if any(p is None for p in halves) else noise_proxy(
        np.concatenate(halves[0], axis=1), np.concatenate(halves[1], axis=1))
    return x, full, scale, count+cfg['burn'], diagnostics


def update(s, k, algorithm, full, scale, method, rank, cfg):
    # Adaptive calls cannot access rank; only the known-rank reference receives it.
    known = rank if method == 'known_rank' else None
    if algorithm == 'CE':
        n = len(k)
        candidate, b, info = ce_update(full[:, :n], full[:, n:], s['Q'], s['R'], method, scale, known)
        return candidate, dict(B=b), info
    if algorithm == 'NPG':
        z, _, info = select(full[2], method, scale, known)
        candidate = k-cfg['npg_eta']*(s['R']@k+z)
        return candidate, dict(Z=z), info
    candidate, g, c, info = pi_update(*full[:2], s['R'], method, scale, known)
    return candidate, dict(G=g, C=c, Z=g@k-c), info


def diagnostics(s, k, algorithm, corrected, raw, rank, cfg):
    if algorithm == 'CE':
        return dict(estimation_error_fro2=float(np.sum((corrected['B']-s['B'])**2)))
    truth = targets(s, k, cfg['horizon'])
    zraw = raw[2] if algorithm in ('DIRECT_PI','NPG') else raw[0]@k-raw[1]
    # True kernel is diagnostics-only; flat/approximate spectra have no kernel.
    _, singular, vt = np.linalg.svd(s['B'], full_matrices=False)
    kernel = vt[singular < 1e-10].T
    return dict(estimation_error_fro2=float(np.sum((corrected['Z']-truth['Z'])**2)),
        raw_redundant_noise_fro2=float(np.sum((kernel.T@(zraw-truth['Z']))**2)),
        corrected_redundant_noise_fro2=float(np.sum((kernel.T@(corrected['Z']-truth['Z']))**2)),
        finite_horizon_bias_fro2=float(np.sum((truth['ZH']-truth['Z'])**2)))


def run_task(task, cfg, out, ident):
    path = out/'raw'/f"task-{task['id']:03d}.json"
    if path.exists():
        saved = json.loads(path.read_text())
        if saved['identity'] != ident or saved['task'] != task:
            raise RuntimeError('Completed output identity mismatch')
        return
    start = time.monotonic()
    s, sysdiag = make_system(task, cfg)
    records = []
    for algorithm in cfg['algorithms']:
        # Mechanism: one full estimate and the same auxiliary splits for ALL arms.
        for location, k in (('K0', s['K0']), ('Kstar', s['Kstar'])):
            for count in cfg['fixed_budgets']:
                _, full, scale, used, solver = estimate(s, k, np.zeros(task['n']), algorithm,
                    count, cfg, rng_for(202610113, task['n'], task['system_seed'],
                                       task['trial_seed'], int(location=='Kstar')))
                for method in cfg['methods']:
                    row = dict(phase='fixed', location=location, algorithm=algorithm,
                        method=method, N=count, transitions=used, solver=solver)
                    record_update(row, s, k, algorithm, full, scale, method, task['r'], cfg)
                    records.append(row)
        # Full learning: only innovation seeds shared after policies diverge.
        for method in cfg['methods']:
            k, x, total, actual_total, failed = s['K0'].copy(), np.zeros(task['n']), 0, 0, False
            q, _ = evaluate(s, k)
            records.append(dict(phase='learning', algorithm=algorithm, method=method,
                                stage=0, N=0, transitions=0, actual_transitions=0, **q))
            for stage, count in enumerate(cfg['schedule'], 1):
                used = cfg['burn']+(count+1)*cfg['horizon'] if algorithm in ('DIRECT_PI','NPG') else cfg['burn']+count
                total += used
                row = dict(phase='learning', algorithm=algorithm, method=method,
                           stage=stage, N=count, transitions=total)
                if failed:
                    row.update(stable=False, gap=None, failure='prior_failure', observed=False)
                else:
                    x, full, scale, actual, solver = estimate(s, k, x, algorithm, count, cfg,
                        rng_for(202610114, task['n'], task['system_seed'], task['trial_seed'], stage))
                    assert actual == used
                    actual_total += actual
                    row['solver'] = solver
                    candidate = record_update(row, s, k, algorithm, full, scale, method, task['r'], cfg)
                    failed = not row['stable']
                    if candidate is not None:
                        k = candidate
                row['actual_transitions'] = actual_total
                records.append(row)
            atomic_json(out/'progress.json', dict(task=task, algorithm=algorithm, method=method,
                        seconds=time.monotonic()-start, record_count=len(records)))
    atomic_json(path, dict(task=task, identity=ident, system=sysdiag, records=records,
        seconds=time.monotonic()-start, execution=dict(location='local', host=platform.node(),
        python=platform.python_version(), threads=1, slurm_job_id=None)))
    print(json.dumps(dict(task_id=task['id'], spectrum=task['spectrum'],
                         seconds=time.monotonic()-start)), flush=True)


def record_update(row, s, k, algorithm, full, scale, method, rank, cfg):
    row['observed'] = True
    if full is None or (method.startswith('adaptive_') and scale is None):
        row.update(stable=False, gap=None, failure='full_solver_failure' if full is None else 'split_solver_failure')
        return None
    try:
        candidate, corrected, info = update(s, k, algorithm, full, scale, method, rank, cfg)
        row.update(info)
        quality, _ = evaluate(s, candidate)
        row.update(quality, policy_sha256=hashlib.sha256(candidate.tobytes()).hexdigest())
        row.update(diagnostics(s, k, algorithm, corrected, full, rank, cfg))
        if not quality['stable']:
            row['failure'] = 'unstable_controller'
        return candidate
    except (ValueError, np.linalg.LinAlgError) as error:
        row.update(stable=False, gap=None, failure=type(error).__name__, failure_detail=str(error))
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--task-id', type=int)
    parser.add_argument('--verification', required=True, type=Path)
    args = parser.parse_args()
    from threadpoolctl import threadpool_limits
    cfg = json.loads(args.manifest.read_text())
    ident = identity(args.manifest)
    proof = json.loads(args.verification.read_text())
    if proof['status'] != 'PASS' or proof['identity'] != ident:
        raise RuntimeError('Independent verification for these exact sources/config is required')
    args.output.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=1):
        for task in cfg['tasks']:
            if args.task_id is None or task['id'] == args.task_id:
                run_task(task, cfg, args.output, ident)
    atomic_json(args.output/'completion.json', dict(status='COMPLETE', identity=ident,
        task_ids=[t['id'] for t in cfg['tasks'] if args.task_id is None or t['id']==args.task_id]))


if __name__ == '__main__':
    main()
