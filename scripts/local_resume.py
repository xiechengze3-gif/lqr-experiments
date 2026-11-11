"""Run frozen CE/NPG releases locally without inventing Slurm identities.

Scientific source files and checkpoint identities stay unchanged. Local
authorization, adapter hash, versions and thread limits are recorded separately.
"""
import argparse
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

CAMPAIGNS = ('approx-tail-b16057241cf926bb', 'rank-multiseed-2a95058c9c562fd9')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def paths(root, campaign):
    release = root / 'releases' / campaign
    manifests = list((release / 'configs').glob('*.json'))
    name = 'rank_multiseed.json' if campaign.startswith('rank-') else 'approx_tail_suite.json'
    manifest = release / 'configs' / name
    if not manifest.exists():
        raise RuntimeError(f'Frozen manifest missing: {manifest}; candidates {manifests}')
    return release, manifest, root / 'results' / campaign


def inventory(root):
    pending, counts = [], []
    for campaign in CAMPAIGNS:
        _, manifest, output = paths(root, campaign)
        cfg = json.loads(manifest.read_text())
        for profile, setting in cfg['profiles'].items():
            completed = 0
            for index, task in enumerate(cfg['tasks']):
                final = output / profile / 'raw' / f'task-{index:03d}.json'
                if final.exists():
                    payload = json.loads(final.read_text())
                    assert payload['task'] == task
                    assert payload['manifest_sha256'] == digest(manifest)
                    completed += 1
                elif setting['algorithm'] in ('CE', 'NPG'):
                    workload = (max(setting['budgets']) if setting['algorithm'] == 'CE'
                                else sum(setting['schedule'])) * task['n'] ** 2
                    pending.append(dict(campaign=campaign, profile=profile, task_id=index,
                                        algorithm=setting['algorithm'], n=task['n'], workload=workload))
            counts.append(dict(campaign=campaign, profile=profile, algorithm=setting['algorithm'],
                               completed=completed, total=len(cfg['tasks']),
                               remaining=len(cfg['tasks'])-completed))
    # Finish smaller outstanding work first; preserve every declared task.
    pending.sort(key=lambda job: (job['workload'], job['campaign'], job['task_id']))
    return pending, counts


def setup(root, campaign):
    if os.environ.get('LQR_LOCAL_AUTHORIZED') != '1':
        raise RuntimeError('Explicit local execution flag required')
    release, manifest, output = paths(root, campaign)
    sys.path[:0] = [str(release / 'scripts'), str(root / 'releases' / '7f5c6de07fb244ab')]
    os.environ['LQR_TAIL_SYSTEM_CACHE'] = str(output / 'systems')
    os.environ['LQR_TAIL_BUILD_CACHE'] = '0'
    engine = importlib.import_module('dense_scaling')
    engine.require_compute = lambda: None  # User explicitly authorized local execution.
    original_json = engine.atomic_json
    import numpy
    import scipy
    import numba
    execution = dict(location='local', host=platform.node(), python=platform.python_version(),
                     numpy=numpy.__version__, scipy=scipy.__version__, numba=numba.__version__,
                     blas_threads=1, adapter_sha256=digest(__file__),
                     frozen_scientific_sources_unmodified=True)

    def local_json(path, value):
        if isinstance(value, dict):
            value = dict(value, execution_provenance=execution)
        original_json(path, value)

    engine.atomic_json = local_json
    runner = importlib.import_module('rank_multiseed_run' if campaign.startswith('rank-')
                                    else 'approx_tail_run')
    original = importlib.import_module('approx_tail_run')

    def provenance(module):
        def result(manifest_path):
            return dict(manifest_sha256=digest(manifest_path), source_sha256=digest(module.__file__),
                        system_sha256=digest(module.system.__code__.co_filename),
                        lstd_sha256=digest(module.solve.__code__.co_filename),
                        collector_sha256=digest(module.collect.__code__.co_filename),
                        engine_sha256=digest(module.evaluate.__code__.co_filename), slurm_job_id=None)
        return result

    runner.provenance = provenance(runner)
    original.provenance = provenance(original)
    return runner, manifest, output


