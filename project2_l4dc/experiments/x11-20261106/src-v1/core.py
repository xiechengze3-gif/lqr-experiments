import ctypes,json,math,os,platform,time
from pathlib import Path
import hashlib,numpy as np
import frozen_engine as e
import s_ce_original as original
import ce_reference_local as reference
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
                   execution='LOCAL_AUTHOR_APPROVED_X11', host=platform.node(),
                   process=os.getpid(), Slurm_job_id=None)
    save_new(destination/'DONE.json', receipt)
    return receipt, fits

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
