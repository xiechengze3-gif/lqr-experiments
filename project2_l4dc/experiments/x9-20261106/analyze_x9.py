"""Frozen saved-record report; no new trajectories, truth only for evaluation."""
import csv
import json
import math
import os
from pathlib import Path
import numpy as np
import frozen_engine as e
import x9_core as core


def q(values, p):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered)-1)*p
    lo, hi = math.floor(position), math.ceil(position)
    if lo == hi or ordered[lo] == ordered[hi]:
        return ordered[lo]
    if math.isinf(ordered[hi]):
        return ordered[hi]
    return ordered[lo] + (position-lo)*(ordered[hi]-ordered[lo])


def paired_ratio(d, t):
    if math.isinf(d) and math.isinf(t):
        return None
    if t == 0:
        return 1. if d == 0 else math.inf
    return d/t


def cross(N, y, target):
    """Same arithmetic as figs/make_figs.py cross, with no curve smoothing."""
    N, y = np.asarray(N, float), np.asarray(y, float)
    if np.isfinite(y[0]) and y[0] <= target:
        return -N[0]
    for i in range(1, len(y)):
        if np.isfinite(y[i-1]) and y[i-1] > target >= y[i]:
            t = (np.log(target)-np.log(y[i-1]))/(np.log(y[i])-np.log(y[i-1]))
            return float(np.exp(np.log(N[i-1])+t*(np.log(N[i])-np.log(N[i-1]))))
    return np.nan