def worker(args):
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        runner, manifest, output = setup(args.root, args.campaign)
        if args.mode == 'validate':
            if not args.campaign.startswith('rank-'):
                raise RuntimeError('Use rank campaign for the frozen cross-runner validation')
            root = args.root / 'local-validation'
            root.mkdir(exist_ok=True)
            cfg = json.loads(manifest.read_text())
            cfg['tasks'] = [dict(id=-1, n=6, m=6, r=2, system_seed=0, trial_seed=0,
                                tail_mode='exact', level=0., cell='resume-audit', families=['audit'])]
            cfg['profiles'] = {'npg-audit': dict(algorithm='NPG', schedule=[4096]*4),
                               'ce-audit': dict(algorithm='CE', budgets=[512, 1024])}
            cfg['burn'] = 64
            audit_manifest = root / 'audit_manifest.json'
            save(audit_manifest, cfg)
            checks = []
            for profile in cfg['profiles']:
                assert runner.run(audit_manifest, profile, 0, root / 'whole')
                finished = False
                for _ in range(20):
                    finished = runner.run(audit_manifest, profile, 0, root / 'resumed', stop_after=1)
                    if finished:
                        break
                assert finished
                runner.original.run(audit_manifest, profile, 0, root / 'original')
                records = [json.loads((root / variant / profile / 'raw/task-000.json').read_text())['records']
                           for variant in ('whole', 'resumed', 'original')]
                assert records[0] == records[1] == records[2], profile
                checks.append(dict(profile=profile, exact_resume=True, frozen_runner_equivalence=True))
            save(root / 'resume_audit.json', dict(status='PASS', checks=checks,
                                                adapter_sha256=digest(__file__)))
            print(json.dumps(dict(status='PASS', checks=checks)), flush=True)
        else:
            setting = json.loads(manifest.read_text())['profiles'][args.profile]
            if setting['algorithm'] not in ('CE', 'NPG'):
                raise RuntimeError('LSPI is held for a separate Grace resource validation')
            final = output / args.profile / 'raw' / f'task-{args.task_id:03d}.json'
            if not final.exists():
                runner.run(manifest, args.profile, args.task_id, output)


def supervise(args):
    proof = args.root / 'local-validation' / 'resume_audit.json'
    validation = json.loads(proof.read_text())
    assert validation['status'] == 'PASS', 'Validation must pass before production'
    assert validation['adapter_sha256'] == digest(__file__), 'Adapter changed since validation'
    # Windows file locking prevents a second supervisor from duplicating work.
    import msvcrt
    lock = (args.root / 'local-supervisor.lock').open('a+b')
    lock.seek(0)
    if not lock.read(1):
        lock.write(b'1')
        lock.flush()
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    queue, counts = inventory(args.root)
    logs = args.root / 'local-logs'
    logs.mkdir(exist_ok=True)
    active, done, failed = [], [], []
    initial = len(queue)
    environment = dict(os.environ, LQR_LOCAL_AUTHORIZED='1', PYTHONUTF8='1',
                       PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                       MKL_NUM_THREADS='1', NUMBA_NUM_THREADS='1')
    save(args.root / 'local-inventory.json', dict(counts=counts, pending_local=initial,
         lspi_location='held_for_Grace_CPU_and_memory_validation', workers=args.workers, threads_each=1))
    while queue or active:
        while queue and len(active) < args.workers:
            job = queue.pop(0)
            log = logs / f"{job['campaign']}-{job['profile']}-{job['task_id']:03d}.log"
            stream = log.open('ab')
            command = [sys.executable, '-B', str(Path(__file__).resolve()), 'worker',
                       '--root', str(args.root), '--campaign', job['campaign'],
                       '--profile', job['profile'], '--task-id', str(job['task_id'])]
            process = subprocess.Popen(command, env=environment, stdout=stream, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            active.append((job, process, stream, str(log), time.time()))
        running = []
        for job, process, stream, log, started in active:
            code = process.poll()
            if code is None:
                running.append((job, process, stream, log, started))
            else:
                stream.close()
                record = dict(job, exit_code=code, log=log, seconds=time.time()-started)
                (done if code == 0 else failed).append(record)
        active = running
        save(args.root / 'local-status.json', dict(state='running' if active or queue else
             ('needs_attention' if failed else 'local_CE_NPG_complete'), supervisor_pid=os.getpid(),
             updated_unix=time.time(), initial_pending=initial, waiting=len(queue),
             active=[dict(job, pid=process.pid, log=log, started_unix=started)
                     for job, process, _, log, started in active], completed=done, failed=failed,
             lspi='not_submitted; validate_total_SU_before_Grace_submission'))
        if active:
            time.sleep(5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['inventory', 'validate', 'worker', 'supervise'])
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--campaign', choices=CAMPAIGNS, default=CAMPAIGNS[1])
    parser.add_argument('--profile')
    parser.add_argument('--task-id', type=int, default=0)
    parser.add_argument('--workers', type=int, choices=[1, 2], default=2)
    arguments = parser.parse_args()
    if arguments.mode == 'inventory':
        jobs, coverage = inventory(arguments.root)
        print(json.dumps(dict(coverage=coverage, pending_local=len(jobs)), indent=2))
    elif arguments.mode == 'supervise':
        supervise(arguments)
    else:
        worker(arguments)
