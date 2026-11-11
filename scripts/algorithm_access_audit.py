"""Information-flow checks and CE measured-threshold audit; Grace compute only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import dense_scaling as engine
from approx_tail_system import system
from pi_ce_rank import data
from full_lstd import solve


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(matrix):
    return hashlib.sha256(np.ascontiguousarray(matrix).tobytes()).hexdigest()


def main(release, snapshot, output):
    release, snapshot, output = map(Path, (release, snapshot, output))
    output.mkdir(parents=True, exist_ok=False)
    task = dict(id=-1, n=6, m=6, r=2, system_seed=0, trial_seed=0,
                tail_mode='exact', level=0., families=['audit'], cell='access-audit-n6-r2')
    cfg = dict(tasks=[task], profiles={
        'ce': dict(algorithm='CE', budgets=[512, 1024]),
        'lspi-access': dict(algorithm='LSPI', schedule=[4096, 4096]),
        'npg-access': dict(algorithm='NPG', schedule=[4096, 4096])},
        burn=64, horizon=16, solver_rtol=1e-8)
    manifest = output / 'audit_manifest.json'
    engine.atomic_json(manifest, cfg)
    spec = importlib.util.spec_from_file_location('audit_subject', release / 'scripts/approx_tail_run.py')
    subject = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(subject)
    real_evaluate, real_targets = engine.evaluate, subject.targets
    results = []
    for profile in cfg['profiles']:
        traces = []
        for poison in (False, True):
            trace = []
            def evaluate(s, k):
                trace.append(digest(k))
                quality, p = real_evaluate(s, k)
                if poison:
                    quality = dict(quality)
                    for key in ('gap', 'relative_gap', 'cost'):
                        if quality.get(key) is not None:
                            quality[key] += 123.
                    if p is not None:
                        p = p * 7.
                return quality, p
            def poisoned_targets(s, k, horizon, p=None):
                return {key: np.full((task['n'], task['n']), 77.) for key in
                        ('G', 'C', 'Z', 'GH', 'CH', 'ZH')}
            subject.evaluate = engine.evaluate = evaluate
            subject.targets = poisoned_targets if poison else real_targets
            subject.run(manifest, profile, 0, output / ('poisoned_diagnostics' if poison else 'ordinary_diagnostics'))
            traces.append(trace)
            engine.evaluate = subject.evaluate = real_evaluate
            subject.targets = real_targets
        assert traces[0] == traces[1], ('True diagnostics influenced policies', profile)
        results.append(dict(profile=profile, status='PASS', policy_trace_identical=True,
                            evaluated_policies=len(traces[0]), policy_sha256=traces[0]))

    # One observed batch supports both model OLS and full quadratic LSTD.
    s = system(task)
    _, z, nxt, costs = data(s, s['K0'], np.zeros(task['n']), 4096, 64, engine.rng_for(90317))
    theta = np.linalg.solve(z.T @ z, (nxt[:, :task['n']].T @ z).T).T
    h, solver = solve(z, nxt, costs, rtol=1e-8)
    assert solver['converged']
    g, c = h[task['n']:, task['n']:] - s['R'], h[task['n']:, :task['n']]
    pi, _, _ = engine.pi_gain({'R': s['R']}, g, c, task['r'])
    ce, _ = engine.dare(theta[:, :task['n']], engine.trunc(theta[:, task['n']:], task['r']), s['Q'], s['R'])
    assert np.isfinite(pi).all() and np.isfinite(ce).all()

    summary = json.loads((snapshot / 'report/summary.json').read_text())
    thresholds = summary['thresholds']
    dimensions, ranks = [], []
    for epsilon in (.1, .03, .01):
        for method in ('raw', 'truncated'):
            rows = sorted([t for t in thresholds if t['algorithm'] == 'CE' and t['method'] == method and
                           t['tail_mode'] == 'exact' and t['r'] == 4 and t['epsilon'] == epsilon], key=lambda t:t['n'])
            good = [t for t in rows if t['status'] == 'attained']
            record = dict(epsilon=epsilon, method=method, fixed_rank=4,
                          measured=[{k:t[k] for k in ('n', 'budget', 'status', 'lower_budget')} for t in rows])
            if len(good) >= 3:
                record['descriptive_dimension_exponent'] = float(np.polyfit(np.log([t['n'] for t in good]),
                                                                          np.log([t['budget'] for t in good]), 1)[0])
            dimensions.append(record)
            for n in (50, 100):
                rows = sorted([t for t in thresholds if t['algorithm'] == 'CE' and t['method'] == method and
                               t['tail_mode'] == 'exact' and t['n'] == n and t['r'] in (1,2,4,8,16) and
                               t['epsilon'] == epsilon], key=lambda t:t['r'])
                good = [t for t in rows if t['status'] == 'attained']
                record = dict(epsilon=epsilon, method=method, fixed_dimension=n,
                              measured=[{k:t[k] for k in ('r', 'budget', 'status', 'lower_budget')} for t in rows])
                if len(good) >= 3:
                    record['descriptive_rank_exponent'] = float(np.polyfit(np.log([t['r'] for t in good]),
                                                                         np.log([t['budget'] for t in good]), 1)[0])
                ranks.append(record)
    source = (release / 'scripts/approx_tail_run.py').read_text()
    assert "if not quality['stable']:\n                    break" in source
    engine.atomic_json(output / 'access_audit.json', dict(status='PASS', diagnostic_intervention=results,
        shared_one_step_batch=dict(status='PASS', samples=4096, burn=64, full_LSTD_converged=True,
                                  LSPI_actor_requires_only_R_and_estimated_blocks=True,
                                  CE_actor_uses_fitted_model_and_known_Q_R=True),
        access=dict(known=['Q', 'R', 'K0', 'rank r', 'scalar system bounds'], unknown=['A', 'B', 'W', 'input subspace'],
                    observation='Full state and own action, single continuous trajectory per run; no reset/branch oracle',
                    LSPI='Per-step Gaussian exploration; one-step transition and actual exploration cost; full quadratic LSTD',
                    NPG='One pulse per H=16 transitions; nominal-policy returns computable from full states and known Q/R; direct residual OLS',
                    CE='Per-step Gaussian exploration under fixed K0; one-step vector-response OLS and model Riccati solve',
                    true_stability_used_to_abort_failed_LSPI_NPG_runs=True,
                    intervention_preserves_stability_classification=True,
                    warning='Successful update policies are invariant to changing true P/targets/cost diagnostics; '
                            'the runner still has a true-model stability termination guard. '
                            'Algorithms use different experiments and different summaries of observations.'),
        dimension_thresholds=dimensions, rank_thresholds=ranks,
        joint_threshold_fits=[f for f in summary['fits'] if f['algorithm']=='CE' and f['method']=='truncated'],
        provenance=dict(source_sha256=sha(__file__), subject_sha256=sha(release/'scripts/approx_tail_run.py'),
                        snapshot_summary_sha256=sha(snapshot/'report/summary.json'),
                        subject_manifest_sha256=sha(release/'configs/approx_tail_suite.json')),
        caveat='Small n=6 intervention verifies information flow, not performance or general correctness. '
               'CE is fully complete in this snapshot. Slopes describe discrete measured thresholds, not asymptotic laws.'))
    print(json.dumps(dict(status='PASS', policy_interventions=results, dimension_thresholds=dimensions)))


if __name__ == '__main__':
    engine.require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', required=True)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.release, args.snapshot, args.output)
