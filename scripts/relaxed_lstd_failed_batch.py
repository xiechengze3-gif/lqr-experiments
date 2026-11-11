"""Reconstruct the failed batch from its saved policy and exogenous seed."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old-manifest', type=Path, required=True)
    parser.add_argument('--old-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rtol', type=float, required=True)
    args = parser.parse_args()
    release = args.old_manifest.parent.parent
    sys.path[:0] = [str(release / 'scripts'), str(release)]
    import numpy as np
    from threadpoolctl import threadpool_limits
    from fixed_value_run import identity, load_system, transition_data
    from full_lstd_precision import solve
    from dense_scaling import atomic_json, rng_for, evaluate
    from adaptive_rank import pi_update

    cfg = json.loads(args.old_manifest.read_text())
    ident = identity(args.old_manifest)
    task = cfg['tasks'][0]
    history = json.loads((args.old_output / 'LSTD_PI' / 'raw' / 'task-000.json').read_text())
    assert history['identity'] == ident
    failure = next(r for r in history['records'] if r['method'] == 'dense' and r.get('failure') == 'full_solver_failure')
    previous = next(r for r in history['records'] if r['method'] == 'dense' and r['stage'] == failure['stage'] - 1)
    with np.load(args.old_output / 'LSTD_PI' / 'checkpoints' / 'task-000.npz', allow_pickle=False) as data:
        assert json.loads(str(data['identity'])) == ident
        k, saved_final_x = data['dense_k'].copy(), data['dense_x'].copy()
    assert hashlib.sha256(k.tobytes()).hexdigest() == previous['policy_sha256']
    s, _ = load_system(task, args.old_output, ident)
    count = failure['N']
    seed = (202610134, task['n'], task['system_seed'], task['policy_seed'], task['trial_seed'], failure['stage'])
    with threadpool_limits(limits=cfg['threads']):
        x, z, y = transition_data(s, k, np.zeros(task['n']), count, cfg['burn'], rng_for(*seed))
        other_x, other_z, other_y = transition_data(s, k, saved_final_x.copy(), count, cfg['burn'], rng_for(*seed))
        # The original incoming x was not saved at every stage. Verify that the
        # long stable burn-in erases both tested starts to numerical equality and
        # recovers the historical final collector state to floating-point
        # precision. BLAS allocation/alignment may change its last few bits.
        final_difference = float(np.max(np.abs(x - saved_final_x)))
        assert np.allclose(x, saved_final_x, rtol=1e-12, atol=1e-12), 'Historical final collector state mismatch'
        assert all(np.allclose(a, b, rtol=1e-12, atol=1e-12)
                   for a, b in ((x, other_x), (z, other_z), (y, other_y)))
        starts_difference = max(float(np.max(np.abs(a - b)))
                                for a, b in ((x, other_x), (z, other_z), (y, other_y)))
        n = task['n']
        nxt = np.concatenate((y, -y @ k.T), axis=1)
        costs = np.einsum('ij,ij->i', z[:, :n] @ s['Q'], z[:, :n])
        costs += np.einsum('ij,ij->i', z[:, n:] @ s['R'], z[:, n:])
        result = dict(status='RUNNING', original_identity=ident, task=task, stage=failure['stage'],
                      original_rtol=cfg['solver_rtol'], relaxed_rtol=args.rtol,
                      audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      reconstruction=dict(policy_hash_match=True, saved_final_state_match_rtol_atol=1e-12,
                          saved_final_state_max_absolute_difference=final_difference,
                          saved_final_state_bitwise_equal=bool(np.array_equal(x, saved_final_x)),
                          two_initial_states_match_rtol_atol=1e-12,
                          two_initial_states_max_absolute_difference=starts_difference,
                          two_initial_states_bitwise_equal_after_burn=bool(np.array_equal(z, other_z) and np.array_equal(y, other_y)),
                          original_incoming_state_unavailable=True,
                          batch_sha256=hashlib.sha256(z.tobytes()+nxt.tobytes()+costs.tobytes()).hexdigest()),
                      original_relative_residual=failure['solver']['full_solver']['relative_residual'],
                      original_iterations=failure['solver']['full_solver']['iterations'],
                      samples_added_to_learning=0)
        atomic_json(args.output, result)
        h, diag = solve(z, nxt, costs, rtol=args.rtol, attempts=cfg['solver_attempts'])
        result['relaxed_solver'] = diag
        if diag['converged']:
            candidate, _, _, _ = pi_update(h[n:, n:] - s['R'], h[n:, :n], s['R'], 'dense')
            result['next_policy'], _ = evaluate(s, candidate)
        result['status'] = 'COMPLETE'
        atomic_json(args.output, result)
        print(json.dumps(dict(status=result['status'], converged=diag['converged'],
                              residual=diag['relative_residual'], iterations=diag['iterations'],
                              next_policy=result.get('next_policy'))), flush=True)


if __name__ == '__main__':
    main()
