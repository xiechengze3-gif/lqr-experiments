"""X10a local CE dispatch; original model/collector/learner functions are preserved."""
import argparse
import csv
import ctypes
import datetime
import hashlib
import json
import math
import os
import platform
import time
from pathlib import Path
import numpy as np
import frozen_engine as e
import s_ce_original as original
import x8_original as x8
import ce_reference_local as reference

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, indent=2)
        stream.write('\n')


def peak_memory_bytes():
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ['PeakWorkingSetSize', 'WorkingSetSize',
             'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
             'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage']]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    assert psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return int(counters.PeakWorkingSetSize)


def config_load(path):
    config = json.loads(path.read_text())
    assert config['execution'] == 'LOCAL_AUTHOR_APPROVED_X10a'
    assert os.environ.get('X10_LOCAL_AUTHORIZED') == '1'
    assert not os.environ.get('SLURM_JOB_ID'), 'Never masquerade as a Slurm job.'
    for key in ['OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS', 'NUMBA_NUM_THREADS']:
        assert os.environ.get(key) == '1'
    for key in ['TEMP', 'TMP', 'TMPDIR', 'XDG_CACHE_HOME', 'NUMBA_CACHE_DIR', 'MPLCONFIGDIR']:
        value = os.environ[key]
        assert Path(value).drive.upper() == 'E:' and Path(value).is_dir(), (key, value)
    for name, digest in config['sources'].items():
        assert sha(ROOT/name) == digest, name
    from threadpoolctl import threadpool_info
    threads = threadpool_info()
    assert all(item['num_threads'] == 1 for item in threads), threads
    return config, threads


def save_model(s, destination):
    np.savez_compressed(destination/'model.npz', **{key: value for key, value in s.items()
                         if key != 'certificate' and value is not None})
    save_new(destination/'model-certificate.json', s['certificate'])


def run_shared_ce(s, spec, prefixes, destination):
    """Original CE prefix fit and frozen ce_learner; one trajectory shared by arms."""
    assert not destination.exists()
    destination.mkdir(parents=True)
    begin = time.monotonic()
    save_model(s, destination)
    rows, artifacts, fits = [], [], []
    n, m = s['B'].shape
    random = e.rng(10, n, m, spec['system'], spec['seed'])
    vstar = float(np.sum((s['Pstar'] @ (s['A']-s['B']@s['Kstar']))**2))
    for fitted in original.ce_prefixes(s, prefixes, random, dict(ce_burn=512, nu=1.)):
        theta = np.concatenate((fitted['Ahat'], fitted['Bhat']), axis=1)
        fits.append(theta.copy())
        gains = {}
        for arm, rank in [('dense', min(n, m)), ('truncated', 2)]:
            row = dict(spec, algorithm='CE', n=n, m=m, r=2, arm=arm, N=fitted['N'],
                       primitive_transitions=fitted['N']+512, v_star=vstar)
            try:
                gain = e.ce_learner(theta, n, s['Q'], s['R'], rank)
                assessed = e.assess(s, gain)
                gains['K_'+arm] = gain
                row.update(assessed)
                if not row['stable']:
                    row['gap'] = row['relative_gap'] = math.inf
            except (np.linalg.LinAlgError, ValueError, ArithmeticError) as exc:
                row.update(stable=False, gap=math.inf, relative_gap=math.inf,
                           redundant_cost=None, failure=repr(exc))
            rows.append(row)
        path = destination/f"fit-{fitted['N']}.npz"
        np.savez_compressed(path, **fitted, **gains)
        artifacts.append(dict(path=path.name, sha256=sha(path), N=fitted['N']))
        save_new(destination/f"prefix-{fitted['N']}.json", dict(status='COMPLETE_PREFIX',
                 N=fitted['N'], primitive_transitions=fitted['N']+512,
                 fit_sha256=sha(path), records=rows.copy(), artifacts=artifacts.copy()))
    receipt = dict(status='COMPLETE', spec=spec, records=rows, artifacts=artifacts,
                   primitive_transitions=512+max(prefixes), source_sha256=sha(Path(__file__)),
                   engine_sha256=sha(Path(e.__file__)), seconds=time.monotonic()-begin,
                   final_rng_state=json.dumps(random.bit_generator.state, sort_keys=True),
                   execution='LOCAL_AUTHOR_APPROVED_X10a', host=platform.node(),
                   process=os.getpid(), Slurm_job_id=None)
    save_new(destination/'DONE.json', receipt)
    return receipt, fits


