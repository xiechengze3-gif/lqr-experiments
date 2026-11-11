"""Read-only own-X6 Slurm/AMS queries; append a new accounting snapshot.

No account peer details are retained. AMS settlement and Slurm elapsed cost
are separate views and must never be added together.
"""
import datetime
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/x6-20261101'
ACCOUNT='132685389143'


def run(cmd):return subprocess.check_output(cmd,text=True)


def main():
    path=OUT/'budget/ledger.json'
    ledger=json.loads(path.read_text())
    own={str(r['job']) for r in ledger['submissions'] if r.get('job')}
    rows=[];steps=[];unknown_billing=[];physical_own=set()
    if own:
        raw=run(['sacct','-j',','.join(sorted(own)),'-n','-P',
            '--format=JobID%48,JobIDRaw,State,ElapsedRaw,AllocCPUS,TotalCPU,MaxRSS,AllocTRES'])
        for line in raw.splitlines():
            values=line.split('|')
            if len(values)<8:continue
            job,physical,state,elapsed,cpus,cputime,rss,tres=values[:8]
            job=job.strip();physical=physical.strip()
            physical_own.add(physical.split(".")[0])
            base=job.split('_')[0].split('.')[0]
            assert base in own
            row=dict(job=job,physical_job_id=physical,state=state,elapsed_seconds=int(elapsed),
                     cpus=int(cpus),total_CPU=cputime,max_RSS=rss,allocated_TRES=tres)
            if '.' in job:
                steps.append(row);continue
            if '[' in job:
                assert int(elapsed)==0,'Cannot bill compressed active array records.'
                rows.append(row);continue
            parsed=dict(p.split('=',1) for p in tres.split(',') if '=' in p)
            if int(elapsed)>0:
                if 'billing' not in parsed:
                    unknown_billing.append(job)
                    row['elapsed_billing_SU']=None
                else:
                    row['effective_billing_cores']=float(parsed['billing'])
                    row['elapsed_billing_SU']=float(parsed['billing'])*int(elapsed)/3600
            else:row['elapsed_billing_SU']=0.
            rows.append(row)
    ams=[];unparsed=[];seen=set()
    if own:
        process=subprocess.Popen(['myproject','-j',ACCOUNT,'-s','2026-11-01',
                                  '-e','2026-11-04'],stdout=subprocess.PIPE,text=True)
        for line in process.stdout:
            tokens=re.findall(r'(?<!\d)\d{8}(?:_\d+)?(?!\d)',line)
            if not any(t in own or t in physical_own or t.split('_')[0] in own for t in tokens):continue
            cells=[x.strip() for x in line.split('|')]
            try:
                assert cells[1]==ACCOUNT
                key=(cells[2],cells[3]);assert key not in seen;seen.add(key)
                ams.append(dict(job=cells[2],array_index=cells[3],
                    elapsed_seconds=int(cells[7]),slots=float(cells[8]),
                    displayed_used_SU=float(cells[9])))
            except (AssertionError,IndexError,ValueError):unparsed.append(line.rstrip())
        assert process.wait()==0 and not unparsed
    account_line=next(x for x in run(['myproject']).splitlines() if '|'+ACCOUNT+'|' in x)
    result=dict(status='BILLING_VERIFIED' if not unknown_billing else 'BILLING_UNVERIFIED',
        checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        cap_requested_SU=400,cumulative_requested_SU=ledger['cumulative_requested_SU'],
        slurm_elapsed_billing_SU=None if unknown_billing else
            sum(r.get('elapsed_billing_SU') or 0. for r in rows),
        ams_settled_walltime_slots_SU=sum(r['elapsed_seconds']*r['slots']/3600 for r in ams),
        ams_displayed_rounded_SU_sum=sum(r['displayed_used_SU'] for r in ams),
        allocations=rows,steps=steps,settled_records=ams,unknown_billing_jobs=unknown_billing,
        account_summary_line=account_line,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        note='Slurm elapsed and AMS settled are separate. Do not add; account balance is not study cost.')
    assert result['cumulative_requested_SU']<=400
    target=OUT/'budget'/('accounting-'+str(time.time_ns())+'.json')
    with target.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['allocations','steps','settled_records']}))


if __name__=='__main__':main()
