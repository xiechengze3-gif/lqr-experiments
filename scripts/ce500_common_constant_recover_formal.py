"""Bounded scheduling recovery; reuse the frozen numerical release unchanged.

Run with --submit only after reviewing the plan. Standard library only: safe on
the Grace login node. A partial/uncertain submission must be inspected manually.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import time


RELEASE = Path('/scratch/user/changze/lqr_experiments/releases/ce500-common-constants-20261022')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--submit', action='store_true')
    args = parser.parse_args()
    manifest = RELEASE / 'configs/ce500_common_constants_20261022.json'
    cfg = json.loads(manifest.read_text())
    out = Path(cfg['output'])
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=RELEASE, check=True)
    spec = importlib.util.spec_from_file_location('frozen_ops', RELEASE / 'scripts/ce500_common_constant_ops.py')
    ops = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ops)
    assert not (out / 'submission-formal.json').exists(), 'Inspect receipt; do not replay submission'
    assert cfg['resources']['total_SU_cap'] == 100
    assert cfg['resources']['automatic_retries'] == 0
    report = ops.read(out / 'report-pilot/summary.json')
    audit = ops.read(out / 'audit-shards/pilot-00.json')
    assert report['status'] == 'complete' and audit['status'] == 'PASS'
    assert audit['identity'] == report['identity']
    assert audit['unique_policies'] == 198 and audit['OLS_fits'] == 10
    available = ops.balance(cfg, 'formal-recovery-20261023')
    spent = ops.ledger(cfg, 'before-formal-recovery-20261023')
    measurements = []
    for rank in cfg['ranks']:
        data = [ops.read(out / 'raw' / f'ce-r{rank:03d}-s{seed:04d}.json') for seed in cfg['pilot_seeds']]
        assert all(x['identity'] == report['identity'] and x['budgets'] == cfg['budgets'] for x in data)
        seconds = max(x['seconds_this_invocation'] for x in data)
        wall = max(5, math.ceil((1.25 * seconds + 180) / 60))
        assert wall <= 40
        measurements.append(dict(rank=rank, pilot_max_seconds=seconds, wall_minutes=wall))
    formal = len(cfg['confirm_seeds']) * sum(x['wall_minutes'] for x in measurements) / 60
    bound = (spent + formal + cfg['resources']['audit_shards'] * cfg['resources']['audit_wall_minutes'] / 60
             + cfg['resources']['report_wall_minutes'] / 60 + cfg['resources']['manual_recovery_SU_reserve'])
    assert bound < cfg['resources']['total_SU_cap'], bound
    sidecar_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    plan = dict(status='frozen_before_formal_sampling', budgets=cfg['budgets'], seeds=cfg['confirm_seeds'],
                absolute_targets=cfg['absolute_targets'], primary_absolute_target=cfg['primary_absolute_target'],
                supplied_common_bounds=cfg['supplied_common_bounds'], numerical_identity=report['identity'],
                resource_measurements=measurements, prior_allocated_core_hours=spent,
                formal_requested_SU_bound=formal, total_worst_case_SU_bound=bound,
                science_grid_frozen_before_pilot=True, automatic_retries=0,
                operational_override=dict(reason='Old 35-minute guard blocked formal before any submission',
                                          original_maximum_minutes=35, actual_maximum_minutes=max(x['wall_minutes'] for x in measurements),
                                          wall_formula='ceil((1.25 * slowest measured pilot seconds + 180) / 60)',
                                          frozen_release_unchanged=True, sidecar_sha256=sidecar_sha))
    print(json.dumps(plan, indent=2))
    if not args.submit:
        return
    receipt = dict(filename='submission-formal.json', jobs={}, epoch=time.time(), balance_available=available,
                   total_SU_cap=cfg['resources']['total_SU_cap'], plan=plan)
    ops.write(out / 'formal_plan.json', plan)

    def submit(key, wall, mode, jobargs, dependency=None, array=None):
        receipt['pending_submission'] = dict(key=key, mode=mode, array=array, dependency=dependency)
        job = ops.submit(cfg, RELEASE, receipt, key, wall, mode, jobargs, dependency=dependency, array=array)
        receipt.pop('pending_submission')
        ops.write(out / receipt['filename'], receipt)
        return job

    jobs = []
    size = len(cfg['confirm_seeds'])
    for i, measurement in enumerate(measurements):
        jobs.append(submit('r' + str(measurement['rank']), measurement['wall_minutes'], 'task',
                           ['--phase', 'confirm'], array=f'{i*size}-{(i+1)*size-1}%4'))
    job = submit('audits', cfg['resources']['audit_wall_minutes'], 'audit', ['--phase', 'confirm'],
                 dependency=':'.join(jobs), array='0-5%6')
    submit('report', cfg['resources']['report_wall_minutes'], 'report', ['--phase', 'confirm'], dependency=job)
    ops.ledger(cfg, 'after-formal-recovery-20261023')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
