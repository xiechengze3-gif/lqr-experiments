"""Read-only compact progress for the actuation redundancy main experiment."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT/'configs/actuation_redundancy_20261016.json').read_text())
out = Path(cfg['output'])
stages = sum(length for _, length in cfg['schedule_segments'])
files = sorted((out/'raw').glob('*.json'))
data = [json.loads(p.read_text(encoding='utf-8')) for p in files]
cells = []
for m in cfg['action_dimensions']:
    completed = [d for d in data if d['m'] == m]
    if not completed:
        continue
    cell = dict(m=m, paired_seeds=len(completed))
    for method in cfg['methods']:
        final = [r for d in completed for r in d['records']
                 if r['method'] == method and r['stage'] == stages]
        values = [r['relative_gap'] for r in final if r['stable']]
        cell[method] = dict(stable=len(values),
                            median_g=float(np.median(values)) if values else None,
                            below_point1=sum(g <= .1 for g in values))
    cells.append(cell)
active = []
for path in sorted((out/'checkpoints').glob('*.npz')):
    # Never hold a live checkpoint open on Windows: it can prevent atomic
    # replacement by a worker. Completed raw JSON files are immutable.
    key=path.stem.rsplit('-',1)[0]
    if not (out/'raw'/(key+'.json')).exists():
        active.append(dict(file=path.name,modified_ns=path.stat().st_mtime_ns))
print(json.dumps(dict(complete_pairs=len(data), planned_pairs=100, cells=cells, active=active)))