def run_x8(case, system, seed, destination):
    assert not destination.exists()
    destination.mkdir(parents=True)
    begin = time.monotonic()
    sigma = np.ones(case['rank']) if case['family'] == 'exact' else case['rho']**np.arange(48)
    a, b = x8.make_A(system), x8.make_B(sigma, system)
    np.savez_compressed(destination/'model.npz', A=a, B=b)
    orders = list(range(1, 48))+['dense']
    result, g0 = x8.run(a, b, 100*system+seed, orders)
    rows = [dict(config=case['config'], family=case['family'], system=system, seed=seed,
                 N=N, order=str(order), rel_gap=value, g0=g0,
                 primitive_transitions=N+512)
            for N, values in result.items() for order, value in values.items()]
    assert len(rows) == 480
    receipt = dict(status='COMPLETE', spec=dict(case, system=system, seed=seed),
                   records=rows, primitive_transitions=262144+512,
                   original_source_sha256=sha(Path(x8.__file__)),
                   wrapper_sha256=sha(Path(__file__)), seconds=time.monotonic()-begin,
                   execution='LOCAL_AUTHOR_APPROVED_X10a', host=platform.node(),
                   process=os.getpid(), Slurm_job_id=None)
    save_new(destination/'DONE.json', receipt)
    return receipt


def equivalence(s, spec, prefixes, actual, fits, destination):
    """Reference repeats a NEW pilot input, never an existing formal CE result."""
    collected, original_fit = [], reference.fit_model

    def capture(gram, cross):
        fitted = original_fit(gram, cross)
        collected.append(fitted.copy())
        return fitted

    random = e.rng(10, s['A'].shape[0], s['B'].shape[1], spec['system'], spec['seed'])
    original_rng = reference.rng
    reference.fit_model = capture
    reference.rng = lambda *args: random
    try:
        expected = reference.ce_run(s, dict(spec, trial=spec['seed'], r=2),
                    dict(ce_burn=512, nu=1., ce_prefixes=prefixes), destination/'reference.json')
    finally:
        reference.fit_model, reference.rng = original_fit, original_rng
    assert len(collected) == 3*len(fits)
    assert all(np.array_equal(a, b) for a, b in zip(fits, collected[::3]))
    assert actual['final_rng_state'] == json.dumps(random.bit_generator.state, sort_keys=True)
    assert expected['transitions'] == actual['primitive_transitions']
    assert len(expected['records']) == len(actual['records'])
    with np.load((destination/'reference.json').with_suffix('.npz')) as archive:
        for left, right in zip(expected['records'], actual['records']):
            assert left['mode'] == right['arm'] and left['N'] == right['N']
            for key in ['stable', 'rho', 'gap', 'relative_gap', 'redundant_cost']:
                if left['stable']:
                    assert left.get(key) == right.get(key), key
                elif key == 'stable':
                    assert left[key] == right[key]
            if left['stable']:
                with np.load(destination/f"fit-{right['N']}.npz") as fitted:
                    assert np.array_equal(archive[str(right['N'])+'_'+right['arm']], fitted['K_'+right['arm']])
    return dict(status='PASS_BITWISE_FULL_FITS_GAINS_METRICS_RNG_COUNTS',
                actual_primitive_transitions=actual['primitive_transitions'],
                reference_primitive_transitions=expected['transitions'])


