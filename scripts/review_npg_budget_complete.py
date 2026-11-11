"""Supplementary completion audit on Grace; preserves frozen experiment outputs."""
import argparse
import csv
import hashlib
import json
import os
import socket
from collections import defaultdict
from pathlib import Path


def main():
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Numerical review requires a real Slurm compute allocation')
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    root, out = Path(a.input), Path(a.output)
    summary = json.loads((root / 'summary.json').read_text())
    audit = json.loads((root / 'numerical_audit.json').read_text())
    assert summary['status'] == 'complete' and audit['status'] == 'PASS'
    assert not summary['missing_tasks'] and summary['complete_tasks'] == 336
    with (root / 'endpoints_per_run.csv').open(newline='') as f:
        endpoints = list(csv.DictReader(f))
    assert len(endpoints) == 672
    groups = defaultdict(lambda: dict(trajectories=0, stable=0, unstable=0,
                                    actual_transitions=0, planned_transitions=0))
    pairs = defaultdict(dict)
    for row in endpoints:
        assert row['stable'] in ('True', 'False')
        key = (int(row['r']), int(row['minimum_batch']), row['method'])
        g = groups[key]
        g['trajectories'] += 1
        g['stable' if row['stable'] == 'True' else 'unstable'] += 1
        g['actual_transitions'] += int(row['actual_transitions'])
        g['planned_transitions'] += int(row['planned_transitions'])
        pairs[int(row['task_id'])][row['method']] = row
    full_rank_endpoint_max_abs_gap_difference = 0.
    for arms in pairs.values():
        assert set(arms) == {'raw', 'truncated'}
        assert arms['raw']['planned_transitions'] == arms['truncated']['planned_transitions']
        if int(arms['raw']['r']) == 50:
            assert arms['raw']['stable'] == arms['truncated']['stable']
            assert arms['raw']['actual_transitions'] == arms['truncated']['actual_transitions']
            if arms['raw']['stable'] == 'True':
                difference = abs(float(arms['raw']['gap']) - float(arms['truncated']['gap']))
                assert difference < 1e-8 * (1 + abs(float(arms['raw']['gap'])))
                full_rank_endpoint_max_abs_gap_difference = max(
                    full_rank_endpoint_max_abs_gap_difference, difference)
    # Stream every recorded stage to check the full-rank equivalence control.
    full_rank_stages = defaultdict(dict)
    with (root / 'records.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            if int(row['r']) == 50:
                full_rank_stages[int(row['task_id']), int(row['stage'])][row['method']] = row
    max_stage_gap_difference = 0.
    for arms in full_rank_stages.values():
        assert set(arms) == {'raw', 'truncated'}
        raw, trunc = arms['raw'], arms['truncated']
        for field in ('stable', 'observed', 'transitions'):
            assert raw[field] == trunc[field], (field, raw['task_id'], raw['stage'])
        if raw['stable'] == 'True' and raw['gap']:
            difference = abs(float(raw['gap']) - float(trunc['gap']))
            assert difference < 1e-8 * (1 + abs(float(raw['gap'])))
            max_stage_gap_difference = max(max_stage_gap_difference, difference)
    assert len(full_rank_stages) == 48 * 257
    reference = summary['exact_reference_endpoints']
    parent_jobs = []
    for line in (root / 'slurm_audit.txt').read_text().splitlines():
        fields = line.split('|')
        if len(fields) < 4:
            continue
        job = fields[0]
        if job.startswith(('20060805_', '20060802_')) and '.' not in job:
            assert fields[1] == 'COMPLETED' and fields[3] == '0:0', fields
            parent_jobs.append(job)
    assert len(set(parent_jobs)) == 336
    actual = sum(g['actual_transitions'] for g in groups.values())
    planned = sum(g['planned_transitions'] for g in groups.values())
    stable = sum(g['stable'] for g in groups.values())
    assert planned == 269176406016 and stable == summary['stable_methods']
    result = dict(
        status='PASS', job_id=os.environ['SLURM_JOB_ID'], host=socket.gethostname(),
        computation='Grace Slurm compute node',
        input_sha256={name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in ('summary.json', 'numerical_audit.json', 'endpoints_per_run.csv',
                                   'records.csv', 'slurm_audit.txt')},
        trajectories=len(endpoints), stable=stable, unstable=len(endpoints)-stable,
        completed_parent_array_tasks=len(set(parent_jobs)),
        campaign_actual_transitions=actual, campaign_planned_transitions=planned,
        campaign_cost_scope='Current release production plus its two smoke tasks once; excludes '
                            'superseded pilot, verification and unsampled exact references.',
        by_rank_floor_method=[dict(r=k[0], minimum_batch=k[1], method=k[2], **v)
                             for k, v in sorted(groups.items())],
        full_rank_equivalence=dict(status='PASS', paired_stage_checks=len(full_rank_stages),
            maximum_stable_endpoint_gap_difference=full_rank_endpoint_max_abs_gap_difference,
            maximum_stable_stage_gap_difference=max_stage_gap_difference),
        maximum_reference_endpoint_gap=max(float(row['gap']) for row in reference),
        caveat='No new simulations, fits, success rules or changes to the frozen primary report.')
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'completion_review.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
