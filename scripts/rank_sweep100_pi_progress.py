"""Saved-data statistics for one fully completed formal rank, while others run."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics

from publish_rank_sweep100_results import read, write


def wilson(k,n):
    z=1.959963984540054;p=k/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,mid-half),min(1.,mid+half)]


p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--rank',type=int,required=True);a=p.parse_args();out=a.output
cfg=read(out/'resolved_config.json');assert a.rank in cfg['ranks'];seeds=cfg['confirm_seeds']
paths=sorted((out/'raw').glob(f'pi-r{a.rank:03d}-s*.json'))
data=[(path,read(path)) for path in paths];data=[(path,d) for path,d in data if d['seed'] in seeds]
assert len(data)==len(seeds)==30 and {d['seed'] for _,d in data}==set(seeds)
assert all(d['identity']==cfg['identity'] for _,d in data)
rows=[r for _,d in data for r in d['records']];results=[]
for eps in (cfg['epsilon'],cfg['epsilon']/2):
    for method in ('dense','truncated'):
        group=[r for r in rows if r['method']==method];grid=sorted({r['transitions'] for r in group});curve=[]
        for budget in grid:
            current=[r for r in group if r['transitions']==budget];assert len(current)==30
            hits=sum(bool(r['observed'] and r['stable'] and r['whole_path_stable']
                          and r['gap'] is not None and r['gap']<=eps) for r in current)
            curve.append(dict(transitions=budget,successes=hits,success_rate=hits/30,success_ci95=wilson(hits,30)))
        end=[r for r in group if r['transitions']==grid[-1]]
        gaps=[r['gap'] for r in end if r['observed'] and r['stable'] and r['gap'] is not None]
        results.append(dict(rank=a.rank,method=method,epsilon=eps,
            N_hat=next((r['transitions'] for r in curve if r['successes']>=27),None),
            success_by_budget=curve,endpoint_gap_median=statistics.median(gaps) if gaps else None,
            endpoint_stable_observed=len(gaps),whole_path_stable_endpoints=sum(r['whole_path_stable'] for r in end)))
proof=dict(scope='Historical intermediate snapshot for the specified rank only; see completion.json for final whole-experiment status',
    recorded_utc=datetime.now(timezone.utc).isoformat(),rank=a.rank,seeds=30,results=results,
    sources_sha256={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path,_ in data},
    new_simulator_transitions=0)
write(out/'progress'/f'formal-rank{a.rank:03d}.json',proof)
print(json.dumps({k:v for k,v in proof.items() if k!='sources_sha256'}),flush=True)
