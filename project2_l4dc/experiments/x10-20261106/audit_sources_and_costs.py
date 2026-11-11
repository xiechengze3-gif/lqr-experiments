"""Metadata/source bytes and planning arithmetic only; no scientific imports."""
import csv
import datetime
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
OLD = EXP/'x6-20261101/X6b-protocol-v2'


def ref(path):
    return dict(path=str(path.resolve()), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    cells, receipts = [], []
    new_sum = sum([.5, .125, .03125, .0078125, .00390625])
    for n in [24, 36, 48, 72]:
        for algorithm in ['NPG', 'PI']:
            group = f'n{n}-full-{algorithm}'
            paths = [OLD/'deliveries/formal-v1/X6b/formal-v1'/group/f'task-{i}/DONE.json'
                     for i in range(32)]
            times = [json.loads(p.read_text())['seconds'] for p in paths]
            receipts.extend(ref(p) for p in paths)
            predicted = max(times)*new_sum
            limit = math.ceil((1.2*predicted+30)/60)
            cells.append(dict(n=n, algorithm=algorithm, existing_group=group,
                              old_full_max_seconds=max(times), old_full_sum_seconds=sum(times),
                              provisional_body_seconds=predicted,
                              provisional_limit_minutes=limit,
                              requested_upper_SU=32*limit/60))
    inventory = {}
    for part in ['b', 'c']:
        path = EXP/'x8-local-20261104'/f'x8_{part}_raw.csv'
        with path.open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        inventory[part] = dict(source=ref(path), rows=len(rows),
                               configs=sorted({r['config'] for r in rows}),
                               systems=sorted({int(r['system']) for r in rows}),
                               seeds=sorted({int(r['seed']) for r in rows}),
                               regression_N=sorted({int(r['N']) for r in rows}))
    spectra = {str(rho): {str(eps): next(k for k in range(49)
                if sum(rho**(2*j) for j in range(k, 48)) <= eps)
                for eps in [.01, .005]} for rho in [.4, .6, .75, .85]}
    sources = [EXP/'x8-local-20261104'/name for name in
               ['PROTOCOL.md', 'PROTOCOL_AMENDMENT.md', 'run_x8.py', 'analysis/analyze_x8.py']]
    sources += [OLD/name for name in ['frozen_engine.py', 'actor_paths.py', 'formal_driver.py', 'analyze_actor.py']]
    sources += [EXP/'supplement-20261101'/name for name in ['engine.py', 'refine_ce.py']]
    sources += [EXP/'x6-20261101'/name for name in ['estimation.py', 'config-X6a-v1.json']]
    formal = sum(r['requested_upper_SU'] for r in cells)
    proof = dict(status='X10b_OVER_CAP_PROVISIONAL_PLAN_STOP_AND_REPORT',
                 created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 new_rung_sum=new_sum, cells=cells, formal_requested_upper_SU=formal,
                 cap_SU=160, exceeds_cap_before_pilot_report=formal > 160,
                 actual_new_benchmark=False, new_jobs=0, new_SU=0,
                 limits='Extrapolation from saved worst task runtime, not a measured X10 resource result. No extra stage was run.',
                 proposed_bounded_pilot=dict(n72_tasks=2, n72_wall_minutes=120,
                     equivalence_tasks=1, equivalence_wall_minutes=10, cpus=1, memory_MiB=2048,
                     requested_upper_SU=4+1/6,
                     status='PROPOSAL_ONLY_WAITING_CLAUDE_RESOURCE_DECISION'),
                 existing_source_hashes=[ref(p) for p in sources],
                 existing_timing_receipts=receipts,
                 X8_author_local_inventory=inventory, X10a_geometric_k_eps=spectra,
                 provisional_formal_body_core_hours=sum(r['old_full_sum_seconds']*new_sum for r in cells)/3600,
                 eight_core_formal_allocation_running_hours=formal/8)
    path = HERE/'SOURCE_AND_COST_AUDIT_v1.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in proof.items() if k not in
                      ['existing_source_hashes', 'existing_timing_receipts', 'X8_author_local_inventory']}))


if __name__ == '__main__':
    main()
