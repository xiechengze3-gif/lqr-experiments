"""Read already saved medians and metadata; no simulation or scientific refit."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sources = {
    'X2': EXP / 'supplement-20261101/X2/report-ce/all_statistics.csv',
    'X7': EXP / 'x7-20261102/summary.csv',
}
groups = defaultdict(list)
provenance = {}
for study, path in sources.items():
    provenance[study] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if study == 'X2':
                if row['n'] != '24' or row['metric'] != 'relative_gap':
                    continue
                key = (study, row['n'], 'exact-r' + row['r'], row['mode'])
                value = row['median']
                full, stable = row['count'], row['stable_count']
            else:
                key = (study, row['n'], row['spectrum'], row['mode'])
                value = row['relative_gap_median']
                full, stable = row['full'], row['stable']
            groups[key].append({'N': int(row['N']), 'transitions': int(row['transitions']),
                                'saved_median': value, 'full': full, 'stable': stable})
rows = []
for (study, n, cell, arm), curve in sorted(groups.items()):
    curve.sort(key=lambda x: x['N'])
    for target in (0.05, 0.02):
        hits = [i for i, point in enumerate(curve) if float(point['saved_median']) <= target]
        index = hits[0] if hits else None
        right = curve[index] if index is not None else None
        left = curve[index - 1] if index is not None and index > 0 else None
        status = 'RIGHT_CENSORED' if index is None else ('LEFT_CENSORED' if index == 0 else 'BRACKET_EXISTS')
        rows.append({'study': study, 'n': n, 'cell': cell, 'arm': arm, 'target': target,
                     'status': status, 'last_N': curve[-1]['N'],
                     'last_saved_median': curve[-1]['saved_median'],
                     'left': left, 'right': right, 'saved_curve': curve})
payload = {'scope': 'Queries saved median tables only. No median recomputation, interpolation, model evaluation, bootstrap or new job.',
           'provenance': provenance, 'rows': rows}
destination = HERE / 'saved_median_availability_v1.json'
with destination.open('x', encoding='utf-8') as stream:
    json.dump(payload, stream, indent=2)
print(json.dumps({'sources': provenance, 'cells': [
    {k: value for k, value in row.items() if k not in {'left', 'right', 'saved_curve'}}
    for row in rows]}, indent=2))
