"""Full LSTD-PI and full-model OLS CE; numerical work only on Grace."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import numpy as np
from dense_scaling import (system, ce, ce_chunk, pi_gain, evaluate, targets,
                           atomic_json, require_compute, rng_for)
from full_lstd import solve, verify


def provenance(manifest):
    return dict(manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        lstd_sha256=hashlib.sha256(Path(solve.__code__.co_filename).read_bytes()).hexdigest(),
        engine_sha256=hashlib.sha256(Path(system.__code__.co_filename).read_bytes()).hexdigest(),
        slurm_job_id=os.environ['SLURM_JOB_ID'])


def data(s, k, x, count, burn, rng):
    n = len(x)
    f = np.ascontiguousarray(s['A']-s['B'] @ k)
    if burn:
        x, _, _ = ce_chunk(f, s['B'], k, x, rng.normal(size=(burn, n)),
                           rng.normal(size=(burn, n)))
    # Keep only original z and target-policy next_z. Preserve innovation order.
    z, nxt = np.empty((count, 2*n)), np.empty((count, 2*n))
    costs = np.empty(count)
    for lo in range(0, count, 2048):
        size = min(2048, count-lo)
        x, zz, yy = ce_chunk(f, s['B'], k, x, rng.normal(size=(size, n)),
                             rng.normal(size=(size, n)))
        z[lo:lo+size] = zz
        nxt[lo:lo+size, :n] = yy
        nxt[lo:lo+size, n:] = -yy @ k.T
        costs[lo:lo+size] = np.einsum('ij,ij->i', zz[:, :n] @ s['Q'], zz[:, :n])
        costs[lo:lo+size] += np.einsum('ij,ij->i', zz[:, n:] @ s['R'], zz[:, n:])
    return x, z, nxt, costs


def run(manifest, task_id, output):
    cfg = json.loads(Path(manifest).read_text()); task = cfg['tasks'][task_id]
    s = system(task); records = []; start = time.monotonic()
    if cfg['algorithm'] == 'CE':
        ce_task = dict(task, budgets=cfg['budgets'], sigma=1.)
        records, _ = ce(ce_task, s)
    else:
        for method in ('raw', 'truncated'):
            k, x, total = s['K0'].copy(), np.zeros(task['n']), 0
            quality, _ = evaluate(s, k)
            records.append(dict(method=method, stage=0, N=0, transitions=0, **quality))
            for stage, count in enumerate(cfg['batch_schedule']):
                x, z, nxt, costs = data(s, k, x, count, cfg['burn'],
                    rng_for(911833, task['n'], task['system_seed'], stage))
                total += count+cfg['burn']
                h, diagnostics = solve(z, nxt, costs, rtol=cfg['solver_rtol'],
                    maxiter=cfg['solver_maxiter'], restart=cfg['solver_restart'])
                del z, nxt, costs
                row = dict(method=method, stage=stage+1, N=count, transitions=total,
                           solver=diagnostics)
                if not diagnostics['converged']:
                    row.update(stable=False, gap=None, failure='LSTD_solver_failure')
                    records.append(row); break
                n = task['n']
                # Full critic is solved first. Only its extracted action blocks
                # are passed to the joint projection/PSD clipping operation.
                g, c = h[n:, n:]-s['R'], h[n:, :n]
                truth = targets(s, k, 16)
                row['joint_error_fro2'] = float(np.sum((g-truth['G'])**2)+np.sum((c-truth['C'])**2))
                candidate, _, _ = pi_gain(s, g, c, None if method == 'raw' else task['r'])
                quality, _ = evaluate(s, candidate)
                row.update(quality); records.append(row); k = candidate
                payload = dict(task=task, records=records, **provenance(manifest))
                atomic_json(Path(output)/'raw'/f'progress-{task_id:03d}.json', payload)
                print(json.dumps(dict(task_id=task_id, **row)), flush=True)
                if not quality['stable']: break
    atomic_json(Path(output)/'raw'/f'task-{task_id:03d}.json',
        dict(task=task, records=records, algorithm=cfg['algorithm'],
             seconds=time.monotonic()-start, **provenance(manifest)))


def check(manifest, output):
    result = verify()
    cfg = json.loads(Path(manifest).read_text())
    rows = []
    for n in (6, 50, 100):
        task = dict(n=n, m=n, r=1 if n == 6 else 4, system_seed=0,
            tail=0., tail_shape='energy', family='coupled_unstable', stabilizer='isotropic')
        s = system(task); k = s['K0']; count = 8192 if n == 6 else 65536
        _, z, nxt, costs = data(s, k, np.zeros(n), count, 1024, rng_for(783,n))
        h, diag = solve(z, nxt, costs, rtol=1e-7, maxiter=10, restart=40)
        quality, _ = evaluate(s, k)
        row = dict(n=n, **diag, initial_gap=quality['gap'])
        if h is not None:
            truth = targets(s, k, 16)
            row['joint_relative_error'] = float(np.linalg.norm(np.concatenate((h[n:,n:]-s['R']-truth['G'], h[n:,:n]-truth['C']), axis=1))/max(np.linalg.norm(np.concatenate((truth['G'],truth['C']),axis=1)),1e-30))
        rows.append(row); print(json.dumps(row), flush=True)
    atomic_json(Path(output)/'verification.json', dict(identity=result, benchmarks=rows, **provenance(manifest)))
    if not all(r['converged'] for r in rows):
        raise RuntimeError('Full LSTD numerical solve failed: no production PI submission')


if __name__ == '__main__':
    require_compute()
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['run', 'verify'])
    p.add_argument('--manifest', required=True); p.add_argument('--output', required=True)
    p.add_argument('--task-id', type=int, default=0); a = p.parse_args()
    if a.mode == 'verify': check(a.manifest, a.output)
    else: run(a.manifest, a.task_id, a.output)
