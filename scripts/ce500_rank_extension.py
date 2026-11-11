"""Extend the frozen independent/common-certificate family to ranks 70/150/300."""
import argparse
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import ce500_common_constants as core
import numpy as np
from scipy.linalg import solve_discrete_lyapunov


def identity(cfg):
    result = core.identity(cfg)
    result['extension_sources'] = {p: core.e.sha(ROOT / p) for p in
        ['scripts/ce500_rank_extension.py', 'scripts/ce500_rank_diagnostic.py']}
    return result


def prepare(cfg, ident):
    e = core.e
    out = Path(cfg['output'])
    out.mkdir(parents=True, exist_ok=True)
    assert not (out / 'preflight.json').exists(), 'Inspect existing preparation before replay'
    base = Path(cfg['base_output'])
    proof = e.read(base / 'verification.json')
    assert proof['status'] == 'PASS' and proof['identity'] == cfg['base_numerical_identity']
    old = core.engine.load_system(e.read(base / 'resolved_config.json'), 2)
    # This is the original, independent B stream. A is copied, never regenerated
    # from B or K0. Verify every previously used B before constructing new ranks.
    rng = np.random.default_rng(np.random.SeedSequence([2026102292, 500, 5001]))
    u = np.linalg.qr(rng.normal(size=(500, 500)))[0]
    v = np.linalg.qr(rng.normal(size=(500, 500)))[0]
    reproduction = {}
    basecfg = e.read(base / 'resolved_config.json')
    for rank in [2, 4, 8, 32, 500]:
        saved = core.engine.load_system(basecfg, rank)
        br = u[:, :rank] @ v[:, :rank].T
        err = float(np.max(np.abs(br - saved['B'])))
        assert err < 2e-12
        reproduction[str(rank)] = err
        for key in ['A', 'Q', 'R', 'W', 'K0', 'F0', 'P0']:
            np.testing.assert_array_equal(saved[key], old[key])
    hashes = {}
    rows = []
    for rank in cfg['ranks']:
        s = {key: old[key].copy() for key in ['A', 'Q', 'R', 'W', 'K0', 'F0', 'P0']}
        s['B'] = u[:, :rank] @ v[:, :rank].T
        singular = np.linalg.svd(s['B'], compute_uv=False)
        assert np.max(np.abs(singular[:rank] - 1)) < 1e-11 and singular[rank] < 1e-11
        f = s['A'] - s['B'] @ s['K0']
        np.testing.assert_allclose(f, old['F0'], atol=2e-12, rtol=0)
        p = solve_discrete_lyapunov(f.T, s['Q'] + s['K0'].T @ s['R'] @ s['K0'])
        assert np.linalg.eigvalsh(p)[-1] < cfg['supplied_common_bounds']['p_0']
        np.testing.assert_allclose(p, old['P0'], atol=1e-10, rtol=1e-10)
        # Task optimum enters only after the shared K0 has already been copied.
        ks, ps = e.dare(s['A'], s['B'], s['Q'], s['R'])
        s.update(Kstar=ks, Pstar=ps, Jstar=float(np.trace(ps)), initial_gap=float(np.trace(s['P0'] - ps)))
        assert s['initial_gap'] > 0
        path = out / 'systems' / f'r{rank:03d}.npz'
        e.save_npz(path, **s)
        hashes[str(rank)] = e.sha(path)
        rows.append(dict(rank=rank, rho_A=float(max(abs(np.linalg.eigvals(s['A'])))),
                         rho_F0=float(max(abs(np.linalg.eigvals(f)))),
                         F0_max_error=float(np.max(abs(f - old['F0']))),
                         P0_relative_difference=float(np.linalg.norm(p - old['P0']) / np.linalg.norm(old['P0'])),
                         supplied_p0=47, initial_gap=s['initial_gap'], Jstar=s['Jstar'],
                         system_sha256=e.sha(path)))
    e.atomic_json(out / 'verification.json', dict(status='PASS', identity=ident, system_hashes=hashes,
        systems=rows, shared_matrices=['A', 'Q', 'R', 'W', 'K0', 'F0', 'P0'],
        A_independent_of_B=True, initialization_uses_Kstar=False, base_B_reproduction_max_errors=reproduction,
        supplied_common_bounds=cfg['supplied_common_bounds'], base_output=str(base)))
    e.atomic_json(out / 'resolved_config.json', dict(cfg, identity=ident))
    s = core.engine.load_system(cfg, cfg['ranks'][0])
    rng = np.random.default_rng(2026102307)
    pulse = cfg['sigma'] * rng.normal(size=(1024, 500))
    _, z, y = e.ce_chunk(np.ascontiguousarray(s['F0']), s['B'], s['K0'], np.zeros(500), pulse, np.zeros((1024, 500)))
    label_error = float(np.max(abs(z @ np.concatenate([s['A'], s['B']], axis=1).T - y)))
    assert label_error < 1e-11
    e.atomic_json(out / 'preflight.json', dict(status='PASS', identity=ident,
        noiseless_label_max_error=label_error, existing_engine_noiseless_and_bitwise_resume_checks='base preflight PASS; byte-identical engine',
        systems=rows, slurm_job_id=os.environ['SLURM_JOB_ID']))


