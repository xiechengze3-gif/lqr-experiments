"""Missing-cell Grace runner. Frozen historical estimators are imported unchanged."""
import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
import numpy as np
from dense_scaling import atomic_json, ce, eta, evaluate, require_compute, rng_for, system, trunc
from final_round import actor, collect, quality
from direct_stein_final import correct, update
from npg_batched_collector import collect as npg_collect


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def checked_config():
    cfg = read(ROOT/'manifest.json')
    for name, digest in cfg['sources'].items():
        if sha(ROOT/name) != digest:
            raise ValueError('Frozen source hash changed: '+name)
    return cfg


def model(task):
    return system(dict(n=task['n'], m=task['n'], r=task['r'], system_seed=task['system_seed'],
                       family='coupled_unstable', stabilizer='isotropic', tail=0., tail_shape='energy'))


def run_npg(task, cfg, out, max_updates=None):
    out.mkdir(parents=True, exist_ok=True)
    ident = sha(ROOT/'manifest.json')
    final = out/'result.json'
    if final.exists():
        assert read(final)['identity'] == ident
        return
    s = model(task)
    step = cfg['npg']['step_multiplier']*eta(s)
    schedule = cfg['npg']['batch_schedule']
    if max_updates is not None:
        schedule = schedule[:max_updates]
    combined = []
    for method in ('dense', 'known_rank'):
        ckpt = out/f'{method}.npz'
        k, x, total, first, status = s['K0'].copy(), np.zeros(task['n']), 0, 0, 'completed'
        q, _ = evaluate(s, k)
        rows = [dict(method=method, stage=0, transitions=0, observed=True, **q)]
        if ckpt.exists():
            with np.load(ckpt, allow_pickle=False) as saved:
                assert str(saved['identity']) == ident
                k, x, total = saved['K'].copy(), saved['x'].copy(), int(saved['total'])
                first, rows, status = int(saved['next_stage']), json.loads(str(saved['rows'])), str(saved['status'])
        for stage in range(first, len(schedule)):
            if status != 'completed':
                break
            count = schedule[stage]
            used = cfg['npg']['burn']+(count+1)*cfg['npg']['horizon']
            # Same continuous state, chunking, innovations and original-coordinate
            # OLS as the archived growing80 run. Truth never enters the update.
            try:
                _, x, raw, _, _, actual = next(npg_collect(s, k, x, [count], cfg['npg']['horizon'],
                    cfg['npg']['sigma'], rng_for(773991, task['n'], task['system_seed'], task['sampling_seed'], stage),
                    burn=cfg['npg']['burn']))
                assert used == actual
            except (ValueError, np.linalg.LinAlgError, ArithmeticError) as error:
                total += used
                status = 'numerical_failure'
                rows.append(dict(method=method, stage=stage+1, transitions=total, observed=True,
                                 stable=None, gap=None, failure=status, detail=str(error)))
            else:
                total += actual
                try:
                    z = raw if method == 'dense' else trunc(raw, task['r'])
                    candidate = k-step*(s['R']@k+z)
                    q, _ = evaluate(s, candidate)
                    k = candidate
                    if not q['stable']:
                        status = 'controller_instability'
                    rows.append(dict(method=method, stage=stage+1, N=count, transitions=total,
                                     observed=True, eta=step, failure=None if status=='completed' else status, **q))
                except (ValueError, np.linalg.LinAlgError, ArithmeticError) as error:
                    status = 'numerical_failure'
                    rows.append(dict(method=method, stage=stage+1, transitions=total, observed=True,
                                     stable=None, gap=None, failure=status, detail=str(error)))
            temporary = ckpt.with_suffix('.tmp')
            with temporary.open('wb') as stream:
                np.savez(stream, identity=ident, K=k, x=x, total=total, next_stage=stage+1,
                         rows=json.dumps(rows, allow_nan=False), status=status)
            os.replace(temporary, ckpt)
            print(json.dumps(dict(task=task.get('id'), method=method, stage=stage+1, status=status)), flush=True)
        combined += rows
    atomic_json(final, dict(identity=ident, task=task, records=combined, initial_gap=s['initial_gap'],
                            planned_stages=len(schedule), planned_transitions=task['planned_transitions'],
                            actual_transitions=sum(max(r['transitions'] for r in combined if r['method']==m)
                                                   for m in ('dense', 'known_rank')),
                            slurm_job_id=os.environ['SLURM_JOB_ID']))


