"""Read committed NPZ metadata only, without numerical simulation or NumPy."""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import statistics
import zipfile

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
p.add_argument('--route',choices=['npg','pi'],required=True);p.add_argument('--phase',choices=['pilot','confirm'],default='pilot')
a=p.parse_args();folder=a.root/a.route;cfg=json.loads((folder/'resolved_config.json').read_text());seeds=set(cfg[a.phase+'_seeds'])
data=[];stages=[]
for rank in cfg['ranks']:
    for seed in sorted(seeds):
        raw=folder/'raw'/f'{a.route}-r{rank:03d}-s{seed:04d}.json'
        cp=folder/'checkpoints'/raw.with_suffix('.npz').name
        if raw.exists():d=json.loads(raw.read_text());rows=d['records'];stage=max(q['stage'] for q in rows);complete=True
        elif cp.exists():
            with zipfile.ZipFile(cp) as z:blob=z.read('meta.npy')
            size=2 if blob[6]==1 else 4;offset=8+size;length=int.from_bytes(blob[8:offset],'little')
            header=ast.literal_eval(blob[offset:offset+length].decode('latin1'));assert header['descr'].startswith('<U')
            d=json.loads(blob[offset+length:].decode('utf-32le').rstrip('\0'));rows=d['rows'];stage=d['next_stage'];complete=False
        else:continue
        stages.append(stage)
        for m in ('dense','truncated'):
            q=max((v for v in rows if v['method']==m),key=lambda v:v['stage'])
            data.append(dict(rank=rank,seed=seed,method=m,stage=stage,complete=complete,
                transitions=q['transitions'],gap=q['gap'],stable=q['stable'],failure=q['failure']))
summary=[]
for rank in cfg['ranks']:
    for m in ('dense','truncated'):
        g=[q for q in data if q['rank']==rank and q['method']==m]
        if not g:continue
        valid=[q['gap'] for q in g if q['gap'] is not None]
        summary.append(dict(rank=rank,method=m,committed_seeds=len(g),complete=sum(q['complete'] for q in g),
            stages=[min(q['stage'] for q in g),max(q['stage'] for q in g)],
            median_latest_gap=statistics.median(valid) if valid else None,failures=sum(q['failure'] is not None for q in g)))
print(json.dumps(dict(route=a.route,phase=a.phase,committed_pairs=len(stages),stage_histogram=dict(Counter(stages)),
    summary=summary,scope='Latest committed snapshots can have different stages; this is progress, not a final success curve.')))
