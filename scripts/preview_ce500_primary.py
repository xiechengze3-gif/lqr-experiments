"""Read saved-result counts only. Full independent Grace audit still required."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'analysis/ce500-primary-preview-20261019'
rows={}
for rank in (2,500):
    for seed in range(200,230):
        path=source/f'ce-r{rank:03d}-s{seed:04d}.json'
        raw=json.loads(path.read_text(encoding='utf-8'))
        assert raw['rank']==rank and raw['seed']==seed and len(raw['records'])==30
        for method in ('dense','truncated'):rows[rank,method,seed]=[r for r in raw['records'] if r['method']==method]
points=[]
for target in (.1,.05):
    pair={}
    for rank,method in [(2,'truncated'),(500,'dense')]:
        budgets=[r['transitions'] for r in rows[rank,method,200]]
        hits=[]
        counts=[]
        for j,b in enumerate(budgets):
            n=sum(bool(rows[rank,method,s][j]['stable'] and rows[rank,method,s][j]['gap']<=target) for s in range(200,230))
            counts.append(dict(transitions=b,successes=n))
            if n>=27:hits.append((b,n))
        assert hits
        pair[str(rank)]=dict(N90=hits[0][0],successes=hits[0][1],counts=counts)
    points.append(dict(target=target,rank2_truncated_N90=pair['2']['N90'],full500_dense_N90=pair['500']['N90'],
        saving_factor=pair['500']['N90']/pair['2']['N90'],rank2_successes=pair['2']['successes'],full_successes=pair['500']['successes'],counts=pair))
result=dict(status='preliminary_counts_awaiting_full_independent_cost_recompute',seeds=30,initial_gap=1,
    primary_comparisons=points,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('ce-*.json')})
(source/'preliminary_primary_counts.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=result['status'],primary_comparisons=[{k:v for k,v in r.items() if k!='counts'} for r in points])))
