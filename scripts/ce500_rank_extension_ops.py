"""Measured, receipt-based bounded scheduler; no numerical work on login nodes."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import time


def read(p): return json.loads(p.read_text())


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix('.tmp')
    t.write_text(json.dumps(obj, indent=2) + '\n')
    t.replace(p)


def ledger(out, label):
    ids = [j for f in out.glob('submission-*.json') for j in read(f)['jobs'].values()]
    if not ids: return 0.
    txt = subprocess.check_output(['sacct', '-j', ','.join(ids), '-n', '-P',
        '--format=JobIDRaw,JobID,State,ElapsedRaw,AllocCPUS,AllocTRES'], text=True)
    rows = {}
    for line in txt.splitlines():
        c = line.split('|')
        if len(c) < 6 or not c[0] or '.' in c[1]: continue
        seconds, cpus = int(c[3] or 0), int(c[4] or 0)
        if cpus == 0:
            assert seconds == 0, line
            continue
        assert cpus == 1 and 'billing=1' in c[5], line
        rows[c[0]] = dict(job=c[1], state=c[2], seconds=seconds, allocated_cpus=cpus, tres=c[5])
    spent = sum(r['seconds'] / 3600 for r in rows.values())
    write(out / 'accounting' / (label + '.json'), dict(allocated_core_hours=spent, rows=list(rows.values())))
    return spent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('phase', choices=['preflight', 'pilot', 'formal'])
    p.add_argument('--manifest', type=Path, required=True)
    a = p.parse_args()
    cfg = read(a.manifest)
    out, resources = Path(cfg['output']), cfg['resources']
    release = a.manifest.resolve().parents[1]
    filename = 'submission-' + a.phase + '.json'
    assert not (out / filename).exists(), 'Inspect receipt; never replay uncertain submission'
    text = subprocess.check_output(['myproject'], text=True)
    out.mkdir(parents=True, exist_ok=True)
    (out / ('balance-' + a.phase + '.txt')).write_text(text)
    line = next(l for l in text.splitlines() if '|' + resources['account'] + '|' in l)
    balance = float(line.split('|')[6].strip())
    assert balance > resources['total_SU_cap']
    spent = ledger(out, 'before-' + a.phase)
    receipt = dict(filename=filename, jobs={}, status='planned', epoch=time.time(),
                   balance_available=balance, total_SU_cap=resources['total_SU_cap'])

    def submit(key, minutes, mode, phase=None, array=None, dependency=None):
        (out / 'logs').mkdir(exist_ok=True)
        cmd = ['sbatch', '--parsable', '-A', resources['account'], '-p', 'short', '-t', str(minutes),
               '--exclude=c136,c294', '-J', 'ce-rankext-' + key, '-o', str(out / 'logs' / (key + '-%A_%a.out'))]
        if array: cmd += ['--array=' + array]
        if dependency: cmd += ['--dependency=afterok:' + dependency]
        cmd += [str(release / 'slurm/ce500_rank_extension.sbatch'), mode]
        if phase: cmd += ['--phase', phase]
        receipt['pending_submission'] = dict(key=key, command=cmd)
        receipt['status'] = 'submitting'
        write(out / filename, receipt)
        job = subprocess.check_output(cmd, cwd=release, text=True).strip()
        assert job.isdigit()
        receipt['jobs'][key] = job
        receipt.pop('pending_submission')
        receipt['status'] = 'submitted'
        write(out / filename, receipt)
        return job

    if a.phase == 'preflight':
        job = submit('prepare', 20, 'prepare')
        submit('diagnose', 30, 'diagnose', dependency=job)
    elif a.phase == 'pilot':
        assert read(out / 'preflight.json')['status'] == 'PASS'
        receipt['requested_SU_bound'] = spent + 6 * 40 / 60 + 25 / 60 + 30 / 60
        assert receipt['requested_SU_bound'] < resources['total_SU_cap']
        job = submit('pilot', 40, 'task', 'pilot', array='0-5%6')
        submit('pilot_report', 25, 'report', 'pilot', dependency=job)
    else:
        assert read(out / 'report-pilot/summary.json')['status'] == 'complete'
        measured = []
        for rank in cfg['ranks']:
            seconds = max(read(out / 'raw' / f'ce-r{rank:03d}-s{s:04d}.json')['seconds_this_invocation'] for s in cfg['pilot_seeds'])
            wall = max(5, math.ceil((1.25 * seconds + 180) / 60))
            assert wall <= 45
            measured.append(dict(rank=rank, pilot_max_seconds=seconds, wall_minutes=wall))
        formal = 30 * sum(m['wall_minutes'] for m in measured) / 60
        bound = spent + formal + 6 * 25 / 60 + 25 / 60 + 5 + 30 / 60
        assert bound < resources['total_SU_cap'], bound
        plan = dict(budgets=cfg['budgets'], seeds=cfg['confirm_seeds'], targets=cfg['absolute_targets'],
                    measurements=measured, prior_allocated_core_hours=spent,
                    remaining_requested_SU_bound=formal + 6 * 25 / 60 + 25 / 60,
                    total_worst_case_SU_bound=bound, automatic_retries=0,
                    diagnostics_remaining_bound_SU=.5, manual_recovery_SU_reserve=5)
        write(out / 'formal_plan.json', plan)
        receipt['plan'] = plan
        jobs = [submit('r' + str(m['rank']), m['wall_minutes'], 'task', 'confirm',
                       array=f'{i*30}-{(i+1)*30-1}%4') for i, m in enumerate(measured)]
        job = submit('audits', 25, 'audit', 'confirm', array='0-5%6', dependency=':'.join(jobs))
        submit('report', 25, 'report', 'confirm', dependency=job)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__': main()
