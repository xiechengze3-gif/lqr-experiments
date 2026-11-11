"""One bounded zero-observation I/O pilot after failed-evidence E verification."""
import datetime,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path('/home/changze/lqr-x12-recovery-20261107-v2');REL=ROOT/'pilot-release-v2'
OLD=Path('/scratch/user/changze/lqr_experiments/results/x12-20261106')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def call(a):return subprocess.check_output(a,text=True,stderr=subprocess.STDOUT)
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(d,f,indent=2)
def main():
    assert Path(__file__).resolve()==REL/'submit_storage_pilot_v2.py'
    for line in (REL/'SHA256SUMS').read_text().splitlines():
        h,n=line.split('  ',1);assert sha(REL/n)==h
    cfg=json.loads((REL/'pilot-plan-v2.json').read_text())
    assert cfg['evidence_verified_on_E'] and cfg['new_training_transitions']==0
    assert cfg['evidence_archive_sha256']=='051d016a353fc4c743e9f7aee5ae6f8ddb0d3a17212d13c1fcd8081f65f9b4f2'
    review=(REL/'CLAUDE_TASK_authorized.md').read_text(encoding='utf-8-sig')
    assert 'X12 storage-failure recovery: ruling (01:40Z 11/07)' in review
    assert 'If all pass, proceed to FORMAL and REPORT without another review' in review
    dest=ROOT/'submissions/storage-io-v2';assert not dest.exists(),'Never replay an earlier submission attempt.'
    assert not (ROOT/'results/storage-pilot-v2').exists()
    prior=json.loads((OLD/'budget/LEDGER_v10.json').read_text());rows=[]
    assert abs(prior['cumulative_requested_SU']-169.9)<1e-8
    for entry in prior['allocations']:
        raw=call(['sacct','-X','--array','-n','-P','-j',entry['job'],'--format=JobID,State,ElapsedRaw,AllocTRES'])
        rr=[x.split('|')[:4] for x in raw.splitlines() if x];assert len(rr)==entry['tasks']
        for jid,state,secs,tres in rr:
            t=dict(x.split('=',1) for x in tres.split(',') if '=' in x)
            assert state in ['FAILED','COMPLETED'] and int(t['billing'])==int(t['cpu'])==1
            rows.append(dict(job=jid,state=state,elapsed_seconds=int(secs),actual_SU=int(secs)/3600))
    assert len(rows)==76 and sum(r['state']=='FAILED' for r in rows)==64
    actual=sum(r['actual_SU'] for r in rows)
    assert actual+5/60+8<300 and actual+5/60+8<230
    assert not call(['squeue','-r','-h','-u','changze','-o','%i']).strip()
    assert not call(['sacct','-X','--array','-n','-P','-u','changze','-S','2026-11-06T00:00:00','--name=x12-storage-io-v2','--format=JobID']).strip()
    quota=call(['/sw/local/bin/showquota']);df=call(['df','-B1','--output=size,used,avail',str(ROOT)]);di=call(['df','-i',str(ROOT)])
    home=next(s for s in quota.splitlines() if s.startswith('/home/changze')).split()
    assert 10000-int(home[-2])>=100 and home[1].endswith('G') and float(home[1][:-1])<8
    balance=call(['myproject']);account=next(s for s in balance.splitlines() if '|132685389143|' in s)
    assert float(account.split('|')[6])>=5/60
    args=['sbatch','--parsable','--account=132685389143','--partition=short','--ntasks=1','--cpus-per-task=1','--mem=2048M',
          '--time=5','--no-requeue','--job-name=x12-storage-io-v2','--output='+str(ROOT/'logs/storage-io-v2-%j.out'),str(REL/'pilot.sbatch')]
    dest.mkdir(parents=True)
    save(dest/'BEGIN.json',dict(command=args,requested_SU=5/60,prior_actual_SU=actual,prior_rows=rows,
        historical_summed_requests_SU=prior['cumulative_requested_SU'],prior_ledger_sha256=sha(OLD/'budget/LEDGER_v10.json'),
        exposure_bound_after_submission_SU=actual+5/60+8,report_reserved_SU=8,quota_snapshot=quota,df=df,df_inodes=di,
        balance=balance,review_sha256=sha(REL/'CLAUDE_TASK_authorized.md'),new_training_transitions=0,automatic_retries=0))
    response=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    save(dest/'RESPONSE.json',dict(command=args,returncode=response.returncode,stdout=response.stdout,stderr=response.stderr))
    assert response.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',response.stdout.strip()),'Stop, reconcile; never replay.'
    job=response.stdout.strip().split(';')[0]
    result=dict(status='STORAGE_IO_PILOT_SUBMITTED_ONCE',job=job,requested_SU=5/60,prior_actual_SU=actual,
                historical_summed_requests_SU=prior['cumulative_requested_SU']+5/60,
                actual_finished_plus_outstanding_plus_report_bound_SU=actual+5/60+8,
                requested_exposure_cap_SU=300,cumulative_actual_cap_SU=230,new_training_transitions=0,automatic_retries=0)
    save(dest/'DONE.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
