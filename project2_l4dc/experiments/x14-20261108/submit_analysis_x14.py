"""Submit a bounded X14 saved-data report with the shared accounting ledger."""
import argparse
import re
import subprocess
from datetime import datetime, timezone

import admit_x14 as admission


def main(item):
    root = admission.ROOT
    key = f'{item}-report'
    script = root / (key+'.sbatch')
    assert script.is_file()
    previous = admission.read(root / f'submit-{item}-formal-DONE.json')
    books = admission.history()
    assert books['outstanding_upper_SU']==0 and previous['job'] in {r['job'] for r in books['jobs']}
    assert (root/f'x14{item}-formal-{previous["tasks"]-1:03d}.tar').is_file()
    assert not (root/f'x14{item}-report').exists()
    begin, response, done = (root / f'submit-{key}-{suffix}.json' for suffix in ('BEGIN','RESPONSE','DONE'))
    assert not any(p.exists() for p in (begin,response,done))
    minutes = 10 if item=='a' else 20
    projected = books['settled_SU']+minutes/60+admission.REPORT_RESERVE
    assert projected<=60 and projected<=80
    balance = admission.call('myproject')
    account = next(l.split('|') for l in balance.splitlines() if '|'+admission.ACCOUNT+'|' in l)
    assert float(account[6])>=minutes/60+admission.REPORT_RESERVE
    queue = admission.call('squeue','-r','-h','-u','changze','-o','%i %T')
    assert len(queue.splitlines())<64
    assert not admission.call('sacct','-X','-n','-P','-u','changze','-S','2026-11-08',
                              '--name=x14-'+key,'--format=JobID').strip()
    quota = admission.quota(128, 512*2**20)
    command = ['sbatch','--parsable','--account='+admission.ACCOUNT,'--partition=medium','--ntasks=1',
               '--cpus-per-task=1','--mem=2048M',f'--time={minutes}','--no-requeue','--job-name=x14-'+key,
               '--array=0-0%1',f'--output={root}/x14{item}-report-%A_%a.out',str(script)]
    receipt = dict(item=item,stage='report',tasks=1,minutes=minutes,command=command,quota=quota,
                   exposure_SU=projected,books=books,own_queue=queue, balance=balance,
                   utc=datetime.now(timezone.utc).isoformat())
    admission.write(begin,receipt)
    job = subprocess.run(command,text=True,capture_output=True)
    admission.write(response,dict(stdout=job.stdout,stderr=job.stderr,returncode=job.returncode))
    assert job.returncode==0 and re.fullmatch(r'\d+(;\S+)?',job.stdout.strip())
    result = dict(receipt,job=job.stdout.strip().split(';')[0],status='SUBMITTED_ONCE')
    admission.write(done,result)
    print({k:result[k] for k in ('job','stage','minutes','exposure_SU')})


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('item',choices=['a','b'])
    main(parser.parse_args().item)