def run_task(task, cfg, output):
    dest = output/'tasks'/f"task-{task['id']:03d}"
    dest.mkdir(parents=True, exist_ok=True)
    identity = sha(ROOT/'manifest.json')
    if task['algorithm'] == 'Direct_Stein_PI':
        frozen = dest/'frozen_config.json'
        if frozen.exists():
            assert sha(frozen) == identity
        else:
            frozen.write_bytes((ROOT/'manifest.json').read_bytes())
        actor(dest, [task['system_seed']], [task['sampling_seed']], [task['blocks']],
              cfg['pi']['eta'], 'core', updates=cfg['pi']['updates'], n=task['n'], rank=task['r'])
    elif task['algorithm'] == 'NPG':
        run_npg(task, cfg, dest)
    elif task['algorithm'] == 'CE':
        final = dest/'result.json'
        if final.exists():
            assert read(final)['identity'] == identity
            return
        s = model(task)
        rows, _ = ce(dict(n=task['n'], r=task['r'], system_seed=task['system_seed'],
                          trial_seed=task['sampling_seed'], budgets=cfg['ce']['budgets'], sigma=1.), s)
        atomic_json(final, dict(identity=identity, task=task, records=rows, initial_gap=s['initial_gap'],
                                actual_transitions=max(cfg['ce']['budgets'])+512,
                                slurm_job_id=os.environ['SLURM_JOB_ID']))
    else:
        raise ValueError(task['algorithm'])
    atomic_json(dest/'execution.json', dict(identity=identity, task_id=task['id'],
                location='Grace Slurm compute node', hostname=platform.node(),
                slurm_job_id=os.environ['SLURM_JOB_ID'],
                slurm_array_job_id=os.environ.get('SLURM_ARRAY_JOB_ID'),
                threads=1, TMPDIR=os.environ.get('TMPDIR'),
                XDG_CACHE_HOME=os.environ.get('XDG_CACHE_HOME')))


def replay(cfg):
    checks = []
    for item in read(ROOT/'fixtures.json'):
        task = item['task']
        s = model(task)
        np.testing.assert_allclose(s['initial_gap'], item['initial_gap'], rtol=1e-8, atol=1e-7)
        if item['algorithm'] == 'NPG':
            assert item['engine_sha256'] == sha(ROOT/'dense_scaling.py')
            _, _, z, _, _, used = next(npg_collect(s, s['K0'], np.zeros(task['n']),
                [cfg['npg']['batch_schedule'][0]], 16, 1., rng_for(773991, task['n'], task['system_seed'], 0, 0), burn=1024))
            for method in ('raw', 'truncated'):
                zz = z if method == 'raw' else trunc(z, task['r'])
                k = s['K0']-cfg['npg']['step_multiplier']*eta(s)*(s['R']@s['K0']+zz)
                q, _ = evaluate(s, k)
                expected = next(r for r in item['rows'] if r['method']==method and r['stage']==1)
                assert used == expected['transitions'] and q['stable'] == expected['stable']
                for key in ('cost', 'gap', 'rho'):
                    np.testing.assert_allclose(q[key], expected[key], rtol=1e-8, atol=1e-7)
        elif item['algorithm'] == 'Direct_Stein_PI':
            _, (g, z, _), halves, used = collect(s, s['K0'], np.zeros(task['n']), 32768,
                rng_for(202610142, task['n'], task['r'], task['system_seed'], 0, 1))
            gg, zz, _ = correct(g, z, task['method'], halves, task['r'] if task['method']=='known_rank' else None)
            candidate, _ = update(s['K0'], s['R'], gg, zz, .25)
            q, _ = quality(s, candidate)
            expected = item['rows'][1]
            assert used == expected['transitions'] and q['stable'] == expected['stable']
            for key in ('cost', 'gap', 'rho'):
                np.testing.assert_allclose(q[key], expected[key], rtol=1e-8, atol=1e-7)
        else:
            assert item['algorithm'] == 'CE' and item['engine_sha256'] == sha(ROOT/'dense_scaling.py')
            current, _ = ce(dict(task, sigma=1., budgets=[min(cfg['ce']['budgets'])]), s)
            for q, expected in zip(current, item['rows']):
                assert q['method'] == expected['method'] and q['transitions'] == expected['transitions']
                for key in ('cost', 'gap', 'rho'):
                    np.testing.assert_allclose(q[key], expected[key], rtol=1e-8, atol=1e-7)
        checks.append(dict(algorithm=item['algorithm'], n=task['n'], r=task['r'], status='PASS'))
    return checks


