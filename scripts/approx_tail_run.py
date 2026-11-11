"""CE, full-LSTD LSPI, and adjacent-return NPG on the same declared systems."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import (require_compute, atomic_json, ce, evaluate, targets, trunc,
                          pi_gain, dare, rng_for, pulse_moments)
from approx_tail_system import system, ETA
from full_lstd import solve, verify as verify_lstd
from pi_ce_rank import data
from npg_batched_collector import collect


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance(manifest):
    return dict(manifest_sha256=sha(manifest), source_sha256=sha(__file__),
        system_sha256=sha(system.__code__.co_filename), lstd_sha256=sha(solve.__code__.co_filename),
        collector_sha256=sha(collect.__code__.co_filename),
        engine_sha256=sha(evaluate.__code__.co_filename), slurm_job_id=os.environ['SLURM_JOB_ID'])


def run(manifest, profile, task_id, output):
    cfg = json.loads(Path(manifest).read_text())
    task = cfg['tasks'][task_id]
    setting = cfg['smoke_setting'] if profile=='npg-smoke' else cfg['profiles'][profile]
    s, start = system(task), time.monotonic()
    algorithm, records = setting['algorithm'], []
    out = Path(output)/profile/'raw'
    payload = dict(task=task, profile=profile, algorithm=algorithm,
                   diagnostics=s['diagnostics'], **provenance(manifest))
    if algorithm == 'CE':
        records, _ = ce(dict(task, budgets=setting['budgets'], sigma=1.), s)
    else:
        schedule = setting['schedule']
        for method in ('raw', 'truncated'):
            k, x, total = s['K0'].copy(), np.zeros(task['n']), 0
            quality, p = evaluate(s, k)
            records.append(dict(method=method, stage=0, N=0, transitions=0, observed=True, **quality))
            for stage, count in enumerate(schedule):
                row = dict(method=method, stage=stage+1, N=count, observed=True)
                if algorithm == 'LSPI':
                    x, z, nxt, costs = data(s, k, x, count, cfg['burn'],
                                           rng_for(202610082, task['n'], task['system_seed'], stage))
                    total += count+cfg['burn']
                    h, diag = solve(z, nxt, costs, rtol=cfg['solver_rtol'],
                                   restart=40, maxiter=10)
                    del z, nxt, costs
                    row['solver'] = diag
                    if not diag['converged']:
                        row.update(transitions=total, stable=False, gap=None, failure='LSTD_solver_failure')
                        records.append(row)
                        break
                    n = task['n']
                    g, c = h[n:, n:]-s['R'], h[n:, :n]
                    truth = targets(s, k, cfg['horizon'], p)
                    row['joint_error_fro2'] = float(np.sum((g-truth['G'])**2)+np.sum((c-truth['C'])**2))
                    candidate, _, _ = pi_gain(s, g, c, None if method == 'raw' else task['r'])
                elif algorithm == 'NPG':
                    truth = targets(s, k, cfg['horizon'], p)
                    _, x, raw, _, gram, used = next(collect(s, k, x, [count], cfg['horizon'], 1.,
                        rng_for(202610083, task['n'], task['system_seed'], stage), burn=cfg['burn']))
                    total += used
                    zhat = raw if method == 'raw' else trunc(raw, task['r'])
                    row.update(eta=ETA, critic_error_fro2=float(np.sum((zhat-truth['Z'])**2)),
                        horizon_bias_fro2=float(np.sum((truth['ZH']-truth['Z'])**2)),
                        gram_condition=float(np.linalg.cond(gram)))
                    candidate = k-ETA*(s['R']@k+zhat)
                else:
                    raise ValueError(algorithm)
                quality, p = evaluate(s, candidate)
                row.update(transitions=total, **quality)
                records.append(row)
                k = candidate
                atomic_json(out/f'progress-{task_id:03d}.json', dict(payload, records=records))
                if stage % 16 == 15 or algorithm == 'LSPI' or not quality['stable']:
                    print(json.dumps(dict(task_id=task_id, profile=profile, **row)), flush=True)
                if not quality['stable']:
                    break
    atomic_json(out/f'task-{task_id:03d}.json', dict(payload, records=records,
                seconds=time.monotonic()-start))


def reference(manifest, task_id, output):
    cfg = json.loads(Path(manifest).read_text())
    task = cfg['tasks'][task_id]
    s, records, completion = system(task), [], []
    for method in ('raw', 'truncated'):
        b = s['B'] if method == 'raw' else trunc(s['B'], task['r'])
        k, _ = dare(s['A'], b, s['Q'], s['R'])
        quality, _ = evaluate(s, k)
        records.append(dict(algorithm='CE', method=method, finite_horizon=False,
                            stage=0, **quality))
        completion.append(dict(algorithm='CE', method=method, finite_horizon=False,
                               converged=quality['stable'], final_gap=quality['gap']))
    for algorithm in ('LSPI', 'NPG'):
        for finite in ((False,) if algorithm == 'LSPI' else (False, True)):
            for method in ('raw', 'truncated'):
                k = s['K0'].copy()
                converged = False
                cap = 64 if algorithm == 'LSPI' else cfg['reference_cap']
                for stage in range(cap+1):
                    quality, p = evaluate(s, k)
                    if stage <= cfg['npg_stages'] or stage in (256,512,1024,2048) or stage == cap:
                        records.append(dict(algorithm=algorithm, method=method, finite_horizon=finite,
                                            stage=stage, **quality))
                    if not quality['stable']:
                        break
                    truth = targets(s, k, cfg['horizon'], p)
                    if algorithm == 'LSPI':
                        candidate, _, _ = pi_gain(s, truth['G'], truth['C'],
                                                  None if method == 'raw' else task['r'])
                    else:
                        z = truth['ZH' if finite else 'Z']
                        if method == 'truncated':
                            z = trunc(z, task['r'])
                        candidate = k-ETA*(s['R']@k+z)
                    change = float(np.linalg.norm(candidate-k, 'fro'))
                    # Diagnostic-only convergence; production outputs never stop by true costs.
                    converged = change <= cfg['reference_tolerance']
                    if stage == cap:
                        break
                    k = candidate
                    # Always provide matched sampled-update references, even if already converged.
                    if converged and stage >= cfg['npg_stages']:
                        quality, _ = evaluate(s, k)
                        records.append(dict(algorithm=algorithm, method=method, finite_horizon=finite,
                                            stage=stage+1, **quality))
                        break
                quality, _ = evaluate(s, k)
                completion.append(dict(algorithm=algorithm, method=method, finite_horizon=finite,
                    converged=bool(converged and quality['stable']), final_gap=quality['gap'],
                    stages=records[-1]['stage'], last_change_fro=change))
    atomic_json(Path(output)/'reference'/f'task-{task_id:03d}.json',
                dict(task=task, records=records, completion=completion,
                     diagnostics=s['diagnostics'], **provenance(manifest)))
    print(json.dumps(dict(task_id=task_id, reference=completion)), flush=True)


def verify(manifest, output):
    cfg = json.loads(Path(manifest).read_text())
    diagnostics, seen = [], {}
    for task in cfg['tasks']:
        s = system(task)
        hashes = {k:v for k,v in s['diagnostics']['matrix_sha256'].items() if k != 'B'}
        key = (task['n'], task['system_seed'])
        if key in seen:
            assert hashes == seen[key], 'A/Q/R/K0 changed across rank or tail'
        seen[key] = hashes
        r, n = task['r'], task['n']
        spectrum = np.asarray(s['diagnostics']['B_spectrum'])
        assert np.allclose(spectrum[:r], 1., atol=1e-12)
        assert np.allclose(spectrum[r:], s['diagnostics']['tail_singular'], atol=1e-12)
        diagnostics.append(dict(task_id=task['id'], task=task, **s['diagnostics']))
    checks = verify_lstd()
    checks['new_full_rank_update_equivalence'] = True
    for task in cfg['tasks']:
        if task['r']!=task['n']: continue
        s=system(task)
        truth=targets(s,s['K0'],cfg['horizon'])
        raw,_,_=pi_gain(s,truth['G'],truth['C'])
        tr,_,_=pi_gain(s,truth['G'],truth['C'],task['r'])
        assert np.allclose(raw,tr,rtol=1e-10,atol=1e-10)
        assert np.allclose(trunc(truth['Z'],task['r']),truth['Z'],rtol=1e-10,atol=1e-10)
        assert np.allclose(trunc(s['B'],task['r']),s['B'],rtol=1e-10,atol=1e-10)
    synthetic = dict(id=-1, n=6, m=6, r=2, system_seed=0, trial_seed=0, tail_mode='exact', level=0)
    s = system(synthetic)
    # Independent full Bellman recovery on a new dense system, with noiseless transitions.
    rng = rng_for(202610084)
    z = rng.normal(size=(16384, 12))
    y = z[:, :6]@s['A'].T+z[:, 6:]@s['B'].T
    nxt = np.concatenate((y, -y@s['K0'].T), axis=1)
    costs = np.einsum('ij,ij->i', z[:, :6]@s['Q'], z[:, :6])
    costs += np.einsum('ij,ij->i', z[:, 6:]@s['R'], z[:, 6:])
    f = s['A']-s['B']@s['K0']
    p = solve_discrete_lyapunov(f.T, s['Q']+s['K0'].T@s['R']@s['K0'])
    expected = np.block([[s['Q']+s['A'].T@p@s['A'], s['A'].T@p@s['B']],
                         [s['B'].T@p@s['A'], s['R']+s['B'].T@p@s['B']]])
    h, diag = solve(z, nxt, costs)
    assert diag['converged'] and np.allclose(h, expected, rtol=1e-6, atol=1e-7)
    checks['new_dense_bellman_recovery'] = True
    # Paired sequence/OLS equivalence on the new family; preserve baseline and all transitions.
    for tail_mode, level in (('exact', 0), ('singular', .1)):
        s = system(dict(synthetic, tail_mode=tail_mode, level=level))
        old = list(pulse_moments(s, s['K0'], np.zeros(6), [1024,4096], 16, 1.,
                                rng_for(202610085), burn=1024))
        new = list(collect(s, s['K0'], np.zeros(6), [1024,4096], 16, 1.,
                           rng_for(202610085), burn=1024))
        for a,b in zip(old,new):
            assert a[0] == b[0] and a[-1] == b[-1]
            for index in (1,2,4):
                assert np.allclose(a[index], b[index], rtol=2e-9, atol=2e-9)
    checks['new_family_adjacent_return_equivalence'] = True
    benchmarks = []
    task = next(t for t in cfg['tasks'] if t['n']==100 and t['r']==4 and
                t['tail_mode']=='exact' and t['system_seed']==0)
    s = system(task)
    for count in (32768,131072,524288):
        start = time.monotonic()
        _, z, nxt, costs = data(s, s['K0'], np.zeros(100), count, cfg['burn'], rng_for(202610086,count))
        h, diag = solve(z,nxt,costs)
        del z,nxt,costs
        assert diag['converged'], 'Stochastic full-LSTD benchmark did not converge'
        benchmarks.append(dict(n=100,N=count,total_seconds=time.monotonic()-start,**diag))
    atomic_json(Path(output)/'verification.json', dict(status='PASS', checks=checks,
        systems_checked=len(diagnostics), shared_matrices_bitwise_identical=True,
        diagnostics=diagnostics, benchmarks=benchmarks, **provenance(manifest)))
    print(json.dumps(dict(status='PASS', systems=len(diagnostics),checks=checks,benchmarks=benchmarks)),flush=True)


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['run','reference','verify'])
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--profile')
    parser.add_argument('--task-id', type=int, default=0)
    args = parser.parse_args()
    if args.mode == 'verify':
        verify(args.manifest,args.output)
    elif args.mode == 'reference':
        reference(args.manifest,args.task_id,args.output)
    else:
        run(args.manifest,args.profile,args.task_id,args.output)
