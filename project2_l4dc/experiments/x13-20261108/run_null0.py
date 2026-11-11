"""X13: CE redundant-cost cells of Table 8 that were never run (null part 0, m-r in {1,3,5,6,8,9}).

Uses the hash-verified frozen sources of X10a (frozen_engine.py 9915fc..., s_ce_original.py 3e9aed...)
unchanged, and repeats the numerical path of X10a ce_driver.run_shared_ce and the aggregation of
analyze_ce.py (q(), +inf for non-stabilizing outputs). Systems 101..108, seeds 1001..1004, n=12, r=2,
N in {4096, 8192}, burn 512, nu 1, as in the original X1 panel. No outcome-dependent choice.

Stage 'validate' recomputes published cells (null 0: m-r 2,4,7,10, original X1; null 0.25: m-r 3, X10a)
and must reproduce the published medians before stage 'formal' runs the new cells.
"""
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'src'))
sys.path.insert(0, str(HERE / 'shim'))  # numba stand-in, see shim/numba/__init__.py
import frozen_engine as e          # noqa: E402
import s_ce_original as original   # noqa: E402

N_GRID = [4096, 8192]
SYSTEMS = range(101, 109)
SEEDS = range(1001, 1005)


def q(values, p):  # analyze_ce.q, verbatim logic
    ordered = sorted(values)
    at = p * (len(ordered) - 1)
    lo, hi = math.floor(at), math.ceil(at)
    if lo == hi or ordered[lo] == ordered[hi]:
        return ordered[lo]
    return math.inf if math.isinf(ordered[hi]) else ordered[lo] + (at - lo) * (ordered[hi] - ordered[lo])


def run_cell(extra, null_scale):
    m, n = 2 + extra, 12
    records = []
    for system in SYSTEMS:
        s = e.plant(n, m, 2, system, null_scale=null_scale)
        vstar = float(np.sum((s['Pstar'] @ (s['A'] - s['B'] @ s['Kstar'])) ** 2))
        for seed in SEEDS:
            random = e.rng(10, n, m, system, seed)
            for fitted in original.ce_prefixes(s, N_GRID, random, dict(ce_burn=512, nu=1.)):
                theta = np.concatenate((fitted['Ahat'], fitted['Bhat']), axis=1)
                for arm, rank in [('dense', min(n, m)), ('truncated', 2)]:
                    rec = dict(null_scale=null_scale, m=m, m_minus_r=extra, system=system, seed=seed,
                               N=fitted['N'], arm=arm, v_star=vstar)
                    try:
                        gain = e.ce_learner(theta, n, s['Q'], s['R'], rank)
                        a = e.assess(s, gain)
                        rec.update(stable=a['stable'], redundant_cost=a['redundant_cost'])
                    except (np.linalg.LinAlgError, ValueError, ArithmeticError) as exc:
                        rec.update(stable=False, redundant_cost=None, failure=repr(exc))
                    rec['N_D_over_v_star'] = (fitted['N'] * rec['redundant_cost'] / vstar
                                              if rec['stable'] else math.inf)
                    records.append(rec)
    rows = []
    for N in N_GRID:
        for arm in ['dense', 'truncated']:
            group = [r for r in records if r['N'] == N and r['arm'] == arm]
            assert len(group) == 32
            v = [r['N_D_over_v_star'] for r in group]
            rows.append(dict(null_scale=null_scale, m=m, m_minus_r=extra, N=N, mode=arm, count=32,
                             failures=sum(not r['stable'] for r in group),
                             median=q(v, .5), q25=q(v, .25), q75=q(v, .75)))
    return records, rows


def write(path, rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    stage = sys.argv[1]
    cells = {'validate': [(2, 0.), (4, 0.), (7, 0.), (10, 0.), (3, .25)],
             'formal': [(1, 0.), (3, 0.), (5, 0.), (6, 0.), (8, 0.), (9, 0.)]}[stage]
    out = HERE / stage
    out.mkdir(exist_ok=False)
    all_records, all_rows = [], []
    for extra, ns in cells:
        rec, rows = run_cell(extra, ns)
        all_records += rec
        all_rows += rows
        print(json.dumps(dict(stage=stage, m_minus_r=extra, null_scale=ns, done=True)), flush=True)
    write(out / 'records.csv', all_records)
    write(out / 'X1_normalized_statistics.csv', all_rows)
