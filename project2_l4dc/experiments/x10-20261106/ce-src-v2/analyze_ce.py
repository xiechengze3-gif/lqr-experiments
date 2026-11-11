"""X10a saved-record statistics; new rows only, existing CSV bytes preserved."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import ce_driver as driver

ROOT = driver.ROOT


def write_csv(path, rows, fields=None):
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def q(values, p):
    ordered = sorted(values)
    at = p*(len(ordered)-1)
    lo, hi = math.floor(at), math.ceil(at)
    if lo == hi or ordered[lo] == ordered[hi]:
        return ordered[lo]
    return math.inf if math.isinf(ordered[hi]) else ordered[lo]+(at-lo)*(ordered[hi]-ordered[lo])


def cost(N, y, target):
    """Original X8 cost arithmetic; regression N, first downcross, no extrapolation."""
    if y[0] <= target:
        return N[0]
    for i in range(1, len(y)):
        if np.isfinite(y[i-1]) and y[i-1] > target >= y[i]:
            t = (np.log(target)-np.log(y[i-1]))/(np.log(y[i])-np.log(y[i-1]))
            return float(np.exp(np.log(N[i-1])+t*(np.log(N[i])-np.log(N[i-1]))))
    return np.inf


def merge_bytes(baseline, added, target):
    before = baseline.read_bytes()
    new = added.read_bytes()
    old_header = before.splitlines()[0]
    new_header, remainder = new.split(b'\n', 1)
    assert old_header.rstrip(b'\r') == new_header.rstrip(b'\r')
    assert before.endswith(b'\n')
    merged = before+remainder
    with target.open('xb') as stream:
        stream.write(merged)
    assert target.read_bytes()[:len(before)] == before
    return dict(baseline_sha256=hashlib.sha256(before).hexdigest(),
                baseline_bytes=len(before), merged_sha256=driver.sha(target),
                baseline_prefix_byte_identical=True)


def main(config_path):
    cfg, _ = driver.config_load(config_path)
    formal = ROOT/'ce-formal-v2'
    receipt = json.loads((formal/'FORMAL_DONE.json').read_text())
    assert receipt['status'] == 'COMPLETE_FORMAL_NEW_CONFIGURATIONS_ONLY'
    assert receipt['config_sha256'] == driver.sha(config_path)
    assert len(receipt['paths']) == 672
    out = ROOT/'ce-report-v2'
    assert not out.exists()
    out.mkdir()
    x8_rows, dimension, redundancy = [], [], []
    for ref in receipt['paths']:
        path = formal/ref['path']/'DONE.json'
        assert driver.sha(path) == ref['done_sha256']
        item = json.loads(path.read_text())
        assert item['status'] == 'COMPLETE'
        target = x8_rows if ref['path'].startswith('x8/') else dimension if ref['path'].startswith('dimension/') else redundancy
        target.extend(item['records'])
    assert len(x8_rows) == 122880 and len(dimension) == 2432 and len(redundancy) == 768
    sample_cost, flags = [], []
    d = pd.DataFrame(x8_rows)
    d['abs_gap'] = d.rel_gap*d.g0
    rng = np.random.default_rng(0)
    med = d.groupby(['family', 'config', 'order', 'N']).agg(
        median_abs_gap=('abs_gap', 'median'), median_rel_gap=('rel_gap', 'median'),
        n_unstable=('rel_gap', lambda x: int(np.sum(~np.isfinite(x)))), runs=('rel_gap', 'size')).reset_index()
    med.to_csv(out/'X8_new_medians.csv', index=False)
    for (family, config), g in d.groupby(['family', 'config']):
        g0 = g.groupby('system').g0.first()
        assert len(g0) == 8
        for eps in [.01, .005]:
            if family == 'exact':
                k = int(config[1:])
            else:
                rho = float(config[3:])
                singular = rho**np.arange(48)
                tail = np.array([np.sum(singular[i:]**2) for i in range(49)])
                k = max(int(np.argmax(tail <= eps)), 1)
            order = 'dense' if family == 'geometric' and k >= 48 else str(k)
            for arm, chosen in [('truncated', order), ('dense', 'dense')]:
                s = g[g.order == chosen]
                piv = s.pivot_table(index=['system', 'seed'], columns='N', values='abs_gap')
                assert len(piv) == 32
                Ns, arr = np.array(piv.columns, float), piv.values
                estimate = cost(Ns, np.median(arr, 0), eps)
                systems = piv.index.get_level_values(0).values
                ids = np.unique(systems)
                boots = []
                for _ in range(2000):
                    picked = rng.choice(ids, len(ids), replace=True)
                    sampled = np.concatenate([arr[systems == i] for i in picked])
                    boots.append(cost(Ns, np.median(sampled, 0), eps))
                boots = np.array(boots)
                sample_cost.append(dict(family=family, config=config, eps=eps, k=k, arm=arm,
                    order=chosen, N_req=estimate, ci_low=np.quantile(boots, .025),
                    ci_high=np.quantile(boots, .975), censored_draws=int(np.sum(~np.isfinite(boots))),
                    g0_median=float(g0.median()), n_unstable=int(np.sum(~np.isfinite(s.abs_gap)))))
                flags.append(dict(part='X8', config=config, eps=eps, arm=arm,
                    left_censored=bool(np.median(arr, 0)[0] <= eps), right_censored=bool(not np.isfinite(estimate)),
                    minimum_regression_N=int(Ns[0]), maximum_regression_N=int(Ns[-1])))
    dim_cost = []
    for n in cfg['dimension_n']:
        row = dict(n=n, eps=.01)
        for arm in ['dense', 'truncated']:
            selected = [r for r in dimension if r['n'] == n and r['arm'] == arm]
            Ns = sorted({r['N'] for r in selected})
            values = []
            for N in Ns:
                group = [r for r in selected if r['N'] == N]
                assert len(group) == 32
                values.append(q([r['gap'] for r in group], .5))
            estimate = cost(np.asarray(Ns, float), np.asarray(values), .01)
            row[arm+'_N_req'] = estimate
            flags.append(dict(part='X6a', n=n, eps=.01, arm=arm,
                              left_censored=bool(values[0] <= .01), right_censored=bool(not np.isfinite(estimate)),
                              minimum_regression_N=Ns[0], maximum_regression_N=Ns[-1]))
        dim_cost.append(row)
    normalized = []
    norm_records = []
    for r in redundancy:
        value = r['N']*r['redundant_cost']/r['v_star'] if r['stable'] else math.inf
        norm_records.append(dict(r, N_D_over_v_star=value))
    for extra in cfg['redundant_inputs']:
        for N in [4096, 8192]:
            for arm in ['dense', 'truncated']:
                group = [r for r in norm_records if r['m'] == 2+extra and r['N'] == N and r['arm'] == arm]
                assert len(group) == 32
                values = [r['N_D_over_v_star'] for r in group]
                normalized.append(dict(null_scale=.25, m=extra+2, m_minus_r=extra, N=N,
                    mode=arm, count=32, failures=sum(not r['stable'] for r in group),
                    median=q(values, .5), q25=q(values, .25), q75=q(values, .75)))
    assert len(sample_cost) == 32 and len(dim_cost) == 7 and len(normalized) == 24
    products = [('X8_sample_cost.csv', sample_cost),
                ('X6a_sample_cost_derived.csv', dim_cost), ('X1_normalized_statistics.csv', normalized)]
    preservation = {}
    for name, rows in products:
        baseline = ROOT/'ce-baseline'/name
        with baseline.open(newline='', encoding='utf-8-sig') as stream:
            schema = next(csv.reader(stream))
        added = out/('new_'+name)
        write_csv(added, rows, schema)
        preservation[name] = merge_bytes(baseline, added, out/('merged_'+name))
    write_csv(out/'new_X8_records.csv', x8_rows)
    write_csv(out/'new_dimension_records.csv', dimension)
    write_csv(out/'new_normalized_records.csv', norm_records)
    write_csv(out/'censoring_flags.csv', flags)
    failures = [dict(r, part='X8') for r in x8_rows if not math.isfinite(r['rel_gap'])]
    failures += [dict(r, part='X6a') for r in dimension if not r['stable']]
    failures += [dict(r, part='X1') for r in norm_records if not r['stable']]
    fields = list(dict.fromkeys(k for r in x8_rows+dimension+norm_records for k in r))+['part']
    fields = list(dict.fromkeys(fields))
    write_csv(out/'failures.csv', failures, fields)
    driver.save_new(out/'REPORT_DONE.json', dict(status='COMPLETE_NEW_ROWS_BASELINE_BYTES_PRESERVED',
        source_sha256=driver.sha(Path(__file__)), config_sha256=driver.sha(config_path),
        preservation=preservation, new_training_transitions=0, Grace_SU=0, Slurm_job_id=None,
        files={p.name: driver.sha(p) for p in out.iterdir() if p.is_file()}))
    print(json.dumps(dict(status='COMPLETE', new_sample_cost_rows=32, new_dimension_rows=7,
                         new_normalized_rows=24, failure_records=len(failures), Grace_SU=0)))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, required=True)
    main(p.parse_args().config)
