"""Saved-result dense qualification, no numerical simulation or favorable-pair filtering."""
import argparse,hashlib,json,statistics
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('experiment',choices=['X2','X3']);p.add_argument('base',type=int);p.add_argument('n',type=int);a=p.parse_args()
out=Path('/scratch/user/changze/lqr_experiments/results/supplement-20261101')
root=out/a.experiment/f'pilot-npg-base{a.base}';spectra=['exact'] if a.experiment=='X2' else ['smooth','gapped','flat']
groups=[];files=[]
for sp in spectra:
    paths=sorted(root.glob(f'n{a.n}-{sp}-s*-t*.json'))
    if len(paths)!=4:
        print(json.dumps(dict(status='PENDING',experiment=a.experiment,n=a.n,spectrum=sp,complete=len(paths),expected=4)));raise SystemExit(0)
    values=[json.loads(path.read_text()) for path in paths]
    assert len({(d['spec']['system'],d['spec']['trial']) for d in values})==4
    assert all(d['status']=='COMPLETE' and d['actual_transitions']==d['independently_counted_transitions'] for d in values)
    stable=all(all(r['stable'] for r in d['records'] if r['mode']=='dense') for d in values)
    endpoints=[next(r for r in reversed(d['records']) if r['mode']=='dense') for d in values]
    median=statistics.median(r['relative_gap'] if r['stable'] else float('inf') for r in endpoints)
    groups.append(dict(n=a.n,spectrum=sp,count=4,all_dense_paths_stable=stable,dense_endpoint_relative_median=median,
      qualified=stable and median<=.5,max_complete_trajectory_seconds=max(d['seconds'] for d in values),
      actual_transitions_per_arm=values[0]['planned_transitions_per_arm']))
    files.extend(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths)
result=dict(status='QUALIFIED' if all(g['qualified'] for g in groups) else 'NOT_QUALIFIED',experiment=a.experiment,
   base=a.base,n=a.n,criterion='all dense paths stable and dense median relative endpoint<=.5 in every spectrum',
   groups=groups,files=files,truncated_performance_used=False)
dest=root/f'QUALIFICATION-n{a.n}.json';assert not dest.exists();dest.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='files'}))
