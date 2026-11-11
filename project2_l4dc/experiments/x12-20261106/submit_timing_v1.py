"""Submit two preregistered X12 timing jobs only after complete calibration."""
import datetime,hashlib,json,re,subprocess
from pathlib import Path
B=Path('/scratch/user/changze/lqr_experiments');O=B/'results/x12-20261106';R=B/'releases/x12-20261106-pilot-v1'
def call(args):return subprocess.check_output(args,universal_newlines=True,stderr=subprocess.STDOUT)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
    with p.open('x') as f:json.dump(d,f,indent=2)
assert subprocess.call(['sha256sum','-c','SHA256SUMS'],cwd=R,stdout=subprocess.DEVNULL)==0
cfg=json.loads((R/'config-protocol-v1.json').read_text());assert cfg['pilot_timing_requested_SU']==6
calpath=O/'calibration-resolution-v1/DONE.json';cal=json.loads(calpath.read_text())
assert cal['status']=='PASS_CALIBRATION' and cal['config_sha256']==sha(R/'config-protocol-v1.json')
assert cal['N_cal'] in cfg['calibration_grid'] and not cal['formal_data_used'] and not cal['truncated_readout']
ledger=json.loads((O/'budget/LEDGER_v3.json').read_text());assert ledger['cumulative_requested_SU']==2.75
assert ledger['cumulative_requested_SU']+6+8<=300
for entry in ledger['allocations']:
    rows=[line.split('|') for line in call(['sacct','-X','--array','-n','-P','-j',entry['job'],'--format=JobID,State,ElapsedRaw,AllocTRES']).splitlines() if line]
    assert len(rows)==entry['tasks'] and all(row[1]=='COMPLETED' for row in rows)
    assert all('billing=1' in row[3] for row in rows)
for i in range(8):
    rows=call(['sacct','-X','-n','-P','-j','20416268_'+str(i),'--format=JobID,State']).splitlines()
    assert len(rows)==1 and rows[0].split('|')[1]=='COMPLETED'
assert not (O/'timing-v1').exists() and not (O/'submissions/timing-v1').exists()
assert not call(['squeue','-r','-h','-u','changze','-n','x12-timing-v1-NPG,x12-timing-v1-PI','-o','%i']).strip()
assert not call(['sacct','-X','--array','-n','-P','-u','changze','-S','2026-11-06T00:00:00','--name=x12-timing-v1-NPG,x12-timing-v1-PI','--format=JobID']).strip()
queue=[line.split('|') for line in call(['squeue','-r','-h','-u','changze','-o','%i|%T|%j']).splitlines() if line]
allowed={'20416267','20416268','20416269','20416270','20416279','20416280','20416281','20416282'}
x10=B/'results/x10-20261106/X10b';report=x10/'submissions/REPORT_CHAIN_v1.json'
if report.exists():
    chain=json.loads(report.read_text());assert len(chain['jobs'])==5
    allowed.update(j['job'] for j in chain['jobs'])
assert all(row[0].split('_')[0] in allowed for row in queue)
assert sum(row[1] in ['RUNNING','COMPLETING','CONFIGURING'] for row in queue)+2<=64
# Permanent upper: at most24remaining n72PI + serial32otherlane + all5report
# reservations (conservative, even though reports follow formal) +2timing=63.
assert sum(row[0].split('_')[0]=='20416268' for row in queue)<=24
part=call(['scontrol','show','partition','medium','-o'])
assert 'MaxTime=1-00:00:00' in part or 'MaxTime=24:00:00' in part
dest=O/'submissions/timing-v1';dest.mkdir()
save(dest/'BEFORE.json',dict(utc=datetime.datetime.utcnow().isoformat()+'Z',queue=queue,partition=part,
    calibration_sha256=sha(calpath),config_sha256=sha(R/'config-protocol-v1.json'),reserved_timing_SU=6,
    slot_proof='24+32+5conservativeReportReservations+2timing<=63; no otherX12allocation active'))
jobs=[]
for alg in ['NPG','PI']:
    balance=call(['myproject']);line=next(x for x in balance.splitlines() if '|132685389143|' in x)
    assert float(line.split('|')[6])>=3
    args=['sbatch','--parsable','--account=132685389143','--partition=medium','--ntasks=1','--cpus-per-task=1','--mem=2048M','--time=03:00:00',
        '--no-requeue','--job-name=x12-timing-v1-'+alg,'--output='+str(O/'logs'/('timing-v1-'+alg+'-%j.out')),str(R/(alg+'.sbatch'))]
    save(dest/(alg+'-BEGIN.json'),dict(command=args,requested_upper_SU=3,balance=balance))
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    record=dict(command=args,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,requested_upper_SU=3)
    save(dest/(alg+'-RESPONSE.json'),record)
    assert result.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',result.stdout.strip()),'Submission uncertain/rejected: stop, no replay.'
    job=result.stdout.strip().split(';')[0];jobs.append(dict(job=job,role=alg,tasks=1,cpus=1,memory_MiB=2048,wall_minutes=180,requested_SU=3))
    save(dest/(alg+'-SUBMITTED.json'),dict(job=job,algorithm=alg,requested_SU=3))
    print(json.dumps(dict(status='TIMING_SUBMITTED_ONCE',algorithm=alg,job=job,requested_upper_SU=3)),flush=True)
save(O/'budget/LEDGER_v4.json',dict(ledger,allocations=ledger['allocations']+jobs,cumulative_requested_SU=8.75,
    timing_reserved_SU=0,report_reserved_SU=8,formal_not_yet_authorized_by_measured_gates=True))
save(dest/'DONE.json',dict(status='TIMING_BOTH_SUBMITTED_ONCE',jobs=jobs,cumulative_requested_SU=8.75,N_cal=cal['N_cal'],
    dependency='None: all calibration tasks/resolve already verified COMPLETED; saved receipt is immutable retrospective gate'))
