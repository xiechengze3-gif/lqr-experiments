"""Compact read-only progress from task logs and committed raw files."""
from collections import Counter
import json
from pathlib import Path
import statistics
import subprocess

out=Path('/scratch/user/changze/lqr_experiments/results/ce500-rank4-extension-20261020')
receipt=json.loads((out/'submission-formal.json').read_text());array=receipt['jobs']['formal']
latest=[];by_budget={};logs=list((out/'logs').glob('confirm-'+array+'_*.out'))
for p in logs:
    records=[]
    for line in p.read_text(errors='replace').splitlines():
        if not line.startswith('{'):continue
        try:r=json.loads(line)
        except ValueError:continue
        if 'budget' in r and 'gaps' in r:
            records.append(r);by_budget.setdefault(r['budget'],[]).append(r)
    if records:latest.append(records[-1])
focus=[]
for b in [14336,24576,28672,40960,65536,131072,1048576]:
    rows=by_budget.get(b,[])
    if not rows:continue
    d=[r['gaps'][0] for r in rows if r['gaps'][0] is not None]
    t=[r['gaps'][1] for r in rows if r['gaps'][1] is not None]
    focus.append(dict(primitive_transitions=b+256,returned_seeds=len(rows),
        dense_median_gap=statistics.median(d) if d else None,truncated_median_gap=statistics.median(t) if t else None,
        truncated_successes_01=sum(x<=.1 for x in t),truncated_successes_005=sum(x<=.05 for x in t)))
result=dict(log_files=len(logs),tasks_returning_prefixes=len(latest),
    completed_raw_tasks=len(list((out/'raw').glob('ce-r004-s02*.json'))),
    latest_OLS_prefix_counts=dict(sorted(Counter(r['budget'] for r in latest).items())),focus=focus,
    formal_report_exists=(out/'report-confirm/summary.json').exists(),
    identification_audit_exists=(out/'identification-audit/audit.json').exists(),
    archive_receipt_exists=(out.parent.parent/'archives'/out.name/'receipt.json').exists())
print(json.dumps(result,indent=2))
print(subprocess.check_output(['squeue','-u','changze','-h','-n',
    'ce500-r4-confirm,ce500-r4-confirm-report,ce500-r4-identification,ce500-r4-archive',
    '-o','%T %M %N %R'],text=True))
