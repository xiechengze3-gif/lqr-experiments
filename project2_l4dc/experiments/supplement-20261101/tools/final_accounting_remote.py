"""Own-study settled/accounting snapshot; no simulations and no new Slurm job."""
import hashlib,json,re,subprocess,sys,time
from pathlib import Path

base=Path('/scratch/user/changze/lqr_experiments');out=base/'results/supplement-20261101'
sys.path.insert(0,str(base/'releases/supplement-20261101-x3-actor-report-v28/tools'))
import submit_pilot_remote as ops
target=out/'budget/final-accounting-v1.json';assert not target.exists(),'Do not replace a prior accounting snapshot'
ledger=ops.status()
active=[r for r in ledger['allocations'] if r['state'].split('+')[0] in ['RUNNING','PENDING','COMPLETING','CONFIGURING','SUSPENDED','RESIZING']]
assert not active,'Wait for every own-study job to finish before final accounting'
own={str(r['job']) for r in ledger['jobs'] if r.get('job')}
own.update(str(r['job']).split('.')[0] for r in ledger['allocations'])
process=subprocess.Popen(['myproject','-j',ops.ACCOUNT,'-s','2026-11-01','-e','2026-11-02'],stdout=subprocess.PIPE,universal_newlines=True)
rows=[];seen=set();unparsed=[]
for line in process.stdout:
    tokens=re.findall(r'(?<!\d)\d{8}(?:_\d+)?(?!\d)',line)
    if not any(t in own or t.split('_')[0] in own for t in tokens):continue
    cells=[x.strip() for x in line.split('|')]
    try:
        assert cells[1]==ops.ACCOUNT
        key=(cells[2],cells[3]);assert key not in seen;seen.add(key)
        rows.append(dict(job=cells[2],array_index=cells[3],submit_time=cells[4],start_time=cells[5],end_time=cells[6],
           elapsed_seconds=int(cells[7]),total_slots=float(cells[8]),displayed_used_SU=float(cells[9])))
    except (ValueError,IndexError,AssertionError):unparsed.append(line.rstrip())
assert process.wait()==0 and not unparsed
account_line=next(x for x in ops.run(['myproject']).splitlines() if '|'+ops.ACCOUNT+'|' in x)
resource_output=ops.run(['sacct','-j',','.join(str(r['job']) for r in ledger['jobs'] if r.get('job')),
     '-n','-P','--format=JobIDRaw,State,ElapsedRaw,AllocCPUS,TotalCPU,MaxRSS,AllocTRES'])
ams_seconds_SU=sum(r['elapsed_seconds']*r['total_slots']/3600 for r in rows)
result=dict(status='COMPLETE_FINAL_ACCOUNTING',checked_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
 cap_SU=200,slurm_elapsed_billing_SU=ledger['spent_SU'],cumulative_requested_bound_SU=ledger['requested_total_bound_SU'],
 new_submissions=len([r for r in ledger['jobs'] if r.get('job')]),unsubmitted_reserved_entries=len([r for r in ledger['jobs'] if not r.get('job')]),
 slurm_job_records=len(ledger['allocations']),ams_own_study_records=len(rows),ams_walltime_slots_SU=ams_seconds_SU,
 ams_displayed_rounded_SU_sum=sum(r['displayed_used_SU'] for r in rows),AMS_records=rows,account_summary_line=account_line,
 ledger_snapshot=ledger,slurm_resource_rows=resource_output.splitlines(),
 source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),new_training_transitions=0,new_job_SU=0,
 interpretation='Slurm elapsed billing includes all own-study jobs. AMS is a separate settled snapshot and may lag; displayed per-record SUs are rounded to two decimals. Do not add AMS and Slurm figures. Account-wide balance changes are not this study cost. Other account job details were discarded.')
assert result['slurm_elapsed_billing_SU']<=200 and result['cumulative_requested_bound_SU']<=200
target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['AMS_records','ledger_snapshot','slurm_resource_rows']}))
