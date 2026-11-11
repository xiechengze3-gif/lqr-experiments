"""Summarize only this campaign's Slurm records; allocations are not AMS settlement."""
import argparse
from collections import Counter
import csv
import json
import re
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--cap',type=float,default=140)
p.add_argument('--cap-unit',choices=['SU','allocated_core_hours'],default='SU')
a=p.parse_args()
columns=['job_id_raw','job_id','state','exit_code','elapsed_seconds','allocated_cpus','requested_memory',
         'allocated_tres','reported_total_cpu','nodes','time_limit_minutes']
rows=[];step_memory=[]
for line in a.input.read_text(encoding='utf-8-sig').splitlines():
    values=line.strip().split('|')
    if len(values)<len(columns) or not values[0].strip():continue
    row=dict(zip(columns,[value.strip() for value in values[:len(columns)]]))
    if '.' in row['job_id']:
        if len(values)>len(columns):
            memory=values[len(columns)].strip()
            match=re.fullmatch(r'([\d.]+)([KMGTP]?)',memory)
            if match:step_memory.append(float(match[1])*1024**('KMGTP'.find(match[2])+1 if match[2] else 0))
        continue
    for key in ('elapsed_seconds','allocated_cpus'):
        row[key]=int(row[key]) if row[key] else 0
    rows.append(row)
assert len({r['job_id_raw'] for r in rows})==len(rows),'Duplicate accounting entries would double charge cost'
assert all(not r['state'].startswith(('PENDING','RUNNING','COMPLETING')) for r in rows)

def seconds(value):
    if not value:return 0.
    days,clock=(value.split('-',1) if '-' in value else ('0',value))
    parts=[float(x) for x in clock.split(':')]
    return int(days)*86400+sum(v*60**i for i,v in enumerate(reversed(parts)))

for row in rows:
    tres=dict(item.split('=',1) for item in row['allocated_tres'].split(',') if '=' in item)
    row['billing_units']=float(tres.get('billing',row['allocated_cpus']))
    row['allocated_core_hours']=row['elapsed_seconds']*row['allocated_cpus']/3600
    row['elapsed_billing_unit_hours']=row['elapsed_seconds']*row['billing_units']/3600
    row['reported_total_cpu_hours']=seconds(row['reported_total_cpu'])/3600
result=dict(job_records=len(rows),states=dict(Counter(r['state'] for r in rows)),
    allocated_core_hours=sum(r['allocated_core_hours'] for r in rows),
    elapsed_billing_unit_hours=sum(r['elapsed_billing_unit_hours'] for r in rows),
    reported_total_cpu_hours=sum(r['reported_total_cpu_hours'] for r in rows) or None,
    total_cpu_counter_available=any(r['reported_total_cpu_hours']>0 for r in rows),
    maximum_recorded_step_RSS_bytes=max(step_memory) if step_memory else None,
    numerical_workers_one_allocated_cpu=all(r['allocated_cpus']==1 for r in rows if r['elapsed_seconds']>0),
    failed_jobs=[r for r in rows if r['state'].startswith(('FAILED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL'))],
    retired_unstarted_jobs=[r['job_id'] for r in rows if r['state'].startswith('CANCELLED') and r['elapsed_seconds']==0],
    compute_cap_SU=a.cap if a.cap_unit=='SU' else None,
    compute_cap_allocated_core_hours=a.cap if a.cap_unit=='allocated_core_hours' else None,
    cap_unit=a.cap_unit,
    note='Elapsed allocated-core and billing-unit hours are measured Slurm occupancy for own job IDs only. Reported TotalCPU is a separate utilization counter. These are not a claim that all AMS SU settlement has completed; original reservation caps are not counted as actual usage.')
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
with a.output.with_suffix('.csv').open('w',newline='',encoding='utf-8-sig') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps({k:v for k,v in result.items() if k not in ('failed_jobs','retired_unstarted_jobs')}))
