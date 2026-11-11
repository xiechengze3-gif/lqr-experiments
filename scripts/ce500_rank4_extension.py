"""Add rank 4 to the frozen CE500 family without rerunning existing ranks."""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
if os.environ.get('LQR_NUMBA_SITE'):
    sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from scipy.optimize import brentq
from threadpoolctl import threadpool_limits, threadpool_info
import rank_sweep100 as e
import ce500_matched_gap as run
from ce_matched_initial_gap import performance_gap


def identity(cfg):
    result = run.identity(cfg)
    result['extension_sources'] = {p: e.sha(ROOT / p) for p in
        ('scripts/ce500_rank4_extension.py', 'scripts/ce500_rank_scaling_report.py')}
    return result


def prepare(cfg, ident, manifest):
    out = Path(cfg['output']); out.mkdir(parents=True, exist_ok=True)
    if (out / 'preflight.json').exists():
        assert e.read(out / 'preflight.json')['identity'] == ident
        return
    began = time.monotonic()
    source = Path(cfg['source_output'])
    assert e.sha(source / 'artifact_sha256.json') == cfg['source_manifest_sha256']
    for name, expected in cfg['source_numeric_sha256'].items():
        assert e.sha(ROOT / name) == expected, name
    source_path = source / 'systems/r002.npz'
    assert e.sha(source_path) == cfg['source_system_sha256']
    with np.load(source_path, allow_pickle=False) as a:
        s = {k: float(a[k]) if a[k].ndim == 0 else a[k].copy() for k in a.files}
    common = {k: s[k].copy() for k in ('A', 'U', 'V', 'initialization_direction')}
    n = cfg['n']; rank = 4
    s['B'] = cfg['b'] * s['U'][:, :rank] @ s['V'][:, :rank].T
    s['Kstar'], s['Pstar'] = e.dare(s['A'], s['B'], s['Q'], s['R'])
    s['Jstar'] = float(np.trace(s['Pstar']))
    direction = s['initialization_direction']
    hi = .01
    while performance_gap(s, s['Kstar'] + hi * direction)[0] < cfg['initial_gap']:
        hi *= 2
    alpha = brentq(lambda a: performance_gap(s, s['Kstar'] + a * direction)[0] - cfg['initial_gap'],
                   0, hi, xtol=5e-15, rtol=1e-14)
    s['K0'] = s['Kstar'] + alpha * direction
    gap, rho, _ = performance_gap(s, s['K0'])
    s['F0'] = s['A'] - s['B'] @ s['K0']
    s['P0'] = solve_discrete_lyapunov(s['F0'].T, s['Q'] + s['K0'].T @ s['K0'])
    actual = float(np.trace(s['P0']) - s['Jstar'])
    certificate = float(np.max(abs(s['P0'] - s['F0'].T @ s['P0'] @ s['F0'] - s['Q'] - s['K0'].T @ s['K0'])))
    original_residual = float(np.max(abs(s['A'] - s['B'] @ s['K0_original'] - s['F0_original'])))
    assert abs(actual - 1) < 1e-9 and abs(gap - 1) < 1e-10 and rho < 1
    assert certificate < 1e-10 and original_residual < 2e-12
    assert np.linalg.matrix_rank(s['B'], tol=1e-10) == rank
    assert np.linalg.matrix_rank(s['K0'], tol=1e-10) == n
    assert max(abs(np.linalg.eigvals(s['A']))) > 1
    assert max(abs(np.linalg.eigvals(s['F0_original']))) < 1
    np.testing.assert_allclose(s['F0_original'] @ s['U'][:, 0], .75 * s['U'][:, 0], atol=1e-12)
    for name, value in common.items():
        np.testing.assert_array_equal(s[name], value)
    # A, U, V and D are copied from the verified old artifact, not regenerated.
    s.update(initial_gap=cfg['initial_gap'], actual_initial_gap=actual, initialization_alpha=alpha)
    system_path = out / 'systems/r004.npz'; e.save_npz(system_path, **s)
    check = dict(rank=rank, initial_gap=actual, J0=float(np.trace(s['P0'])), Jstar=s['Jstar'],
                 rho_K0=rho, B_rank=rank, K0_rank=n, alpha=alpha,
                 certificate_residual=certificate, original_closed_loop_max_error=original_residual,
                 common_A_U_V_initialization_direction_bitwise_equal=True)
    e.atomic_json(out / 'verification.json', dict(status='PASS', identity=ident, systems=[check],
                    system_hashes={'4': e.sha(system_path)}, source_system_sha256=e.sha(source_path)))
    e.atomic_json(out / 'resolved_config.json', dict(cfg, identity=ident))
    # Actual noisy trajectory; independently solve raw joint least squares.
    pulse, noise = run.rngs(cfg, 9000)
    f = np.ascontiguousarray(s['F0']); count = 8192
    x, _ = e.nominal_chunk(f, np.zeros(n), noise.normal(size=(cfg['burn'], n)))
    pulses = cfg['sigma'] * pulse.normal(size=(count, n)); noises = noise.normal(size=(count, n))
    _, z, y = e.ce_chunk(f, s['B'], s['K0'], x, pulses, noises)
    truth = np.concatenate((s['A'], s['B']), axis=1)
    direct = np.linalg.lstsq(z, y, rcond=None)[0].T
    sufficient = run.cho_solve(run.cho_factor(z.T @ z), (y.T @ z).T).T
    error = float(np.max(abs(direct - sufficient)))
    noiseless_error = float(np.max(abs(np.linalg.lstsq(z, y - noises, rcond=None)[0].T - truth)))
    label_error = float(np.max(abs(y - z @ truth.T - noises)))
    assert max(error, noiseless_error, label_error) < 2e-11
    paths = {k: out / 'diagnostics' / k for k in ('continuous', 'resumed')}
    run.task(cfg, ident, rank, 9001, [2048, 4096], paths['continuous'])
    run.task(cfg, ident, rank, 9001, [2048], paths['resumed'])
    run.task(cfg, ident, rank, 9001, [2048, 4096], paths['resumed'])
    a = e.read(paths['continuous'] / 'raw/ce-r004-s9001.json')
    b = e.read(paths['resumed'] / 'raw/ce-r004-s9001.json')
    assert a['records'] == b['records']
    with np.load(paths['continuous'] / 'checkpoints/ce-r004-s9001.npz') as aa, np.load(paths['resumed'] / 'checkpoints/ce-r004-s9001.npz') as bb:
        for key in ('x', 'gram', 'cross'):
            np.testing.assert_array_equal(aa[key], bb[key])
    for name in run.SOURCES + ['scripts/ce500_rank4_extension.py', 'scripts/ce500_rank_scaling_report.py']:
        dest = out / 'frozen' / name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    shutil.copyfile(manifest, out / 'frozen/config.json')
    e.atomic_json(out / 'preflight.json', dict(status='PASS', identity=ident, seconds=time.monotonic() - began,
        diagnostic_primitive_transitions=count + cfg['burn'] + 2 * (4096 + cfg['burn']),
        raw_joint_OLS_vs_sufficient_statistics_error=error, noiseless_AB_error=noiseless_error,
        label_alignment_error=label_error, checkpoint_resume_bitwise_equal=True,
        peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        threadpools=threadpool_info(), slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS', **check)), flush=True)


def main():
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['prepare', 'task'])
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--phase', choices=['pilot', 'confirm'], default='pilot')
    p.add_argument('--task-id', type=int)
    a = p.parse_args(); assert os.environ.get('SLURM_JOB_ID')
    cfg = e.read(a.manifest); ident = identity(cfg)
    for key, expected in [('TMPDIR', cfg['temp']), ('NUMBA_CACHE_DIR', cfg['cache'] + '/numba'),
                          ('MPLCONFIGDIR', cfg['cache'] + '/matplotlib')]:
        assert os.environ.get(key) == expected
        Path(expected).mkdir(parents=True, exist_ok=True)
    with threadpool_limits(1):
        if a.mode == 'prepare':
            prepare(cfg, ident, a.manifest)
        else:
            assert e.read(Path(cfg['output']) / 'preflight.json')['identity'] == ident
            seed = cfg[a.phase + '_seeds'][a.task_id]
            result = run.task(cfg, ident, 4, seed, cfg[a.phase + '_budgets'])
            e.atomic_json(Path(cfg['output']) / 'task_receipts' / f'{a.phase}-{a.task_id:03d}.json',
                dict(result, phase=a.phase, task_id=a.task_id, slurm_job_id=os.environ['SLURM_JOB_ID']))


if __name__ == '__main__':
    main()
