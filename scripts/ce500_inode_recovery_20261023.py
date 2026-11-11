"""One bounded recovery of missing formal tasks after the inode failure.

Numerical releases/configurations/seeds/budgets remain unchanged. Only missing
task receipts are scheduled. Valid complete results and committed checkpoints
are reused by the frozen engine. A missing final OLS artifact is reconstructed
from the committed sufficient statistics on a compute node before resuming.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/scratch/user/changze/lqr_experiments')
PYTHON = '/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python'
GROUPS = {
    'original': ('ce500-common-constants-20261022', 'ce500_common_constants_20261022.json',
                 'ce500_common_constants', 37, 20, 100),
    'extension': ('ce500-common-rank-extension-20261023-v2', 'ce500_rank_extension_20261023.json',
                  'ce500_rank_extension', 45, 25, 85),
}
SIDE = BASE / 'releases/ce500-inode-recovery-20261023.py'
BATCH = BASE / 'releases/ce500-inode-recovery-20261023.sbatch'


def read(p):
    return json.loads(p.read_text())


def write(p, value):
    temp = p.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(p)


def details(group):
    name, manifest, module, taskwall, reportwall, cap = GROUPS[group]
    release, out = BASE / 'releases' / name, BASE / 'results' / name
    cfg = read(release / 'configs' / manifest)
    return release, out, cfg, module, taskwall, reportwall, cap


def accounted(roots, additional=()):
    ids = set(additional)
    for root in roots:
        for p in root.glob('submission*.json'):
            ids.update(read(p).get('jobs', {}).values())
    txt = subprocess.check_output(['sacct', '-j', ','.join(sorted(ids)), '-n', '-P',
                                   '--format=JobIDRaw,JobID,State,ElapsedRaw,AllocCPUS,AllocTRES'], text=True)
    rows = {}
    for line in txt.splitlines():
        c = line.split('|')
        if len(c) < 6 or '.' in c[1]:
            continue
        seconds, cpus = int(c[3] or 0), int(c[4] or 0)
        if cpus == 0:
            assert seconds == 0
            continue
        assert cpus == 1 and 'billing=1' in c[5], line
        rows[c[0]] = dict(job=c[1], state=c[2], seconds=seconds, cpus=cpus, tres=c[5])
    return sum(r['seconds'] / 3600 for r in rows.values()), list(rows.values())


def missing(out, cfg):
    wanted = []
    for i, rank in enumerate(cfg['ranks']):
        ids = []
        for j, seed in enumerate(cfg['confirm_seeds']):
            idx = i * len(cfg['confirm_seeds']) + j
            receipt = out / 'task_receipts' / f'confirm-{idx:03d}.json'
            if receipt.exists():
                d = read(receipt)
                assert d['rank'] == rank and d['seed'] == seed and d['phase'] == 'confirm'
            else:
                ids.append(idx)
        wanted.append(dict(rank=rank, task_ids=ids))
    return wanted


def plan_submit(do_submit):
    archive_root = BASE / 'results/ce500-common-constants-20261022'
    archive = read(archive_root / 'inode_archive_submission_20261023.json')
    state = subprocess.check_output(['sacct', '-j', archive['job'], '-n', '-P', '--format=JobID,State'], text=True)
    assert archive['job'] + '|COMPLETED' in state, state
    for name in ['ce500-matched-gap-20261019', 'ce500-random-a-20261020', 'ce-matched-initial-gap-20261018']:
        assert read(BASE / 'results' / name / 'INODE_ARCHIVE_20261023.json')['status'] == 'PASS'
    stat = os.statvfs(BASE)
    assert stat.f_favail >= 3200 and stat.f_bavail * stat.f_frsize > 15 * 1024**3, (stat.f_favail, stat.f_bavail)
    balance = subprocess.check_output(['myproject'], text=True)
    line = next(s for s in balance.splitlines() if '|132685389143|' in s)
    available = float(line.split('|')[6].strip())
    assert available > 185
    active = subprocess.check_output(['squeue', '-u', 'changze', '-h', '-o', '%j'], text=True)
    assert 'ce-inode-' not in active and 'ce-rankext-' not in active
    plans = {}
    for group in GROUPS:
        release, out, cfg, module, wall, reportwall, cap = details(group)
        assert not (out / 'submission-inode-recovery-20261023.json').exists(), 'Inspect journal before replay'
        subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=release, check=True, stdout=subprocess.DEVNULL)
        wanted = missing(out, cfg)
        n = sum(len(w['task_ids']) for w in wanted)
        roots = [out]
        extra = []
        if group == 'extension':
            roots.append(BASE / 'results/ce500-r300-fine-20261023-v1')
        else:
            extra.append(archive['job'])
        spent, rows = accounted(roots, extra)
        future = n * wall / 60 + 6 * 25 / 60 + reportwall / 60
        bound = spent + future
        assert bound < cap, (group, bound, cap)
        plans[group] = dict(status='planned', missing=wanted, missing_tasks=n,
                           prior_actual_SU=spent, remaining_requested_SU_bound=future,
                           total_worst_case_SU_bound=bound, cap_SU=cap,
                           task_wall_minutes=wall, report_wall_minutes=reportwall,
                           seeds=cfg['confirm_seeds'], budgets=cfg['budgets'],
                           frozen_numerical_release_unchanged=True, recovery_attempts_per_missing_task=1,
                           preserves_all_completed_results=True, independent_audit_shards=6,
                           actual_accounting=rows)
    print(json.dumps({g: {k: v for k, v in p.items() if k != 'actual_accounting'} for g, p in plans.items()}), flush=True)
    if not do_submit:
        return
    for group, plan in plans.items():
        release, out, cfg, module, wall, reportwall, cap = details(group)
        path = out / 'submission-inode-recovery-20261023.json'
        receipt = dict(status='submitting', jobs={}, plan=plan, epoch=time.time(),
                       sidecar_sha256=hashlib.sha256(SIDE.read_bytes()).hexdigest(), balance_available=available)
        write(path, receipt)

        def submit(key, mode, minutes, array=None, deps=None):
            cmd = ['sbatch', '--parsable', '-A', '132685389143', '-p', 'short', '-t', str(minutes),
                   '--exclude=c136,c294', '-J', 'ce-inode-' + group + '-' + key,
                   '-o', str(out / 'logs' / ('inode-' + key + '-%A_%a.out'))]
            if array:
                cmd += ['--array=' + array]
            if deps:
                cmd += ['--dependency=afterok:' + ':'.join(deps)]
            cmd += [str(BATCH), group, mode]
            receipt['pending_submission'] = dict(key=key, command=cmd)
            write(path, receipt)
            job = subprocess.check_output(cmd, text=True).strip()
            assert job.isdigit(), job
            receipt['jobs'][key] = job
            receipt.pop('pending_submission')
            write(path, receipt)
            return job

        tasks = []
        for want in plan['missing']:
            if want['task_ids']:
                tasks.append(submit('r' + str(want['rank']), 'task', wall,
                                    ','.join(map(str, want['task_ids'])) + '%4'))
        audit = submit('audits', 'audit', 25, '0-5%6', tasks or None)
        submit('report', 'report', reportwall, deps=[audit])
        receipt['status'] = 'submitted'
        write(path, receipt)
        print(json.dumps(dict(group=group, status='submitted', jobs=receipt['jobs'])), flush=True)


def compute(group, mode, index):
    assert os.environ.get('SLURM_JOB_ID')
    release, out, cfg, module, wall, reportwall, cap = details(group)
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=release, check=True, stdout=subprocess.DEVNULL)
    sys.path[:0] = [str(release), str(release / 'scripts')]
    os.environ['LQR_NUMBA_SITE'] = '/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages'
    for key, value in [('TMPDIR', cfg['temp']), ('XDG_CACHE_HOME', cfg['cache']),
                       ('NUMBA_CACHE_DIR', cfg['cache'] + '/numba'), ('MPLCONFIGDIR', cfg['cache'] + '/matplotlib')]:
        os.environ[key] = value
        Path(value).mkdir(parents=True, exist_ok=True)
    backend = importlib.import_module(module)
    core = backend if group == 'original' else backend.core
    ident = backend.identity(cfg)
    assert core.e.read(out / 'preflight.json')['identity'] == ident
    with core.threadpool_limits(1):
        if mode == 'task':
            rank = cfg['ranks'][index // len(cfg['confirm_seeds'])]
            seed = cfg['confirm_seeds'][index % len(cfg['confirm_seeds'])]
            stem = f'ce-r{rank:03d}-s{seed:04d}'
            estimate = out / 'estimates' / (stem + '.npz')
            cp = out / 'checkpoints' / (stem + '.npz')
            if not estimate.exists() and cp.exists():
                import numpy as np
                with np.load(cp, allow_pickle=False) as data:
                    meta = json.loads(str(data['meta']))
                    assert meta['identity'] == ident
                    if meta['done'] == max(cfg['budgets']):
                        theta = core.engine.cho_solve(core.engine.cho_factor((data['gram'] + data['gram'].T) / 2), data['cross'].T).T
                        core.e.save_npz(estimate, Ahat=theta[:, :cfg['n']], Bhat=theta[:, cfg['n']:])
                        print(json.dumps(dict(restored_final_OLS_artifact=True, rank=rank, seed=seed)), flush=True)
            core.task(cfg, ident, 'confirm', index)
        elif mode == 'audit':
            core.audit(cfg, ident, 'confirm', index)
        else:
            backend.report(cfg, ident, 'confirm')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['plan', 'submit', 'task', 'audit', 'report'])
    p.add_argument('--group', choices=GROUPS)
    p.add_argument('--index', type=int, default=0)
    a = p.parse_args()
    if a.mode in ['plan', 'submit']:
        plan_submit(a.mode == 'submit')
    else:
        compute(a.group, a.mode, a.index)


if __name__ == '__main__':
    main()
