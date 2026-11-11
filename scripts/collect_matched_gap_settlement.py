"""Filter AMS settlement to the exact own real job IDs in a saved Slurm ledger.

No other account members' rows are printed or retained. Dates use Grace's
local accounting calendar; displayed AMS SUs are rounded per job.
"""
import argparse
import csv
import json
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--account',required=True)
    p.add_argument('--start',required=True)
    p.add_argument('--end',required=True)
    p.add_argument('--accounting',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();jobs={}
    for line in a.accounting.read_text(encoding='utf-8-sig').splitlines():
        fields=line.strip().split('|')
        if len(fields)<11 or not fields[0] or '.' in fields[1]:continue
        assert fields[0] not in jobs
        jobs[fields[0]]=dict(state=fields[2],elapsed=int(fields[4] or 0),allocated_cpus=int(fields[5] or 0))
    assert jobs
    command=['myproject','-j',a.account,'-s',a.start,'-e',a.end]
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    rows=[];matched_lines=[]
    for line in process.stdout:
        fields=[s.strip() for s in line.split('|')]
        if len(fields)<11 or fields[1]!=a.account or fields[2] not in jobs:continue
        job=jobs[fields[2]]
        rows.append(dict(account=fields[1],real_job_id=fields[2],array_index=fields[3],
            submitted=fields[4],started=fields[5],ended=fields[6],
            settled_elapsed_seconds=int(fields[7]),reported_total_slots=float(fields[8]),
            displayed_rounded_SU=float(fields[9]),slurm_state=job['state'],
            slurm_elapsed_seconds=job['elapsed'],slurm_allocated_cpus=job['allocated_cpus']))
        matched_lines.append(line.rstrip('\n'))
    stderr=process.stderr.read();returncode=process.wait()
    assert returncode==0,(returncode,stderr)
    assert len({r['real_job_id'] for r in rows})==len(rows)
    measured={j for j,q in jobs.items() if q['elapsed']>0 and q['allocated_cpus']>0}
    seen={q['real_job_id'] for q in rows}
    result=dict(status='complete_query',account=a.account,start=a.start,end=a.end,
        matched_own_records=len(rows),expected_measured_nonzero_jobs=len(measured),
        missing_measured_job_ids=sorted(measured-seen),
        displayed_rounded_settled_SU_sum=sum(q['displayed_rounded_SU'] for q in rows),
        settled_elapsed_allocated_slot_hours=sum(q['settled_elapsed_seconds']*q['reported_total_slots']/3600 for q in rows),
        all_measured_jobs_settled=not (measured-seen),other_account_job_details_retained=False,
        per_job_elapsed_matches_slurm=all(q['settled_elapsed_seconds']==q['slurm_elapsed_seconds'] for q in rows),
        note='Only exact own IDs from the supplied Slurm ledger were retained. The TotalSlots column is allocated slots, NOT memory-equivalent billing cores. Displayed AMS SU values are rounded per job; their sum is not an unrounded CPU counter. Missing recent jobs are not assigned zero cost.')
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'own_settlement_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (a.output/'own_settled_rows.txt').write_text('\n'.join(matched_lines)+'\n')
    if rows:
        with (a.output/'own_settled_jobs.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(result))


if __name__=='__main__':main()
