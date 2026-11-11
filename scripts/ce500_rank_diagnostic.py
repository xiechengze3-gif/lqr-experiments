"""Audit saved CE fits and quantify the rank-dependent population coefficient.

The derivative experiment uses exact stationary covariances and 16 common
Gaussian probes. It is a mechanism diagnostic, separate from trajectory seeds.
"""
import math
import os
from pathlib import Path
import statistics
import time

import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_discrete_lyapunov, solve_triangular, svd


def diagnose(cfg, ident, core):
    e, engine = core.e, core.engine
    base = Path(cfg['base_output'])
    basecfg = e.read(base / 'resolved_config.json')
    out = Path(cfg['output']) / 'mechanism'
    out.mkdir(exist_ok=True)
    rng = np.random.default_rng(np.random.SeedSequence([2026102292, 500, 5001]))
    ub = np.linalg.qr(rng.normal(size=(500, 500)))[0]
    vb = np.linalg.qr(rng.normal(size=(500, 500)))[0]
    common = engine.load_system(basecfg, 2)
    _, avec = np.linalg.eigh(common['A'])
    unstable = avec[:, -1]
    records = []
    began = time.monotonic()

    def energy(dk, lh, ls): return float(np.sum((lh.T @ dk @ ls) ** 2))

    for rank in [2, 4, 8, 32, 70, 150, 300, 500]:
        activecfg = cfg if rank in cfg['ranks'] else basecfg
        s = engine.load_system(activecfg, rank)
        for key in ['A', 'Q', 'R', 'W', 'K0', 'F0', 'P0']:
            np.testing.assert_array_equal(s[key], common[key])
        b = s['B']
        np.testing.assert_allclose(b, ub[:, :rank] @ vb[:, :rank].T, atol=2e-12, rtol=0)
        pu = ub[:, :rank] @ ub[:, :rank].T
        pv = vb[:, :rank] @ vb[:, :rank].T
        sx = solve_discrete_lyapunov(s['F0'], s['W'] + cfg['sigma'] ** 2 * b @ b.T)
        k0 = s['K0']
        sz = np.block([[sx, -sx @ k0.T], [-k0 @ sx, k0 @ sx @ k0.T + cfg['sigma'] ** 2 * np.eye(500)]])
        lz = np.linalg.cholesky(sz)
        fs = s['A'] - b @ s['Kstar']
        ss = solve_discrete_lyapunov(fs, s['W'])
        hs = s['R'] + b.T @ s['Pstar'] @ b
        lh, ls = np.linalg.cholesky(hs), np.linalg.cholesky(ss)
        hf = cho_factor(hs)
        eigx, eigz = np.linalg.eigvalsh(sx), np.linalg.eigvalsh(sz)
        row = dict(rank=rank, unstable_actuation_squared=float(np.sum((b.T @ unstable) ** 2)),
                   Pstar_op=float(np.linalg.eigvalsh(s['Pstar'])[-1]), Kstar_op=float(np.linalg.norm(s['Kstar'], 2)),
                   Kstar_fro2=float(np.sum(s['Kstar'] ** 2)), Hstar_op=float(np.linalg.eigvalsh(hs)[-1]),
                   optimal_closed_loop_radius=float(max(abs(np.linalg.eigvals(fs)))),
                   exploration_state_trace=float(np.trace(sx)), exploration_state_min=float(eigx[0]), exploration_state_max=float(eigx[-1]),
                   exploration_variance_unstable=float(unstable @ sx @ unstable),
                   joint_design_min=float(eigz[0]), joint_design_max=float(eigz[-1]),
                   joint_inverse_state_trace=float(np.sum(solve_triangular(lz, np.eye(1000), lower=True)[:, :500] ** 2)),
                   supplied_p0=47., actual_P0_op=float(np.linalg.eigvalsh(s['P0'])[-1]), saved_fit_audits=[])

        if rank not in cfg['ranks']:
            for seed in [700, 800]:
                stem = f'ce-r{rank:03d}-s{seed:04d}'
                rawpath = base / 'raw' / (stem + '.json')
                if not rawpath.exists(): continue
                raw = e.read(rawpath)
                last = max(raw['budgets'])
                with np.load(base / 'checkpoints' / (stem + '.npz')) as d:
                    gram, cross = d['gram'], d['cross']
                # Independent general solver rather than the learner's Cholesky.
                ref = np.linalg.solve((gram + gram.T) / 2, cross.T).T
                with np.load(base / 'estimates' / (stem + '.npz')) as d:
                    aa, bb = d['Ahat'], d['Bhat']
                olserr = float(np.max(abs(ref - np.concatenate([aa, bb], axis=1))))
                assert olserr < 1e-9
                u, singular, vh = svd(bb, full_matrices=False, lapack_driver='gesvd')
                bt = (u[:, :rank] * singular[:rank]) @ vh[:rank]
                assert np.max(abs(bt - e.corrected(bb, 'truncated', rank))) < 1e-11
                pair = [r for r in raw['records'] if r['ols_samples'] == last]
                with np.load(base / pair[0]['policy_file']) as p:
                    ks = [p['shared']] * 2 if rank == 500 else [p['dense'], p['truncated']]
                policies = []
                for rr, kk, bfit in zip(pair, ks, [bb, bt]):
                    candidate, _ = e.dare(aa, bfit, s['Q'], s['R'])
                    error = float(np.linalg.norm(candidate - kk) / max(1., np.linalg.norm(kk)))
                    assert error < 1e-8
                    gap, _, covariance = engine.performance_gap(s, kk)
                    assert rr['stable'] and abs(gap - rr['gap']) < 2e-7 * max(1., gap)
                    delta = kk - s['Kstar']
                    active, null = pv @ delta, (np.eye(500) - pv) @ delta
                    lsaved = np.linalg.cholesky(covariance)
                    ga, gn = energy(active, lh, lsaved), float(np.sum((null @ lsaved) ** 2))
                    assert abs(ga + gn - gap) < 1e-7 * max(1., gap)
                    policies.append(dict(method=rr['method'], gap=gap, N_gap=last * gap,
                                         active_action_gap=ga, null_action_gap=gn,
                                         policy_reconstruction_relative_error=error))
                hybrids = {}
                if seed == 700:
                    for name, amat, bmat in [('A_error_only', aa, b), ('B_dense_error_only', s['A'], bb), ('B_truncated_error_only', s['A'], bt)]:
                        hk, _ = e.dare(amat, bmat, s['Q'], s['R'])
                        gap = engine.performance_gap(s, hk)[0]
                        hybrids[name] = gap if math.isfinite(gap) else None
                row['saved_fit_audits'].append(dict(seed=seed, ols_samples=last, joint_OLS_max_error=olserr,
                    svd_tail_fro2=float(np.sum(singular[rank:] ** 2)), policies=policies, hybrid_gaps=hybrids))

        def derivative(da, db):
            innovation = da - db @ s['Kstar']
            y = fs.T @ s['Pstar'] @ innovation
            dp = solve_discrete_lyapunov(fs.T, y + y.T)
            return cho_solve(hf, db.T @ s['Pstar'] @ fs + b.T @ dp @ fs + b.T @ s['Pstar'] @ innovation)

        probes = []
        finite_checks = []
        zero = np.zeros((500, 500))
        for probe in range(16):
            # E[vec(error) vec(error)^T] = Sigma_z^{-1} tensor W for sqrt(N)*OLS error.
            prng = np.random.default_rng(np.random.SeedSequence([2026102308, probe]))
            g = prng.normal(size=(500, 1000))
            noise = solve_triangular(lz.T, g.T, lower=False).T
            da, db = noise[:, :500], noise[:, 500:]
            tangent = pu @ db + db @ pv - pu @ db @ pv
            ka = derivative(da, zero)
            kd, kt = derivative(da, db), derivative(da, tangent)
            coefficients = dict(dense=energy(kd, lh, ls), truncated=energy(kt, lh, ls),
                A_only=energy(ka, lh, ls), B_dense_only=energy(kd-ka, lh, ls),
                B_truncated_only=energy(kt-ka, lh, ls))
            if probe == 0:
                step = 1e-6
                for method, dpolicy in [('dense', kd), ('truncated', kt)]:
                    bt = b + step * db
                    if method == 'truncated': bt = e.corrected(bt, method, rank)
                    kh, _ = e.dare(s['A'] + step * da, bt, s['Q'], s['R'])
                    relative = float(np.linalg.norm((kh-s['Kstar']) / step - dpolicy) / np.linalg.norm(dpolicy))
                    finite = engine.performance_gap(s, kh)[0] / step ** 2
                    coeff_rel = abs(finite - coefficients[method]) / coefficients[method]
                    assert relative < .005 and coeff_rel < .005, (rank, method, relative, coeff_rel)
                    finite_checks.append(dict(method=method, derivative_relative_error=relative,
                                              cost_coefficient_relative_error=coeff_rel))
            probes.append(coefficients)
        prediction = {}
        for name in probes[0]:
            vals = [p[name] for p in probes]
            prediction[name] = dict(mean=statistics.mean(vals), standard_error=statistics.stdev(vals)/4)
        row.update(population_linearized_coefficients=prediction,
                   predicted_dense_to_truncated_ratio=prediction['dense']['mean']/prediction['truncated']['mean'],
                   predicted_truncated_C_over_r_d=prediction['truncated']['mean']/(rank*1000),
                   derivative_finite_difference_checks=finite_checks, diagnostic_probes=16,
                   elapsed_seconds=time.monotonic()-began)
        records.append(row)
        e.atomic_json(out / f'rank-{rank:03d}.json', row)
        print({'rank': rank, 'overlap': row['unstable_actuation_squared'], 'Pstar_op': row['Pstar_op'],
               'prediction': prediction, 'ratio': row['predicted_dense_to_truncated_ratio'], 'seconds': row['elapsed_seconds']}, flush=True)
    e.atomic_json(out / 'summary.json', dict(status='PASS', identity=ident, records=records,
        description='Common upper-bound constants; rank-dependent exact excitation, optimal Riccati sensitivity, and asymptotic CE coefficient.',
        gaussian_probe_count=16, diagnostic_probe_namespace=2026102308, gaussian_probes_are_not_trajectory_seeds=True,
        linearized_coefficient_definition='N*(J(Khat)-Jstar) converges in distribution to a quadratic Gaussian form; C_r is the probe estimate of its mean, not a finite-sample guarantee.',
        slurm_job_id=os.environ['SLURM_JOB_ID'], seconds=time.monotonic()-began))
    flat = [{k: r[k] for k in ['rank', 'unstable_actuation_squared', 'Pstar_op', 'Kstar_op',
            'exploration_state_trace', 'exploration_variance_unstable', 'joint_design_min',
            'predicted_dense_to_truncated_ratio', 'predicted_truncated_C_over_r_d']} for r in records]
    for f, r in zip(flat, records):
        f.update({name+'_C': value['mean'] for name, value in r['population_linearized_coefficients'].items()})
    core.write_csv(out / 'mechanism_summary.csv', flat)


if __name__ == '__main__':
    raise SystemExit('Use the extension runner inside a real Slurm compute allocation')