def verify_npg_resume(cfg, output):
    """Compare a real short trajectory with interruption after a saved stage."""
    from unittest.mock import patch
    small = dict(cfg, npg=dict(cfg['npg'], batch_schedule=[512, 1024, 2048]))
    task = dict(algorithm='NPG', n=6, r=2, system_seed=9003, sampling_seed=0,
                planned_transitions=2*sum(1024+(b+1)*16 for b in (512, 1024, 2048)))
    whole, resumed = output/'resume-whole', output/'resume-interrupted'
    run_npg(task, small, whole)
    calls = 0
    original = npg_collect

    def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt('Intentional checkpoint verification')
        return original(*args, **kwargs)

    try:
        with patch(__name__+'.npg_collect', side_effect=interrupted):
            run_npg(task, small, resumed)
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError('The checkpoint interruption did not occur')
    assert not (resumed/'result.json').exists()
    run_npg(task, small, resumed)
    a, b = read(whole/'result.json'), read(resumed/'result.json')
    assert a['records'] == b['records'] and a['actual_transitions'] == b['actual_transitions']
    for method in ('dense', 'known_rank'):
        with np.load(whole/f'{method}.npz') as left, np.load(resumed/f'{method}.npz') as right:
            for key in ('K', 'x', 'total', 'next_stage', 'status'):
                np.testing.assert_array_equal(left[key], right[key])
    return dict(status='PASS', records_and_final_state_bitwise_equal=True,
                actual_transitions=a['actual_transitions'])


