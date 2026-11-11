"""New X12 calibration allocations only, with persistent once-only receipts."""
import datetime, hashlib, json, subprocess
from pathlib import Path
BASE=Path('/scratch/user/changze/lqr_experiments');OUT=BASE/'results/x12-20261106';REL=BASE/'releases/x12-20261106-pilot-v1'
def call(args):return subprocess.check_output(args,universal_newlines=True,stderr=subprocess.STDOUT)
def save(p,data):
    with p.open('x') as f:json.dump(data,f,indent=2)
assert REL.is_dir() and not OUT.exists()
assert hashlib.sha256((REL/'config-protocol-v1.json').read_bytes()).hexdigest()=='2c4ea385999e7017197b6e7e04cb18b3c809942360e59a2665e7bedd3374d5e5'
assert subprocess.call(['sha256sum','-c','SHA256SUMS'],cwd=REL,stdout=subprocess.DEVNULL)==0
queue=[x.split('|') for x in call(['squeue','-r','-h','-u','changze','-o','%i|%T|%j']).splitlines() if x]
old=['20416267','20416268','20416269','20416270','20416279','20416280','20416281','20416282']
assert all(x[0].split('_')[0] in old for x in queue),'Unexpected own reservation; reconcile first.'
assert sum(x[1] in ['RUNNING','COMPLETING','CONFIGURING'] for x in queue)<=64
predecessors=['20416268_'+str(i) for i in range(8)]
for job in predecessors:
    states=call(['sacct','-X','-n','-P','-j',job,'--format=JobID,State']).splitlines()
    assert len(states)==1 and states[0].split('|')[1] in ['RUNNING','COMPLETED','PENDING','COMPLETING']
OUT.mkdir();(OUT/'logs').mkdir();(OUT/'submissions').mkdir();(OUT/'budget').mkdir()
account=call(['myproject'])
save(OUT/'submissions/BEFORE_CALIBRATION_v1.json',dict(utc=datetime.datetime.utcnow().isoformat()+'Z',queue=queue,account=account,
    slot_proof='first8 n72PI completion permanently releases8; 24+32+8<=64; resolve waits for calibration all8',
    pilot_requested_upper_SU=2.75,actual_cap_SU=230,requested_cap_SU=300,retry_count=0))
common=['sbatch','--parsable','--account=132685389143','--partition=short','--cpus-per-task=1','--mem=2048M','--no-requeue']
def submit(label,args):
    dest=OUT/'submissions'/(label+'.json');save(dest.with_suffix('.BEGIN.json'),dict(command=args))
    raw=call(args).strip();job=raw.split(';')[0];assert job.isdigit(),raw
    save(dest,dict(job=job,response=raw,command=args,utc=datetime.datetime.utcnow().isoformat()+'Z'));return job
cal=submit('calibration-v1',common+['--array=0-7%8','--time=00:20:00',
    '--dependency=afterok:'+':'.join(predecessors),'--job-name=x12-calibration-v1',
    '--output='+str(OUT/'logs/calibration-v1-%A_%a.out'),str(REL/'calibration.sbatch')])
resolve=submit('resolve-v1',common+['--time=00:05:00','--dependency=afterok:'+cal,'--job-name=x12-resolve-v1',
    '--output='+str(OUT/'logs/resolve-v1-%j.out'),str(REL/'resolve.sbatch')])
save(OUT/'budget/LEDGER_v1.json',dict(experiment='X12',allocations=[dict(job=cal,tasks=8,cpus=1,memory_MiB=2048,wall_minutes=20,requested_SU=8/3),
    dict(job=resolve,tasks=1,cpus=1,memory_MiB=2048,wall_minutes=5,requested_SU=1/12)],cumulative_requested_SU=2.75,
    timing_reserved_SU=6,report_reserved_SU=8,formal_authorized_after_measured_gates_only=True,actual_cap_SU=230,requested_cap_SU=300))
save(OUT/'submissions/AFTER_CALIBRATION_v1.json',dict(utc=datetime.datetime.utcnow().isoformat()+'Z',account=call(['myproject']),
    queue=call(['squeue','-h','-u','changze','-o','%i|%T|%j|%E'])))
print(json.dumps(dict(status='CALIBRATION_SUBMITTED_ONCE',calibration_job=cal,resolution_job=resolve,requested_upper_SU=2.75,
    calibration_tasks=8,dependency='afterok:'+':'.join(predecessors),formal_submitted=False)))