def report(cfg, ident, phase):
    core.report(cfg, ident, phase)
    # Preserve the original common-grid comparison alongside refined crossings.
    out = Path(cfg['output'])
    grid = cfg['coarse_reference_budgets']
    seeds = cfg[phase + '_seeds']
    requirements = []
    for rank in cfg['ranks']:
        data = [core.e.read(out / 'raw' / f'ce-r{rank:03d}-s{seed:04d}.json') for seed in seeds]
        for method in ['dense', 'truncated']:
            for epsilon in cfg['absolute_targets']:
                rates = [sum(next(r for r in d['records'] if r['method'] == method and r['ols_samples'] == n)['stable']
                             and next(r for r in d['records'] if r['method'] == method and r['ols_samples'] == n)['gap'] <= epsilon
                             for d in data) / len(seeds) for n in grid]
                hits = [i for i in range(len(grid)) if all(x >= cfg['required_success_fraction'] for x in rates[i:])]
                requirements.append(dict(rank=rank, method=method, absolute_target=epsilon,
                                         sample_count=grid[hits[0]] + cfg['burn'] if hits else None))
    gains = []
    for rank in cfg['ranks']:
        for epsilon in cfg['absolute_targets']:
            nd, nt = [next(r['sample_count'] for r in requirements if r['rank'] == rank and r['method'] == method
                          and r['absolute_target'] == epsilon) for method in ['dense', 'truncated']]
            gains.append(dict(rank=rank, absolute_target=epsilon, seeds=len(seeds), dense_samples=nd, truncated_samples=nt,
                              sample_gain=nd/nt if nd and nt else None,
                              gain_lower_bound=(grid[-1]+cfg['burn'])/nt if nd is None and nt else None))
    dest = out / ('report-' + phase)
    core.write_csv(dest / 'coarse_reference_sample_complexity.csv', requirements)
    core.write_csv(dest / 'coarse_reference_same_accuracy_sample_gain.csv', gains)
    summary = core.e.read(dest / 'summary.json')
    summary.update(coarse_reference_budgets=grid, coarse_reference_gains=gains,
                   refined_budgets=cfg['budgets'], grid_resolution='refined crossings plus preserved original 11-budget comparison')
    core.e.atomic_json(dest / 'summary.json', summary)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['prepare', 'task', 'audit', 'report', 'diagnose'])
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--phase', choices=['pilot', 'confirm'], default='pilot')
    p.add_argument('--task-id', type=int, default=0)
    p.add_argument('--shard', type=int, default=0)
    a = p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    cfg = core.e.read(a.manifest)
    ident = identity(cfg)
    for key, wanted in [('TMPDIR', cfg['temp']), ('XDG_CACHE_HOME', cfg['cache']),
                        ('NUMBA_CACHE_DIR', cfg['cache'] + '/numba'), ('MPLCONFIGDIR', cfg['cache'] + '/matplotlib')]:
        assert os.environ.get(key) == wanted
        Path(wanted).mkdir(parents=True, exist_ok=True)
    with core.threadpool_limits(1):
        if a.mode == 'prepare':
            prepare(cfg, ident)
        elif a.mode == 'task':
            core.task(cfg, ident, a.phase, a.task_id)
        elif a.mode == 'audit':
            core.audit(cfg, ident, a.phase, a.shard)
        elif a.mode == 'report':
            report(cfg, ident, a.phase)
        else:
            from ce500_rank_diagnostic import diagnose
            diagnose(cfg, ident, core)


if __name__ == '__main__':
    main()