def benchmark(cfg, output):
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    for test in ('scripts/test_direct_stein_final.py', 'scripts/test_final_failure_paths.py'):
        subprocess.run([sys.executable, '-B', str(ROOT/test)], cwd=ROOT, check=True)
    checks = replay(cfg)
    resume_check = verify_npg_resume(cfg, output)
    # Check the complete requested generator grid before launching sampled work.
    for n in cfg['dimensions']:
        for rank in cfg['ranks']:
            for seed in cfg['pi']['system_seeds']+[0, 1]:
                s = model(dict(n=n, r=rank, system_seed=seed))
                assert evaluate(s, s['K0'])[0]['stable']
    timings = []
    for n in (50, 100):
        # Full real data generation and learning, including maximum-dimension
        # late batch allocations. Pilot systems never enter formal inference.
        for algorithm in ('Direct_Stein_PI', 'NPG', 'CE'):
            task = dict(algorithm=algorithm, id=len(timings), n=n, r=32, system_seed=9001,
                        sampling_seed=0, blocks=32768, updates=8,
                        planned_transitions=3*8*(512+32769*16) if algorithm=='Direct_Stein_PI' else
                            2*sum(1024+(b+1)*16 for b in cfg['npg']['batch_schedule'][:2]) if algorithm=='NPG' else
                            max(cfg['ce']['budgets'])+512)
            before = time.monotonic()
            if algorithm == 'NPG':
                run_npg(task, cfg, output/f'pilot-n{n}-npg', max_updates=2)
            else:
                run_task(task, cfg, output/f'pilot-n{n}-{algorithm}')
            timings.append(dict(n=n, algorithm=algorithm, seconds=time.monotonic()-before,
                                sampled_transitions=task['planned_transitions'],
                                peak_process_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
        # Largest configured batch in the largest dimension, not a synthetic
        # linear solve. Includes actual sampling, fit, correction and update.
        s = model(dict(n=n, r=32, system_seed=9002))
        before = time.monotonic()
        _, (g, z, _), halves, used = collect(s, s['K0'], np.zeros(n), 524288, rng_for(202610159, n))
        for method in cfg['pi']['methods']:
            gg, zz, _ = correct(g, z, method, halves, 32 if method=='known_rank' else None)
            update(s['K0'], s['R'], gg, zz, .25)
        timings.append(dict(n=n, algorithm='PI_max_batch', seconds=time.monotonic()-before,
                            sampled_transitions=used,
                            peak_process_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    result = dict(status='PASS', identity=sha(ROOT/'manifest.json'), replay=checks,
                  npg_checkpoint_replay=resume_check, timings=timings,
                  wall_seconds=time.monotonic()-start, threads=1,
                  peak_process_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  slurm_job_id=os.environ['SLURM_JOB_ID'],
                  configured_temp=os.environ.get('TMPDIR'), configured_cache=os.environ.get('XDG_CACHE_HOME'),
                  production_submission_authorized_by_this_file=False)
    atomic_json(output/'benchmark.json', result)
    print(json.dumps(result), flush=True)


def report(cfg, output):
    """Retain terminal failures; missing task files are explicit incompletes."""
    rows, coverage = [], []
    sources, systems, policy_checks = [], {}, []
    for task in cfg['tasks']:
        dest = output/'tasks'/f"task-{task['id']:03d}"
        files = list((dest/'core').glob('n*.json')) if task['algorithm']=='Direct_Stein_PI' else [dest/'result.json']
        files = [p for p in files if p.exists()]
        coverage.append(dict(task_id=task['id'], algorithm=task['algorithm'], outputs=len(files),
                             expected_outputs=3 if task['algorithm']=='Direct_Stein_PI' else 1,
                             present=len(files)==(3 if task['algorithm']=='Direct_Stein_PI' else 1)))
        sources.extend((p, task, False) for p in files)
    for entry in cfg['reused_pi']:
        sources.append((ROOT/'reused_pi'/Path(entry['path'].replace('\\', '/')).name,
                        dict(entry, algorithm='Direct_Stein_PI'), True))
    for path, task, reused in sources:
        data = read(path)
        if reused:
            assert sha(path) == task['sha256']
        records = data.get('rows', data.get('records', []))
        if task['algorithm'] == 'Direct_Stein_PI':
            assert data['meta']['planned_transitions'] == 8*(512+(task['blocks']+1)*16)
            key = (task['n'], task['r'], task['system_seed'])
            if key not in systems:
                systems[key] = model(task)
            last = records[-1]
            with np.load(path.with_suffix('.npz'), allow_pickle=False) as saved:
                q, _ = quality(systems[key], saved['K'])
            if last.get('stable') is not None:
                assert q['stable'] == last['stable']
                if q['stable']:
                    np.testing.assert_allclose(q['gap'], last['gap'], rtol=1e-8, atol=1e-7)
            assert data['meta']['actual_transitions'] == last['stage']*(512+(task['blocks']+1)*16)
            policy_checks.append(dict(path=str(path), status='PASS', reused=reused))
        for method in sorted({r.get('method', data.get('meta', {}).get('method')) for r in records}):
            values = [r for r in records if r.get('method', data.get('meta', {}).get('method'))==method]
            chosen = values if task['algorithm']=='CE' else [values[-1]]
            for row in chosen:
                desired = 8 if task['algorithm']=='Direct_Stein_PI' else 80
                complete = task['algorithm']=='CE' or row.get('stage') == desired or bool(row.get('failure'))
                g = row.get('normalized_gap', row.get('relative_gap'))
                rows.append(dict(algorithm=task['algorithm'], n=task['n'], r=task['r'],
                                 system_seed=task['system_seed'], method=method, reused=reused,
                                 transitions=row['transitions'], stage=row.get('stage'), complete=complete,
                                 stable=row.get('stable'), gap=row.get('gap'), g=g,
                                 success=bool(complete and row.get('stable') and g is not None and g<=.1),
                                 failure=row.get('failure'), source=str(path)))
    dest = output/'report'
    dest.mkdir(exist_ok=True)
    for name, values in [('endpoints', rows), ('task_coverage', coverage)]:
        if values:
            with (dest/f'{name}.csv').open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(values[0]))
                writer.writeheader();writer.writerows(values)
    atomic_json(dest/'summary.json', dict(status='COMPLETE' if all(c['present'] for c in coverage) else 'INCOMPLETE',
                                        planned_tasks=len(cfg['tasks']), present_tasks=sum(c['present'] for c in coverage),
                                        reused_pi=len(cfg['reused_pi']), primary_target=.1))
    atomic_json(dest/'policy_audit.json', dict(status='PASS', checked=len(policy_checks), checks=policy_checks))


def main():
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['benchmark', 'run', 'report'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-id', type=int)
    args = parser.parse_args()
    cfg = checked_config()
    if args.mode == 'benchmark':
        benchmark(cfg, args.output)
    elif args.mode == 'report':
        report(cfg, args.output)
    else:
        proof = read(args.output/'benchmark/benchmark.json')
        if proof['status'] != 'PASS' or proof['identity'] != sha(ROOT/'manifest.json'):
            raise ValueError('Benchmark identity gate failed')
        run_task(cfg['tasks'][args.task_id], cfg, args.output)


if __name__ == '__main__':
    main()