def pilot(config, threads):
    dest = ROOT/'ce-pilot-v2'
    assert not dest.exists()
    dest.mkdir()
    started = time.monotonic()
    measured = []
    old_x8_path = ROOT/'ce-pilot-v1/x8/DONE.json'
    x = json.loads(old_x8_path.read_text())
    assert x['status'] == 'COMPLETE'
    assert x['original_source_sha256'] == sha(Path(x8.__file__))
    assert x['spec'] == dict(family='geometric', config='rho0.85', rho=.85, system=9901, seed=7701)
    assert x['primitive_transitions'] == 262656 and len(x['records']) == 480
    assert x['wrapper_sha256'] == sha(ROOT/'ce-src/ce_driver.py')
    # Complete unchanged X8 pilot reused by reference, never sampled again.
    measured.append(dict(part='x8', seconds=x['seconds'], physical_transitions=x['primitive_transitions'],
                         source_identity='ORIGINAL_RUN_FUNCTION_UNCHANGED_ALL480_OUTPUTS'))
    for part, s, spec, prefixes in [
        ('dimension', original.model('S', 96, 9902),
         dict(part='dimension', config='n96', system=9902, seed=7702), config['dimension_N_large']),
        ('redundancy', e.plant(12, 11, 2, 9903, null_scale=.25),
         dict(part='redundancy', config='m11', system=9903, seed=7703, null_scale=.25), [4096, 8192])]:
        path = dest/part
        actual, fits = run_shared_ce(s, spec, prefixes, path)
        check = equivalence(s, spec, prefixes, actual, fits, path)
        measured.append(dict(part=part, seconds=actual['seconds'], equivalence=check,
                             physical_transitions=2*actual['primitive_transitions']))
    peak = peak_memory_bytes()
    assert peak <= config['local_memory_ceiling_bytes']
    proof = dict(status='LOCAL_RESOURCE_EQUIVALENCE_PASS', cases=measured,
                 seconds=time.monotonic()-started, peak_working_set_bytes=peak,
                 threadpools=threads, config_sha256=sha(ROOT/'ce-config-protocol-v2.json'),
                 source_sha256=sha(Path(__file__)), Grace_SU=0, Slurm_job_id=None,
                 no_gap_based_selection=True, no_performance_readout=True,
                 formal_trajectories_collected=0,
                 physical_transitions=sum(r['physical_transitions'] for r in measured))
    save_new(dest/'PILOT.json', proof)
    print(json.dumps(proof), flush=True)


def formal(config):
    proof = json.loads((ROOT/'ce-pilot-v2/PILOT.json').read_text())
    assert proof['status'] == 'LOCAL_RESOURCE_EQUIVALENCE_PASS'
    assert proof['config_sha256'] == sha(ROOT/'ce-config-protocol-v2.json')
    dest = ROOT/'ce-formal-v2'
    assert not dest.exists()
    dest.mkdir()
    completed = []
    for case in config['x8_cases']:
        for system in range(8):
            for seed in range(4):
                path = dest/'x8'/case['config']/f's{system}-t{seed}'
                result = run_x8(case, system, seed, path)
                completed.append(dict(path=str(path.relative_to(dest)), done_sha256=sha(path/'DONE.json'),
                                      physical_transitions=result['primitive_transitions']))
            print(json.dumps(dict(part='x8', config=case['config'], system=system, status='COMPLETE')), flush=True)
    for n in config['dimension_n']:
        prefixes = config['dimension_N_large'] if n >= 60 else config['dimension_N']
        for system in range(301, 309):
            s = original.model('S', n, system)
            for seed in range(1601, 1605):
                spec = dict(part='dimension', config=f'n{n}', system=system, seed=seed)
                path = dest/'dimension'/f'n{n}'/f's{system}-t{seed}'
                result, _ = run_shared_ce(s, spec, prefixes, path)
                completed.append(dict(path=str(path.relative_to(dest)), done_sha256=sha(path/'DONE.json'),
                                      physical_transitions=result['primitive_transitions']))
            print(json.dumps(dict(part='dimension', n=n, system=system, status='COMPLETE')), flush=True)
    for extra in config['redundant_inputs']:
        m = 2+extra
        for system in range(101, 109):
            s = e.plant(12, m, 2, system, null_scale=.25)
            for seed in range(1001, 1005):
                spec = dict(part='redundancy', config=f'm{m}', system=system, seed=seed, null_scale=.25)
                path = dest/'redundancy'/f'm{m}'/f's{system}-t{seed}'
                result, _ = run_shared_ce(s, spec, [4096, 8192], path)
                completed.append(dict(path=str(path.relative_to(dest)), done_sha256=sha(path/'DONE.json'),
                                      physical_transitions=result['primitive_transitions']))
            print(json.dumps(dict(part='redundancy', m=m, system=system, status='COMPLETE')), flush=True)
    assert len(completed) == 672
    receipt = dict(status='COMPLETE_FORMAL_NEW_CONFIGURATIONS_ONLY', paths=completed,
                   config_sha256=sha(ROOT/'ce-config-protocol-v2.json'),
                   source_sha256=sha(Path(__file__)), Grace_SU=0, Slurm_job_id=None,
                   physical_transitions=sum(r['physical_transitions'] for r in completed))
    save_new(dest/'FORMAL_DONE.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'paths'}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['pilot', 'formal'])
    p.add_argument('--config', type=Path, required=True)
    a = p.parse_args()
    cfg, pools = config_load(a.config)
    if a.mode == 'pilot':
        pilot(cfg, pools)
    else:
        formal(cfg)
