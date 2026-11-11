"""Read-only scientific scope monitor; optional new timestamped receipts only."""
import argparse
import datetime
import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101')


def main():
    p=argparse.ArgumentParser();p.add_argument('--save',action='store_true');a=p.parse_args()
    release=Path('/scratch/user/changze/lqr_experiments/releases/x6-20261101-b-formal-v14')
    config=json.loads((release/'formal-config.json').read_text());receipts={}
    for path in (BASE/'submissions').glob('*.json'):
        row=json.loads(path.read_text())
        if row['experiment']=='X6b' and row['stage']=='FORMAL':
            assert row['status']=='SUBMITTED' and row['job']
            receipts[row['plan']['id']]=row
    assert set(receipts)=={g['id'] for g in config['formal_groups']}
    jobs=','.join(receipts[g['id']]['job'] for g in config['formal_groups'])
    text=subprocess.check_output(['sacct','-X','--array','-j',jobs,'-n','-P',
        '--format=JobID%48,State,ElapsedRaw'],universal_newlines=True)
    state_rows={}
    for line in text.splitlines():
        if not line.strip():continue
        job,state,elapsed=line.split('|')[:3]
        state_rows[job.strip()]=dict(state=state.strip(),elapsed_seconds=int(elapsed))
    groups=[];errors=[]
    allowed=['COMPLETED','PENDING','RUNNING','COMPLETING','CONFIGURING','SUSPENDED','RESIZING']
    for group in config['formal_groups']:
        receipt=receipts[group['id']];job=receipt['job'];root=BASE/'X6b/formal-v1'/group['id']
        states=[state_rows.get(job+'_'+str(index),dict(state='ACCOUNTING_NOT_YET_VISIBLE',elapsed_seconds=0)) for index in range(32)]
        bad=[dict(index=index,**row) for index,row in enumerate(states) if row['state'] not in allowed+['ACCOUNTING_NOT_YET_VISIBLE']]
        failures=list(root.glob('task-*/HARD_FAILURE.json'))
        item=dict(group=group['id'],job=job,states=dict(Counter(r['state'] for r in states)),
            done_files=len(list(root.glob('task-*/DONE.json'))),hard_failure_files=len(failures),
            completed_checkpoints=len(list(root.glob('task-*/*/checkpoint-*.json'))),
            expected_checkpoints=32*sum(config['selected_NPG_T'] if r['algorithm']=='NPG' else config['selected_PI_T'] for r in group['runs']),
            max_elapsed_seconds=max(r['elapsed_seconds'] for r in states),
            requested_minutes_per_task=group['wall_minutes'])
        groups.append(item)
        if bad or failures:
            logs=[]
            for row in bad[:3]:
                path=BASE/'logs'/(receipt['id']+'-'+job+'_'+str(row['index'])+'.out')
                if path.exists():logs.append(dict(path=str(path),tail=path.read_text(errors='replace').splitlines()[-12:]))
            errors.append(dict(group=group['id'],bad_states=bad,
                failure_receipts=[json.loads(f.read_text()) for f in failures[:3]],logs=logs))
    data=dict(status='FAILURE_REVIEW_REQUIRED_NO_RETRY' if errors else 'MONITORING',
        checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),groups=groups,errors=errors,
        completed_tasks=sum(g['states'].get('COMPLETED',0) for g in groups),
        done_files=sum(g['done_files'] for g in groups),full_tasks=384,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if all(g['states'].get('COMPLETED',0)==g['done_files']==32 for g in groups):data['status']='ALL384_COMPLETED_READY_FOR_COUNTS_AUDIT'
    if a.save:
        folder=BASE/'X6b/formal-v1/monitor';folder.mkdir(parents=True,exist_ok=True)
        target=folder/('progress-'+str(time.time_ns())+'.json')
        with target.open('x',encoding='utf-8') as stream:stream.write(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data))


if __name__=='__main__':main()
