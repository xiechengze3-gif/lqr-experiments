"""Ten-system rank/precision study; unchanged estimators, resumable NPG stages."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
from dense_scaling import require_compute, atomic_json, ce, evaluate, targets, trunc, pi_gain, rng_for
from approx_tail_system import system, ETA
from full_lstd import solve
from pi_ce_rank import data
from npg_batched_collector import collect
import approx_tail_run as original


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance(manifest):
    return dict(manifest_sha256=sha(manifest), source_sha256=sha(__file__),
        system_sha256=sha(system.__code__.co_filename), lstd_sha256=sha(solve.__code__.co_filename),
        collector_sha256=sha(collect.__code__.co_filename), engine_sha256=sha(evaluate.__code__.co_filename),
        slurm_job_id=os.environ['SLURM_JOB_ID'])


def checkpoint(path, k, x, records, method_index, stage, total, identity):
    temporary = path.with_suffix('.new.npz')
    with temporary.open('wb') as stream:
        np.savez(stream, k=k, x=x, records=json.dumps(records), method_index=method_index,
                 stage=stage, total=total, identity=json.dumps(identity, sort_keys=True))
    os.replace(temporary, path)


def run(manifest, profile, task_id, output, deadline=None, stop_after=None):
    cfg = json.loads(Path(manifest).read_text())
    task, setting = cfg['tasks'][task_id], cfg['profiles'][profile]
    out = Path(output) / profile / 'raw'
    out.mkdir(parents=True, exist_ok=True)
    final = out / f'task-{task_id:03d}.json'
    identity = dict(manifest_sha256=sha(manifest), source_sha256=sha(__file__), task=task, profile=profile)
    if setting['algorithm'] == 'LSPI':
        # A critic implementation change invalidates the entire LSPI trajectory.
        identity['lstd_sha256'] = sha(solve.__code__.co_filename)
    if final.exists():
        existing = json.loads(final.read_text())
        assert existing['task'] == task and existing['manifest_sha256'] == identity['manifest_sha256']
        assert existing['source_sha256'] == identity['source_sha256']
        if setting['algorithm'] == 'LSPI':
            assert existing['lstd_sha256'] == identity['lstd_sha256']
        return True
    s, begin = system(task), time.monotonic()
    algorithm, records = setting['algorithm'], []
    payload = dict(task=task, profile=profile, algorithm=algorithm, diagnostics=s['diagnostics'], **provenance(manifest))
    if algorithm == 'CE':
        records, _ = ce(dict(task, budgets=setting['budgets'], sigma=1.), s)
    else:
        saved = out / f'checkpoint-{task_id:03d}.npz'
        resume = None
        if saved.exists():
            with np.load(saved, allow_pickle=False) as blob:
                assert json.loads(str(blob['identity'])) == identity
                resume = dict(k=blob['k'].copy(), x=blob['x'].copy(),
                    method_index=int(blob['method_index']), stage=int(blob['stage']), total=int(blob['total']))
                records = json.loads(str(blob['records']))
        schedule, stages_this_call = setting['schedule'], 0
        for method_index, method in enumerate(('raw', 'truncated')):
            if resume is not None and method_index < resume['method_index']:
                continue
            if resume is not None and method_index == resume['method_index']:
                k, x, total, first_stage = resume['k'], resume['x'], resume['total'], resume['stage']
                last = next((row for row in reversed(records) if row['method']==method), None)
                if last is not None and not last['stable']:
                    first_stage = len(schedule)
            else:
                k, x, total, first_stage = s['K0'].copy(), np.zeros(task['n']), 0, 0
                quality, _ = evaluate(s, k)
                records.append(dict(method=method, stage=0, N=0, transitions=0, observed=True, **quality))
            for stage in range(first_stage, len(schedule)):
                if deadline is not None and time.monotonic() >= deadline:
                    checkpoint(saved, k, x, records, method_index, stage, total, identity)
                    return False
                count = schedule[stage]
                row = dict(method=method, stage=stage+1, N=count, observed=True)
                if algorithm == 'LSPI':
                    x, z, nxt, costs = data(s, k, x, count, cfg['burn'],
                        rng_for(202610082, task['n'], task['system_seed'], stage))
                    total += count + cfg['burn']
                    h, diagnostics = solve(z, nxt, costs, rtol=cfg['solver_rtol'], restart=40, maxiter=10)
                    del z, nxt, costs
                    row['solver'] = diagnostics
                    if not diagnostics['converged']:
                        row.update(transitions=total, stable=False, gap=None, failure='LSTD_solver_failure')
                        records.append(row)
                        break
                    n = task['n']
                    g, c = h[n:, n:] - s['R'], h[n:, :n]
                    truth = targets(s, k, cfg['horizon'])
                    row['joint_error_fro2'] = float(np.sum((g-truth['G'])**2) + np.sum((c-truth['C'])**2))
                    candidate, _, _ = pi_gain(s, g, c, None if method == 'raw' else task['r'])
                elif algorithm == 'NPG':
                    truth = targets(s, k, cfg['horizon'])
                    _, x, raw, _, gram, used = next(collect(s, k, x, [count], cfg['horizon'], 1.,
                        rng_for(202610083, task['n'], task['system_seed'], stage), burn=cfg['burn']))
                    total += used
                    zhat = raw if method == 'raw' else trunc(raw, task['r'])
                    row.update(eta=ETA, critic_error_fro2=float(np.sum((zhat-truth['Z'])**2)),
                        horizon_bias_fro2=float(np.sum((truth['ZH']-truth['Z'])**2)),
                        gram_condition=float(np.linalg.cond(gram)))
                    candidate = k - ETA * (s['R'] @ k + zhat)
                else:
                    raise ValueError(algorithm)
                quality, _ = evaluate(s, candidate)
                row.update(transitions=total, **quality)
                records.append(row)
                k = candidate
                checkpoint(saved, k, x, records, method_index, stage+1, total, identity)
                atomic_json(out / f'progress-{task_id:03d}.json', dict(payload, records=records))
                if stage % 16 == 15 or algorithm == 'LSPI' or not quality['stable']:
                    print(json.dumps(dict(task_id=task_id, profile=profile, **row)), flush=True)
                stages_this_call += 1
                if not quality['stable']:
                    break
                if stop_after is not None and stages_this_call >= stop_after:
                    return False
            # A failed arm is retained and never resumed as a successful arm.
            checkpoint(saved, s['K0'], np.zeros(task['n']), records, method_index+1, 0, 0, identity)
    atomic_json(final, dict(payload, records=records, seconds_last_segment=time.monotonic()-begin,
                           resumable=True, stability_termination_uses_true_model=algorithm!='CE'))
    return True


def verify_resume(manifest, output):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(Path(manifest).read_text())
    cfg['tasks'] = [dict(id=-1, n=6, m=6, r=2, system_seed=0, trial_seed=0,
                         tail_mode='exact', level=0., cell='resume-audit', families=['audit'])]
    cfg['profiles'] = {'npg-audit': dict(algorithm='NPG', schedule=[4096]*4),
                       'lspi-audit': dict(algorithm='LSPI', schedule=[4096]*2),
                       'ce-audit': dict(algorithm='CE', budgets=[512, 1024])}
    cfg['burn'] = 64
    audit_manifest = root / 'audit_manifest.json'
    atomic_json(audit_manifest, cfg)
    checks = []
    for profile in cfg['profiles']:
        assert run(audit_manifest, profile, 0, root/'whole')
        if profile.startswith('ce'):
            assert run(audit_manifest, profile, 0, root/'resumed')
        else:
            finished = False
            for _ in range(20):
                finished = run(audit_manifest, profile, 0, root/'resumed', stop_after=1)
                if finished:
                    break
            assert finished
        whole = json.loads((root/'whole'/profile/'raw/task-000.json').read_text())
        resumed = json.loads((root/'resumed'/profile/'raw/task-000.json').read_text())
        # Runtime diagnostics are not part of the mathematical trajectory.
        for payload in (whole, resumed):
            for row in payload['records']:
                row.get('solver', {}).pop('seconds', None)
        assert whole['records'] == resumed['records'], ('Resume changed observations or policy', profile)
        original.run(audit_manifest, profile, 0, root/'original')
        prior = json.loads((root/'original'/profile/'raw/task-000.json').read_text())
        for row in prior['records']:
            row.get('solver', {}).pop('seconds', None)
        assert whole['records'] == prior['records'], ('New runner differs from frozen estimator', profile)
        checks.append(dict(profile=profile, exact_resume_records=True, original_runner_records=True))
    atomic_json(root/'resume_audit.json', dict(status='PASS', checks=checks, source_sha256=sha(__file__)))
    print(json.dumps(dict(resume_audit='PASS', checks=checks)), flush=True)


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['run', 'verify', 'reference', 'resume-audit'])
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--profile')
    parser.add_argument('--task-id', type=int, default=0)
    parser.add_argument('--minutes', type=float)
    args = parser.parse_args()
    if args.mode == 'verify':
        original.verify(args.manifest, args.output)
    elif args.mode == 'reference':
        original.reference(args.manifest, args.task_id, args.output)
    elif args.mode == 'resume-audit':
        verify_resume(args.manifest, Path(args.output)/'resume-audit')
    else:
        deadline = None if args.minutes is None else time.monotonic()+60*args.minutes
        if not run(args.manifest, args.profile, args.task_id, args.output, deadline):
            raise SystemExit(85)
