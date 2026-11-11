"""Read-only own-job accounting; administrative stdlib work on login node."""
import datetime
import json
from pathlib import Path
import subprocess

root=Path('/scratch/user/changze/lqr_experiments/results/final-story-20261024')
ids=set()
for p in root.glob('submission-*.json'):
    ids.update(v for v in json.loads(p.read_text())['jobs'].values() if v)
raw=subprocess.check_output(['sacct','-j',','.join(sorted(ids)),'-n','-P',
    '--format=JobIDRaw,JobID,State,ElapsedRaw,AllocCPUS,AllocTRES,TotalCPU'],text=True)
records={}
for line in raw.splitlines():
    c=line.split('|')
    if len(c)<7 or not c[0] or '.' in c[1]:continue
    assert int(c[4] or 0)==1 and 'billing=1' in c[5],line
    records[c[0]]=dict(job=c[1],state=c[2],elapsed_seconds=int(c[3] or 0),cpus=1,tres=c[5],total_cpu=c[6])
balance=subprocess.check_output(['myproject'],text=True)
data=dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    allocated_core_hours=sum(r['elapsed_seconds']/3600 for r in records.values()),
    complete=all(r['state'] in ['COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'] for r in records.values()),
    jobs=list(records.values()),failed_jobs=[r for r in records.values() if r['state']!='COMPLETED'],
    myproject_snapshot=balance,raw_sacct=raw,total_cap_SU=12.,
    basis='Sum of own Slurm allocation elapsed * AllocCPUS; all allocations billing=1. AMS Used & Pending is separate.')
path=root.parent.parent/'exports/final-story-20261024-final-accounting.json'
path.write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({k:data[k] for k in ['complete','allocated_core_hours','checked_at_utc']},indent=2))
