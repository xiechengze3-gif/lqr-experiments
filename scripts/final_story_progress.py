"""Small matched-prefix progress snapshot, stdlib only on Slurm compute."""
import collections
import json
import math
import os
from pathlib import Path
import statistics

assert os.environ.get('SLURM_JOB_ID')
root=Path('/scratch/user/changze/lqr_experiments/results/final-story-20261024')
groups=collections.defaultdict(dict);ce=collections.defaultdict(dict);counts=collections.Counter();e1=collections.defaultdict(list)
for p in (root/'formal').glob('*.json'):
    d=json.loads(p.read_text());t=d['spec'];counts[t['algorithm']]+=1
    if t['algorithm']=='CE':
        if t['family']=='E2':
            for r in d['rows']:
                mode='k12' if r['mode']=='dense' else r['mode']
                ce[r['N'],mode][t['system'],t['trial']]=r['gap'] if r['stable'] else math.inf
        continue
    value=d['rows'][-1].get('gap') if d['status']=='complete' else math.inf
    if t['family']=='E2':
        mode='adaptive' if t['mode']=='adaptive' else 'k'+str(t['k'])
        groups[t['final'],mode][t['system'],t['trial']]=value
    else:e1[t['algorithm'],t['mode'],t['m']].append(value)
rows=[];ranks=[0,1,2,3,4,5,6,8,10,12]
for final in [2048,8192,32768,131072]:
    units=set.intersection(*(set(groups[final,'k'+str(k)]) for k in ranks))
    if not units:
        rows.append(dict(final=final,matched_units=0));continue
    values={str(k):statistics.median([groups[final,'k'+str(k)][u] for u in sorted(units)]) for k in ranks}
    best=min(ranks,key=lambda k:values[str(k)])
    rows.append(dict(final=final,matched_units=len(units),best_k=best,
        median_gaps={k:v if math.isfinite(v) else None for k,v in values.items()},
        failed_counts={str(k):sum(not math.isfinite(groups[final,'k'+str(k)][u]) for u in units) for k in ranks}))
ce_rows=[]
for budget in [512,2048,8192,32768,131072]:
    units=set.intersection(*(set(ce[budget,'k'+str(k)]) for k in ranks))
    if not units:continue
    values={str(k):statistics.median([ce[budget,'k'+str(k)][u] for u in sorted(units)]) for k in ranks}
    ce_rows.append(dict(N=budget,matched_units=len(units),best_k=min(ranks,key=lambda k:values[str(k)]),
                       median_gaps={k:v if math.isfinite(v) else None for k,v in values.items()}))
out=dict(completed_by_algorithm=dict(counts),expected_files=1560,e2=rows,ce_e2=ce_rows,
    e1=[dict(algorithm=a,mode=mode,m=m,completed=len(v),median_gap=statistics.median(v))
        for (a,mode,m),v in sorted(e1.items())],
    interpretation='Preliminary only. U comparisons use identical completed system/trial sets across every fixed k. Failures retained as infinity.')
dest=root/('progress-'+os.environ['SLURM_JOB_ID']+'.json')
dest.write_text(json.dumps(out,indent=2,allow_nan=True)+'\n')
print(json.dumps(out,allow_nan=True),flush=True)
