"""Bounded resource benchmark; synthetic data, never production results."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def worker():
    import numpy as np
    from full_lstd import solve

    rows = []
    for n, count in ((50, 32768), (100, 131072)):
        rng = np.random.default_rng(20261009 + n)
        d = 2 * n
        z = rng.normal(size=(count, d))
        nxt = 0.2 * rng.normal(size=(count, d))
        truth = rng.normal(size=(d, d))
        truth = (truth + truth.T) / 2
        costs = (np.einsum('ij,ij->i', z @ truth, z)
                 - np.einsum('ij,ij->i', nxt @ truth, nxt) + 3.7)
        started = time.monotonic()
        estimate, diagnostics = solve(z, nxt, costs)
        seconds = time.monotonic() - started
        accurate = (estimate is not None and diagnostics['converged']
                    and np.allclose(estimate, truth, rtol=1e-6, atol=1e-6))
        rows.append(dict(n=n, count=count, seconds=seconds,
                         converged=diagnostics['converged'], accurate=bool(accurate),
                         iterations=diagnostics['iterations'],
                         relative_residual=diagnostics['relative_residual']))
        if not accurate:
            raise RuntimeError('Benchmark failed independent dense recovery check')
    print(json.dumps(rows), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Run only on Grace Slurm compute nodes')
    if args.worker:
        worker()
        return
    rows = []
    for threads in (8, 1, 4, 2):
        env = dict(os.environ)
        for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
            env[key] = str(threads)
        result = subprocess.run([sys.executable, '-B', __file__, '--worker'],
                                env=env, text=True, capture_output=True,
                                check=True, timeout=110)
        for row in json.loads(result.stdout):
            row.update(threads=threads,
                       cpu_core_seconds=threads * row['seconds'])
            rows.append(row)
            print(json.dumps(row), flush=True)
    for row in rows:
        baseline = next(r for r in rows if r['n'] == row['n'] and r['threads'] == 8)
        row['cpu_cost_ratio_to_8_threads'] = row['cpu_core_seconds'] / baseline['cpu_core_seconds']
    payload = dict(kind='synthetic_resource_benchmark_not_experiment',
                   job_id=os.environ['SLURM_JOB_ID'], rows=rows,
                   caveat='CPU cost excludes site memory-equivalent core floor; production timings may differ')
    Path(args.output).write_text(json.dumps(payload, indent=2) + '\n')


if __name__ == '__main__':
    main()
