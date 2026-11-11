"""Prepared concurrency-only override. Apply ONLY after explicit new acceptance.

Never submits/cancels/requeues jobs, changes wall/CPU/memory, touches the main
connection, overwrites a frozen release, or replays an existing journal.
"""
import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/x6-20261101'
TARGETS=[('20365638',24,'02:32:00'),('20365639',24,'02:31:00'),('20365565',16,'01:43:00')]
ACCOUNT='132685389143'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n')
    temporary.replace(path)


def inspect(job):
    raw=subprocess.check_output(['scontrol','-o','show','job',job],universal_newlines=True)
    keys=['UserId','Account','ArrayJobId','ArrayTaskThrottle','NumCPUs','TimeLimit','Partition',
          'MinMemoryNode','MinMemoryCPU','NumTasks']
    fields={key:sorted(set(re.findall(r'(?:^|\s)'+key+r'=(\S+)',raw))) for key in keys}
    assert fields['UserId'] and all(value.startswith('changze(') for value in fields['UserId'])
    assert fields['Account']==[ACCOUNT] and fields['ArrayJobId']==[job]
    assert fields['NumCPUs']==['1']
    return dict(job=job,fields=fields,raw=raw)


def coverage():
    raw=subprocess.check_output(['sacct','-X','--array','-j',','.join(t[0] for t in TARGETS),
        '-n','-P','--format=JobID%48,State'],universal_newlines=True)
    rows={line.split('|')[0].strip():line.split('|')[1].strip() for line in raw.splitlines() if line.strip()}
    result={job:{str(i):rows.get(job+'_'+str(i),'MISSING') for i in range(32)} for job,_,_ in TARGETS}
    assert all(state in ['PENDING','RUNNING','COMPLETED','COMPLETING','CONFIGURING']
               for data in result.values() for state in data.values())
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true')
    p.add_argument('--review',type=Path);p.add_argument('--review-sha256');p.add_argument('--exact-quote')
    a=p.parse_args();before=[inspect(job) for job,_,_ in TARGETS]
    proposed=[['scontrol','update','JobId='+job,'ArrayTaskThrottle='+str(limit)] for job,limit,_ in TARGETS]
    if not a.apply:
        print(json.dumps(dict(status='READ_ONLY_PROPOSAL_NOT_APPLIED',before=before,commands=proposed,
                              source_sha256=sha(Path(__file__)))));return
    assert a.review and sha(a.review)==a.review_sha256
    text=a.review.read_text(encoding='utf-8-sig');quote=a.exact_quote
    assert quote in text and 'ACCEPTED' in quote and 'X6b' in quote
    assert 'throttle' in quote.lower() or 'concurrenc' in quote.lower()
    for current,(job,limit,wall) in zip(before,TARGETS):
        assert current['fields']['TimeLimit']==[wall]
        assert current['fields']['ArrayTaskThrottle']==['8'],'Already changed; reconcile instead of replaying.'
    ledger=OUT/'budget/ledger.json';digest=sha(ledger);budget=json.loads(ledger.read_text())
    assert abs(budget['cumulative_requested_SU']-336.8666666666667)<1e-8
    assert budget['cap_requested_SU']==400 and budget['cumulative_requested_SU']+6.5<=400
    balance=subprocess.check_output(['myproject'],universal_newlines=True)
    line=next(line for line in balance.splitlines() if '|'+ACCOUNT+'|' in line)
    assert float(line.split('|')[6].strip())>=0
    states=coverage();folder=OUT/'X6b/formal-v1/scheduling-overrides';folder.mkdir(parents=True,exist_ok=True)
    journal=folder/'throttle-v1.json';assert not journal.exists(),'No replay; inspect existing journal/state.'
    data=dict(status='PREPARED_BEFORE_FIRST_UPDATE_NO_REPLAY',epoch=time.time(),
        review_sha256=a.review_sha256,exact_quote=quote,source_sha256=sha(Path(__file__)),
        before=before,coverage_before=states,commands=proposed,updates=[],balance_snapshot=balance,
        ledger_sha256_before=digest,requested_SU=budget['cumulative_requested_SU'],extra_requested_SU=0)
    write(journal,data)
    for current,command,(job,limit,_) in zip(before,proposed,TARGETS):
        row=dict(job=job,command=command,status='ABOUT_TO_CALL_DO_NOT_REPLAY')
        data['updates'].append(row);write(journal,data)
        process=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        row.update(returncode=process.returncode,stdout=process.stdout,stderr=process.stderr)
        write(journal,data)
        if process.returncode:
            data['status']='UPDATE_FAILED_STOPPED_NO_RETRY';write(journal,data)
            print(json.dumps(data));raise SystemExit(process.returncode)
        after=inspect(job);row['after']=after
        for key in current['fields']:
            if key!='ArrayTaskThrottle':assert current['fields'][key]==after['fields'][key],key
        assert after['fields']['ArrayTaskThrottle']==[str(limit)]
        row['status']='UPDATED_AND_RESOURCE_FIELDS_VERIFIED';write(journal,data)
    assert sha(ledger)==digest
    data.update(status='APPLIED_THROTTLES_ONLY',coverage_after=coverage(),ledger_sha256_after=sha(ledger))
    write(journal,data);print(json.dumps(data))


if __name__=='__main__':main()
