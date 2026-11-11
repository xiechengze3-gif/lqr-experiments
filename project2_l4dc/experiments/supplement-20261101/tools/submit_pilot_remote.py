"""Receipt-first new-study pilot submission; all requested bounds count toward 200 SU."""
import argparse, hashlib, json, re, subprocess, time
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/supplement-20261101'
RELEASE=Path(__file__).resolve().parents[1]
LEDGER=OUT/'budget/ledger.json'
ACCOUNT='132685389143'
CAP=200.

def run(args):return subprocess.check_output(args,universal_newlines=True)
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)
def load():
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {'cap_SU':CAP,'jobs':[],'spent_SU':0.,'requested_total_bound_SU':0.}

def status():
    ledger=load();ids=[str(r['job']) for r in ledger['jobs'] if r.get('job')]
    lines=run(['sacct','-X','-j',','.join(ids),'-n','-P','--format=JobIDRaw,State,ElapsedRaw,AllocCPUS,AllocTRES']) if ids else ''
    actual=0.;allocations=[]
    for line in lines.splitlines():
        c=line.split('|')
        if len(c)<5:continue
        billing=re.search(r'(?:^|,)billing=([0-9.]+)',c[4]);effective=float(billing.group(1)) if billing else float(c[3])
        su=int(c[2])*effective/3600;actual+=su
        allocations.append(dict(job=c[0],state=c[1],elapsed_seconds=int(c[2]),effective_billing_cores=effective,SU=su))
    ledger.update(spent_SU=actual,allocations=allocations,last_accounting_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    ledger['requested_total_bound_SU']=sum(r['requested_bound_SU'] for r in ledger['jobs'])
    assert ledger['requested_total_bound_SU']<=CAP
    write(LEDGER,ledger);return ledger

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['population','checks','invariants','pilot_ce','pilot_actor','status']);p.add_argument('--calibration',type=int,default=0);p.add_argument('--review-sha',default='');p.add_argument('--attempt',type=int,default=0)
    a=p.parse_args()
    if a.mode=='status':print(json.dumps(status(),indent=2));return
    assert re.fullmatch('[a-f0-9]{64}',a.review_sha),'Caller must reread local Claude review log immediately before advancement'
    ledger=status();wall={'population':10,'checks':5,'invariants':5,'pilot_ce':10,'pilot_actor':30 if a.calibration==0 else 60}[a.mode]
    bound=wall/60
    assert ledger['requested_total_bound_SU']+bound<=CAP
    name=a.mode+(('-c'+str(a.calibration)) if a.mode=='pilot_actor' else '')+(('-r'+str(a.attempt)) if a.attempt else '')
    receipt=OUT/'submissions'/('X1-'+name+'.json');assert not receipt.exists(),'Inspect existing receipt before any replay'
    balance=run(['myproject']);account_line=next(x for x in balance.splitlines() if '|'+ACCOUNT+'|' in x)
    assert float(account_line.split('|')[6].strip())>bound
    (OUT/'logs').mkdir(parents=True,exist_ok=True)
    cmd=['sbatch','--parsable','-A',ACCOUNT,'-p','short','-t',str(wall),'-J','l4dc-X1-'+name,
      '-o',str(OUT/'logs'/('%x-%j.out')),str(RELEASE/'slurm/run.sbatch'),a.mode,'--config','configs/X1_v1.json']
    if a.mode=='pilot_actor':cmd+=['--calibration',str(a.calibration)]
    record={'experiment':'X1','stage':'PILOT','mode':a.mode,'calibration':a.calibration,'job':None,
      'wall_minutes':wall,'cpus':1,'memory_MiB':2048,'requested_bound_SU':bound,'review_task_sha256':a.review_sha,
      'automatic_retries':0,'command':cmd,'balance_snapshot':balance,'submission_epoch':time.time()}
    write(receipt,record);ledger['jobs'].append(record.copy());ledger['requested_total_bound_SU']+=bound;write(LEDGER,ledger)
    job=run(cmd).strip();assert job.isdigit(),job
    record['job']=job;write(receipt,record);ledger['jobs'][-1]=record;write(LEDGER,ledger)
    print(json.dumps({'job':job,'mode':a.mode,'calibration':a.calibration,'requested_bound_SU':bound,'cumulative_requested_bound_SU':ledger['requested_total_bound_SU'],'cap_SU':CAP,'receipt':str(receipt)}))

if __name__=='__main__':main()