def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields=None):
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def saved_endpoints(config_path, config):
    endpoints = []
    for r in read_csv(core.ROOT/'baseline/endpoints.csv'):
        if float(r['n']) != 24:
            continue
        item = {}
        for key, value in r.items():
            if value == '':
                item[key] = None
            elif value in ['True', 'False']:
                item[key] = value == 'True'
            else:
                try:
                    item[key] = float(value)
                except ValueError:
                    item[key] = value
        item.update(alpha=0., tau2_sq=0., origin='REUSED_X6b_FULL_CELL')
        endpoints.append(item)
    assert len(endpoints) == 512
    stages = []
    for group in config['formal_groups']:
        for index in range(32):
            folder = core.OUT/'formal-v1'/group['id']/f'task-{index}'
            done = json.loads((folder/'DONE.json').read_text())
            assert done['status'] == 'COMPLETE'
            assert done['config_sha256'] == e.sha(config_path)
            assert done['source_sha256'] == e.sha(core.__file__)
            assert len(done['paths']) == len(group['runs'])
            for run, receipt in zip(group['runs'], done['paths']):
                assert (run['algorithm'], run['rung']) == (receipt['algorithm'], receipt['rung'])
                path = folder/receipt['path']
                assert e.sha(path/'DONE.json') == receipt['done_sha256']
                raw = json.loads((path/'DONE.json').read_text())
                assert raw['source_sha256'] == e.sha(core.actor.__file__)
                assert raw['engine_sha256'] == e.sha(e.__file__)
                spec = raw['spec']
                assert (spec['system'], spec['seed'], spec['alpha']) == (
                    config['formal_systems'][index//4],
                    config['formal_sampling_seeds'][index % 4], group['alpha'])
                expected = receipt['primitive_per_arm']
                assert raw['primitive_transitions'] == dict(dense=expected, truncated=expected)
                for artifact in raw['artifacts']:
                    assert e.sha(path/artifact['path']) == artifact['sha256']
                expected_stages = 16 if run['algorithm'] == 'NPG' else 8
                assert len(raw['records']) == 2*(expected_stages+1)
                for arm in ['dense', 'truncated']:
                    rows = [r for r in raw['records'] if r['arm'] == arm]
                    assert [r['stage'] for r in rows] == list(range(expected_stages+1))
                    failures = [r['stage'] for r in rows if not r['stable']]
                    first_failure = min(failures) if failures else None
                    last = rows[-1]
                    assert last['primitive_transitions'] == expected
                    endpoint = dict(last, first_failure_stage=first_failure,
                                    D=None, D_over_gap=None, action_gap=None,
                                    action_error_fro=None, gap_decomposition_error=None,
                                    cost_identity_error=None, origin='X9_NEW_FULL_RANK')
                    if not endpoint['stable']:
                        endpoint['gap'] = endpoint['relative_gap'] = math.inf
                    assert endpoint['gap'] >= 0 and endpoint['relative_gap'] >= 0
                    endpoints.append(endpoint)
                    stages.extend(rows)
    assert len(endpoints) == 2560
    keys = {(r['alpha'], r['algorithm'], r['rung'], r['system'], r['seed'], r['arm'])
            for r in endpoints}
    assert len(keys) == len(endpoints)
    return endpoints, stages


def main(config_path):
    e.require_compute()
    config = json.loads(config_path.read_text())
    core.verify(config)
    assert config['status'] == 'FORMAL_FROZEN'
    out = core.OUT/'report-v1'
    assert not out.exists()
    out.mkdir(parents=True)
    endpoints, stages = saved_endpoints(config_path, config)
    baseline = read_csv(core.ROOT/'baseline/summary.csv')
    schema = list(baseline[0]) + ['alpha', 'tau2_sq']
    summary = [dict(r, alpha=0., tau2_sq=0.) for r in baseline if float(r['n']) == 24]
    assert len(summary) == 16
    pairs = []
    # X6b uses these exact draws. Reuse across alpha/rung/ratio definitions.
    for algorithm, tag in [('NPG', 20), ('PI', 21)]:
        random = e.rng(config['bootstrap_tag'], 24, tag)
        draws = random.integers(0, 8, size=(5000, 8))
        indices = (draws[:, :, None]*4 + np.arange(4)[None, None, :]).reshape(-1, 32)
        for alpha in config['new_alphas']:
            for rung in config['rungs']:
                rows = [r for r in endpoints if r['algorithm'] == algorithm
                        and r['alpha'] == alpha and r['rung'] == rung]
                assert len(rows) == 64
                lookup = {(r['system'], r['seed'], r['arm']): r for r in rows}
                ordered = {arm: [lookup[s, t, arm] for s in config['formal_systems']
                                 for t in config['formal_sampling_seeds']]
                           for arm in ['dense', 'truncated']}
                d, t = ordered['dense'], ordered['truncated']
                flags = [(a['stable'], b['stable']) for a, b in zip(d, t)]
                ratios = [paired_ratio(a['gap'], b['gap']) for a, b in zip(d, t)]
                row = dict(n=24, algorithm=algorithm, rung=rung, alpha=alpha,
                           tau2_sq=22*alpha**2, primitive_per_arm=d[0]['primitive_transitions'],
                           full_pairs=32, dense_stable=sum(a for a, b in flags),
                           truncated_stable=sum(b for a, b in flags),
                           both_stable=sum(a and b for a, b in flags),
                           both_failed=sum(not a and not b for a, b in flags),
                           dense_only_failed=sum(not a and b for a, b in flags),
                           truncated_only_failed=sum(a and not b for a, b in flags),
                           structural_factor=None)
                for arm in ['dense', 'truncated']:
                    row[arm+'_padding_transitions_total'] = sum(r['padding_transitions'] for r in ordered[arm])
                    row[arm+'_first_failure_stages'] = json.dumps([r['first_failure_stage'] for r in ordered[arm]])
                    for metric in ['gap', 'relative_gap']:
                        for suffix, p in [('median', .5), ('q25', .25), ('q75', .75)]:
                            row[f'{arm}_{metric}_{suffix}'] = q([r[metric] for r in ordered[arm]], p)
                    for metric in ['D', 'action_gap', 'D_over_gap', 'action_error_fro']:
                        row[f'{arm}_{metric}_eligible'] = 0
                        row[f'{arm}_{metric}_median'] = None
                for i, (a, b) in enumerate(zip(d, t)):
                    pairs.append(dict(alpha=alpha, algorithm=algorithm, rung=rung,
                                      system=a['system'], seed=a['seed'],
                                      dense_stable=a['stable'], truncated_stable=b['stable'],
                                      dense_gap=a['gap'], truncated_gap=b['gap'], paired_ratio=ratios[i]))
                for kind in ['both_stable', 'failure_inclusive']:
                    valid = [v if v is not None and (kind != 'both_stable' or all(flags[i])) else None
                             for i, v in enumerate(ratios)]
                    values = [v for v in valid if v is not None]
                    boot = []
                    invalid = 0
                    for sample in indices:
                        vs = [valid[int(i)] for i in sample if valid[int(i)] is not None]
                        if vs:
                            boot.append(q(vs, .5))
                        else:
                            invalid += 1
                    summary.append(dict(row, ratio_kind=kind, ratio_pairs=len(values),
                                        paired_ratio_median=q(values, .5), ci_low=q(boot, .025),
                                        ci_high=q(boot, .975), bootstrap_invalid=invalid,
                                        bootstrap_valid=len(boot), bootstrap_repetitions=5000))
    assert len(summary) == 80 and all(set(r) == set(schema) for r in summary)
    derived = []
    for alpha in config['alphas']:
        for algorithm in ['NPG', 'PI']:
            rows = sorted([r for r in summary if float(r['alpha']) == alpha
                           and r['algorithm'] == algorithm and r['ratio_kind'] == 'both_stable'],
                          key=lambda r: float(r['rung']))
            M = [float(r['primitive_per_arm']) for r in rows]
            target = float(rows[-1]['dense_gap_median'])
            y = [float(r['truncated_gap_median']) for r in rows]
            identified_target = math.isfinite(target) and target > 0
            result = cross(M, y, target) if identified_target else np.nan
            left = bool(result < 0)
            missing = bool(not np.isfinite(result))
            observed_below = any(math.isfinite(v) and v <= target for v in y) if identified_target else False
            right = bool(identified_target and missing and not observed_below)
            unbracketed = bool(identified_target and missing and observed_below)
            derived.append(dict(alpha=alpha, tau2_sq=22*alpha**2, algorithm=algorithm, n=24,
                                N_cal=M[-1], dense_gap_at_N_cal=target,
                                truncated_N_to_match=abs(result), left_censored=left,
                                right_censored=right, unbracketed=unbracketed,
                                target_identified=identified_target,
                                factor=M[-1]/abs(result),
                                interpretation='Descriptive median-curve interpolation; no epsilon/probability guarantee'))
    files = [('summary.csv', summary, schema), ('endpoints.csv', endpoints, None),
             ('new_stages.csv', stages, None), ('new_paired_endpoints.csv', pairs, None),
             ('transitions_saved_derived.csv', derived, None),
             ('failures.csv', [r for r in endpoints if not r['stable']], list(dict.fromkeys(k for r in endpoints for k in r)))]
    for name, rows, fields in files:
        write_csv(out/name, rows, fields)
    core.save_new(out/'verification.json', dict(status='COMPLETE', config_sha256=e.sha(config_path),
                  source_sha256=e.sha(__file__), summary_rows=80, endpoint_rows=2560,
                  zero_new_training_transitions=True, job=os.environ['SLURM_JOB_ID'],
                  alpha_zero_reused_in_full=True,
                  files={name: e.sha(out/name) for name, _, _ in files}))
    print(json.dumps(dict(status='COMPLETE', summary_rows=80, endpoint_rows=2560)))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, required=True)
    main(p.parse_args().config)
