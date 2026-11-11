"""Independent checks for the new scientific path, not historical file edits."""
import argparse
import json
from pathlib import Path
import numpy as np
from adaptive_rank_run import (identity, make_system, direct_data, estimate, update,
                               ROOT, rng_for, atomic_json, pi_gain)
from adaptive_rank import select, pi_update
from dense_scaling import pulse_moments, targets
from full_lstd import verify as verify_lstd


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    cfg = json.loads(a.manifest.read_text())
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        checks = dict(lstd=verify_lstd())
        mat = np.diag([4., 2., .5])
        out, _, info = select(mat, 'adaptive_1', 1.)
        assert info['retained_rank']==2 and np.array_equal(out, np.diag([4.,2.,0.]))
        out, _, info = select(mat, 'adaptive_2', 3.)
        assert info['retained_rank']==0 and np.count_nonzero(out)==0
        # Threshold zero recovers all directions, high threshold permits rank zero.
        assert np.allclose(select(mat, 'adaptive_1', 0.)[0], mat)
        rng = rng_for(771)
        u, _ = np.linalg.qr(rng.normal(size=(3,3)))
        v, _ = np.linalg.qr(rng.normal(size=(3,3)))
        rotated, _, rotated_info = select(u@mat@v.T, 'adaptive_1', 1.)
        assert np.allclose(rotated, u@np.diag([4.,2.,0.])@v.T)
        assert rotated_info['retained_rank']==2
        checks['threshold_zero_rank_and_rotation']=True
        task = dict(id=-1, n=6, r=2, system_seed=0, trial_seed=0, spectrum='exact')
        s, _ = make_system(task, cfg)
        k = s['Kstar']
        x, full, halves, used = direct_data(s, k, np.zeros(6), 4096, cfg['burn'],
                                            cfg['horizon'], rng_for(419))
        prior = next(pulse_moments(s, k, np.zeros(6), [4096], cfg['horizon'], 1.,
                                   rng_for(419), burn=cfg['burn']))
        assert used == prior[-1]
        assert np.allclose(x, prior[1], rtol=1e-10, atol=1e-10)
        assert np.allclose(full[2], prior[2], rtol=1e-10, atol=1e-10)
        assert np.allclose(full[0], prior[3], rtol=1e-10, atol=1e-10)
        checks['direct_original_estimator_and_transitions']=True
        for method, rank in (('dense', None), ('known_rank', 2), ('known_rank', 0)):
            actual = pi_update(full[0], full[1], s['R'], method, known_rank=rank)[0]
            expected = pi_gain(s, full[0], full[1], rank)[0]
            assert np.allclose(actual, expected, rtol=1e-11, atol=1e-11)
        checks['existing_joint_pi_and_psd_equivalence']=True
        for algorithm in cfg['algorithms']:
            _, raw, scale, _, diag = estimate(s, s['K0'], np.zeros(6), algorithm,
                4096, cfg, rng_for(877))
            assert raw is not None and scale is not None, (algorithm, diag)
            # Poison all evaluator-only fields and vary the supplied reference rank.
            # Adaptive policy must remain exactly identical.
            clean, _, info = update(s, s['K0'], algorithm, raw, scale, 'adaptive_1', 2, cfg)
            poisoned = dict(s, B=np.full((6,6),77.), Kstar=np.full((6,6),88.),
                            Jstar=1e20, initial_gap=1e20)
            dirty, _, dirty_info = update(poisoned, s['K0'], algorithm, raw, scale,
                                          'adaptive_1', 5, cfg)
            assert np.array_equal(clean, dirty) and info==dirty_info
        checks['adaptive_no_true_model_rank_or_cost_access']=True
        # Fixed initial spectral certificate, fixed A across nested spectra.
        hashes = {}
        for task in cfg['tasks']:
            s, diag = make_system(task, cfg)
            expected = np.eye(task['n'])/(1-cfg['alpha']**2)
            from scipy.linalg import solve_discrete_lyapunov
            assert np.allclose(solve_discrete_lyapunov(s['A'].T, s['Q']), expected)
            key = (task['n'],task['system_seed'])
            h = {k:v for k,v in diag['matrix_sha256'].items() if k!='B'}
            if key in hashes:
                assert hashes[key]==h
            hashes[key]=h
        checks['fixed_initial_spectral_certificate']=True
    atomic_json(a.output, dict(status='PASS', identity=identity(a.manifest), checks=checks))
    print(json.dumps(dict(status='PASS', output=str(a.output))))


if __name__ == '__main__':
    main()
