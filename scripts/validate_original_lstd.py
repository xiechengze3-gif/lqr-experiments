"""Bounded local audit of original-coordinate LSTD and block collection."""
import argparse
import importlib.util
import json
import os
import time
from pathlib import Path

from local_resume import setup, save, digest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(args):
    import numpy as np
    from threadpoolctl import threadpool_limits
    runner, _, output = setup(args.root, 'rank-multiseed-2a95058c9c562fd9')
    source = Path(__file__).resolve().parent
    raw = load('original_coordinate_lstd', source / 'full_lstd.py')
    collector = load('blocked_original_collector', source / 'pi_ce_rank.py')
    with threadpool_limits(limits=args.threads):
        identity = raw.verify()
        cfg = json.loads((args.root / 'releases/rank-multiseed-2a95058c9c562fd9/configs/rank_multiseed.json').read_text())
        task = next(task for task in cfg['tasks'] if task['n'] == args.n and task['r'] == 4
                    and task['system_seed'] == 0 and task['tail_mode'] == 'exact')
        s = runner.system(task)
        # Identical RNG calls and states; GEMM grouping may round the derived
        # next-policy actions/costs differently, so test a fixed tight tolerance.
        old_rng = runner.rng_for(202610082, args.n, 0, 0)
        new_rng = runner.rng_for(202610082, args.n, 0, 0)
        prior = runner.data(s, s['K0'], np.zeros(args.n), 8192, cfg['burn'], old_rng)
        revised = collector.data(s, s['K0'], np.zeros(args.n), 8192, cfg['burn'], new_rng)
        assert old_rng.bit_generator.state == new_rng.bit_generator.state
        assert np.array_equal(prior[0], revised[0]) and np.array_equal(prior[1], revised[1])
        assert all(np.allclose(a, b, rtol=1e-12, atol=1e-12) for a, b in zip(prior, revised))
        collector_check = dict(rng_state_exact=True, final_state_exact=True, original_samples_exact=True,
                               derived_arrays_rtol=1e-12, derived_arrays_atol=1e-12,
                               next_max_abs=float(np.max(np.abs(prior[2]-revised[2]))),
                               cost_max_abs=float(np.max(np.abs(prior[3]-revised[3]))))
        del prior, revised
        records = []
        # Complete both paired six-update trajectories on a real frozen system.
        for method in ('raw', 'truncated'):
            k, x = s['K0'].copy(), np.zeros(args.n)
            for stage in range(args.stages):
                wall, cpu = time.monotonic(), time.process_time()
                x, z, nxt, costs = collector.data(s, k, x, args.count, cfg['burn'],
                    runner.rng_for(202610082, args.n, 0, stage))
                h, diagnostics = raw.solve(z, nxt, costs, rtol=cfg['solver_rtol'], restart=40, maxiter=10)
                del z, nxt, costs
                row = dict(method=method, stage=stage+1, n=args.n, count=args.count,
                           threads=args.threads, seconds=time.monotonic()-wall,
                           actual_process_cpu_seconds=time.process_time()-cpu, solver=diagnostics)
                if not diagnostics['converged']:
                    row['failure'] = 'LSTD_solver_failure'
                    records.append(row)
                    break
                g, c = h[args.n:, args.n:] - s['R'], h[args.n:, :args.n]
                k, _, _ = runner.pi_gain(s, g, c, None if method == 'raw' else task['r'])
                quality, _ = runner.evaluate(s, k)
                row.update(quality)
                row['policy_sha256'] = __import__('hashlib').sha256(k.tobytes()).hexdigest()
                row['policy'] = k.tolist()
                records.append(row)
                print(json.dumps({key: value for key, value in row.items() if key != 'policy'}), flush=True)
                if not quality['stable']:
                    break
        result = dict(status='PASS' if all(row['solver']['converged'] for row in records) else 'FAIL',
                      independent_identity=identity, collector=collector_check, records=records,
                      solver_sha256=digest(source / 'full_lstd.py'),
                      collector_sha256=digest(source / 'pi_ce_rank.py'),
                      original_coordinates=True, whitening=False, threads=args.threads,
                      n=args.n, count=args.count, stages=args.stages)
        save(args.output, result)
        print(json.dumps(dict(status=result['status'], output=str(args.output))), flush=True)
        if result['status'] != 'PASS':
            raise SystemExit(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--n', type=int, choices=[25, 50, 75, 100], default=25)
    parser.add_argument('--count', type=int, default=32768)
    parser.add_argument('--threads', type=int, choices=[1, 2], default=1)
    parser.add_argument('--stages', type=int, default=6)
    main(parser.parse_args())
