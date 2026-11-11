"""NPG-only critic precision audit. All numerical operations require Slurm.

The actor replay is identical to the frozen isotropic release. Saved policies
are probed using independent, continuous fixed-policy trajectories. Exact
critics are counterfactual diagnostic updates, never learner inputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from scipy.linalg import solve_discrete_lyapunov

from dense_scaling import (system, targets, trunc, op, eta, evaluate,
                           pulse_moments, pulse_chunk, atomic_json,
                           require_compute, rng_for)


def context(s, k, horizon):
    quality, p = evaluate(s, k)
    if not quality['stable']:
        raise RuntimeError('Diagnostic policy must be stable')
    f = s['A'] - s['B'] @ k
    sigma = solve_discrete_lyapunov(f, s['W'])
    t = targets(s, k, horizon, p)
    e = s['R'] @ k + t['Z']
    eig, u = np.linalg.eigh((sigma + sigma.T) / 2)
    root = (u * np.sqrt(np.maximum(eig, 0))) @ u.T
    e_norm = float(np.linalg.norm(e @ root, 'fro'))
    hz = {}
    for h in (8, 16, 32, 64):
        diff = targets(s, k, h, p)['ZH'] - t['Z']
        hz[str(h)] = dict(fro2=float(np.sum(diff**2)), op=op(diff),
                         relative_E_weighted=float(np.linalg.norm(diff @ root, 'fro')) / max(e_norm, 1e-15))
    return dict(k=k, true=t, E=e, root=root, E_weighted=e_norm,
                quality=quality, horizon_bias=hz,
                Z_sigma_r=float(np.linalg.svd(t['Z'], compute_uv=False)[s['audit_rank'] - 1]))


def update_diagnostic(s, ctx, z, method):
    k, t, root, e = ctx['k'], ctx['true'], ctx['root'], ctx['E']
    direction = s['R'] @ k + z
    error = z - t['Z']
    finite_error = z - t['ZH']
    norm_d = float(np.linalg.norm(direction @ root, 'fro'))
    norm_e = ctx['E_weighted']
    inner = float(np.sum((direction @ root) * (e @ root)))
    quality, _ = evaluate(s, k - eta(s) * direction)
    projected_true = t['Z'] if method == 'raw' else trunc(t['Z'], s['audit_rank'])
    quality_inf, _ = evaluate(s, k - eta(s) * (s['R'] @ k + projected_true))
    projected_h = t['ZH'] if method == 'raw' else trunc(t['ZH'], s['audit_rank'])
    quality_h, _ = evaluate(s, k - eta(s) * (s['R'] @ k + projected_h))
    initial_gap = ctx['quality']['gap']
    return dict(method=method, **quality, before_gap=initial_gap,
                cost_change=quality['gap'] - initial_gap if quality['stable'] else None,
                descent=bool(quality['stable'] and quality['gap'] < initial_gap),
                exact_inf_gap=quality_inf['gap'], exact_H_gap=quality_h['gap'],
                total_error_fro2=float(np.sum(error**2)), total_error_op=op(error),
                finite_target_error_fro2=float(np.sum(finite_error**2)),
                sampling_error_fro2=float(np.sum((z - projected_h)**2)),
                population_truncation_bias_fro2=float(np.sum((projected_h - t['ZH'])**2)),
                relative_E_error=float(np.linalg.norm(error @ root, 'fro')) / max(norm_e, 1e-15),
                relative_Z_error=float(np.linalg.norm(error, 'fro')) / max(float(np.linalg.norm(t['Z'], 'fro')), 1e-15),
                error_op_over_sigma_r=op(error) / max(ctx['Z_sigma_r'], 1e-15),
                E_weighted=norm_e, direction_weighted=norm_d,
                direction_cosine=inner / max(norm_e * norm_d, 1e-15),
                directional_derivative=-2 * inner,
                horizon_bias_fro2=ctx['horizon_bias']['16']['fro2'],
                horizon_bias_relative_E=ctx['horizon_bias']['16']['relative_E_weighted'])


def provenance(manifest):
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
                engine_source_sha256=hashlib.sha256(Path(system.__code__.co_filename).read_bytes()).hexdigest(),
                slurm_job_id=os.environ['SLURM_JOB_ID'])


def actor(manifest, task_id, out):
    data = json.loads(Path(manifest).read_text())
    task = data['actor_tasks'][task_id]
    s = system(task)
    s['audit_rank'] = task['r']
    records, references, saved, policies = [], [], {}, []
    for method in ('raw', 'truncated'):
        k, x, total = s['K0'].copy(), np.zeros(task['n']), 0
        if method == 'raw':
            saved['initial'] = k.copy()
            policies.append(dict(name='initial', stage=0, method='shared', **evaluate(s, k)[0]))
        for stage, count in enumerate(task['batch_schedule']):
            ctx = context(s, k, 16)
            _, x, raw_z, _, gram, used = next(pulse_moments(
                s, k, x, [count], 16, 1.,
                rng_for(99111, task['n'], task['system_seed'], task['trial_seed'], stage), burn=1024))
            total += used
            z = raw_z if method == 'raw' else trunc(raw_z, task['r'])
            row = dict(stage=stage + 1, N=count, transitions=total,
                       gram_condition=float(np.linalg.cond(gram)),
                       **update_diagnostic(s, ctx, z, method))
            records.append(row)
            references.append(dict(stage=stage + 1, method=method,
                                   horizon_bias=ctx['horizon_bias'], before_gap=ctx['quality']['gap']))
            # Identical learner update to frozen actor; evaluation never selects it.
            k = k - eta(s) * (s['R'] @ k + z)
            if stage + 1 in (8, 16, 24):
                name = f'{method}{stage + 1}'
                saved[name] = k.copy()
                policies.append(dict(name=name, stage=stage + 1, method=method, **evaluate(s, k)[0]))
            atomic_json(Path(out) / 'raw' / f'actor-progress-{task_id:02d}.json',
                        dict(task=task, records=records))
            if not row['stable']:
                raise RuntimeError('Replay produced an unstable policy; retain progress and investigate')
        print(json.dumps(dict(actor_task=task_id, method=method, final=records[-1])), flush=True)
    k = s['K0'].copy()
    for _ in range(128):
        z = targets(s, k, 16)['Z']
        k = k - eta(s) * (s['R'] @ k + z)
    saved['exact128'] = k.copy()
    policies.append(dict(name='exact128', stage=128, method='exact_reference', **evaluate(s, k)[0]))
    path = Path(out) / 'policies' / f'actor-{task_id:02d}.npz'
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **saved)
    atomic_json(Path(out) / 'raw' / f'actor-{task_id:02d}.json',
                dict(task=task, records=records, references=references, policies=policies,
                     policy_archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     **provenance(manifest)))


def fixed(manifest, task_id, out):
    data = json.loads(Path(manifest).read_text())
    spec = data['fixed_tasks'][task_id]
    task = data['actor_tasks'][spec['actor_task']]
    s = system(task)
    s['audit_rank'] = task['r']
    policy_path = Path(out) / 'policies' / f"actor-{spec['actor_task']:02d}.npz"
    actor_result = json.loads((Path(out) / 'raw' / f"actor-{spec['actor_task']:02d}.json").read_text())
    if hashlib.sha256(policy_path.read_bytes()).hexdigest() != actor_result['policy_archive_sha256']:
        raise RuntimeError('Saved policy provenance mismatch')
    with np.load(policy_path) as archive:
        k = archive[spec['policy']].copy()
    ctx = context(s, k, 16)
    records = []
    seed = rng_for(882117, task['n'], task['system_seed'],
                   spec['actor_task'], spec['policy_seed'], spec['trial_seed'])
    # A fresh independent trajectory for this fixed-policy test, continuous
    # throughout all common prefixes. Initial burn-in is counted.
    for count, _, raw_z, _, gram, used in pulse_moments(s, k, np.zeros(task['n']), spec['budgets'], 16, 1., seed, burn=1024):
        for method in ('raw', 'truncated'):
            z = raw_z if method == 'raw' else trunc(raw_z, task['r'])
            records.append(dict(N=count, transitions=used,
                                gram_condition=float(np.linalg.cond(gram)),
                                **update_diagnostic(s, ctx, z, method)))
    atomic_json(Path(out) / 'raw' / f'fixed-{task_id:03d}.json',
                dict(spec=spec, task=task, records=records, policy_quality=ctx['quality'],
                     horizon_bias=ctx['horizon_bias'], policy_archive_sha256=actor_result['policy_archive_sha256'],
                     **provenance(manifest)))
    print(json.dumps(dict(fixed_task=task_id, policy=spec['policy'], finals=records[-2:])), flush=True)


def verify():
    task = dict(n=6, m=6, r=2, system_seed=0, family='coupled_unstable',
                stabilizer='isotropic', tail=0., tail_shape='energy')
    s = system(task)
    k, n, horizon = s['K0'], 6, 16
    f = np.ascontiguousarray(s['A'] - s['B'] @ k)
    cost = np.ascontiguousarray(s['Q'] + k.T @ s['R'] @ k)
    ph, power = np.zeros((n, n)), np.eye(n)
    for _ in range(horizon):
        ph += power.T @ cost @ power
        power = power @ f
    expected = -s['B'].T @ ph @ f
    assert np.allclose(expected, targets(s, k, horizon)['ZH'], atol=1e-11)
    # Symmetric cubature exactly integrates the pulse label polynomial (degree
    # <=3). Independent fixed-X calls are an identity test, not learner data.
    x_matrix = rng_for(7721).normal(size=(n, n + 3))
    y_matrix = np.zeros((n, n + 3))
    for col, start in enumerate(x_matrix.T):
        y = np.zeros(n)
        for index in range(n):
            for sign in (-1, 1):
                pulse = np.zeros(n)
                pulse[index] = sign * np.sqrt(n)
                _, _, ret = pulse_chunk(f, s['B'], cost, start.copy(), pulse[None, :], np.zeros((1, horizon, n)))
                # Arbitrary predictable baseline cancels by pulse symmetry.
                y += -pulse * (ret[0] - 17.) / 2 / (2 * n)
        y_matrix[:, col] = y
    raw = np.linalg.solve(x_matrix @ x_matrix.T, (y_matrix @ x_matrix.T).T).T
    assert np.allclose(raw, expected, atol=2e-10)
    assert np.allclose(trunc(raw, 2), expected, atol=2e-10)
    # Known RK is kept exactly; identity critic update matches finite-H target.
    assert np.allclose(k - eta(s) * (s['R'] @ k + raw),
                       k - eta(s) * (s['R'] @ k + targets(s, k, horizon)['ZH']), atol=2e-10)
    print(json.dumps(dict(verification='PASS', tests=['finite-H sum', 'pulse timing and label sign',
          'predictable baseline cancellation', 'OLS transpose', 'exact-rank truncation identity', 'known RK retention'])), flush=True)


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['verify', 'actor', 'fixed'])
    parser.add_argument('--manifest')
    parser.add_argument('--task-id', type=int)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.mode == 'verify':
        verify()
    else:
        globals()[args.mode](args.manifest, args.task_id, args.output)
