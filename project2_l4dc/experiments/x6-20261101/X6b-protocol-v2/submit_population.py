"""Only the explicitly accepted X6b protocol-resolution job; no MC dispatch."""
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path
import remote_ops as ops


def main():
    root=Path(__file__).resolve().parent
    ops.verify(root)
    plan=json.loads((root/'job_plan.json').read_text())
    approval=json.loads((root/'approval.json').read_text())
    assert plan['experiment']=='X6b' and plan['stage']=='POPULATION_CALIBRATION'
    assert plan['tasks']==1 and plan['wall_minutes']==5 and plan['cpus']==1
    assert approval['accepted_stage']=='PROTOCOL' and approval['experiment']=='X6b'
    review=root/'CLAUDE_TASK_approved.md'
    assert approval['task_sha256']==ops.sha(review)
    quote=approval['exact_quote']
    assert 'ACCEPTED' in quote and 'X6b' in quote and quote in review.read_text(encoding='utf-8-sig')
    assert approval['protocol_manifest_sha256']==ops.sha(root/'PROTOCOL_SHA256SUMS')
    receipt=ops.OUT/'submissions'/(plan['id']+'.json')
    with (ops.OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert not receipt.exists(),'No implicit replay; reconcile the existing receipt.'
        ledger_path=ops.OUT/'budget/ledger.json'
        ledger=json.loads(ledger_path.read_text())
        bound=1/12
        assert ledger['cap_requested_SU']==400 and ledger['cumulative_requested_SU']+bound<=400
        balance=subprocess.check_output(['myproject'],text=True)
        line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x)
        assert float(line.split('|')[6].strip())>=bound
        cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','--ntasks=1',
             '--cpus-per-task=1','--mem=2048M','-t','5','--array=0-0%1',
             '-J',plan['id'],'-o',str(ops.OUT/'logs'/(plan['id']+'-%A_%a.out')),
             str(root/'run.sbatch')]
        row=dict(id=plan['id'],experiment='X6b',stage=plan['stage'],job=None,
            status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',epoch=time.time(),
            requested_bound_SU=bound,command=cmd,approval=approval,plan=plan,
            release=str(root),release_manifest_sha256=ops.sha(root/'SHA256SUMS'),
            balance_snapshot=balance,automatic_retries=0)
        ops.save(receipt,row);ledger['submissions'].append(row)
        ledger['cumulative_requested_SU']+=bound;ops.save(ledger_path,ledger)
        result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        row.update(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
        if result.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',result.stdout.strip()):
            row.update(job=result.stdout.strip().split(';')[0],status='SUBMITTED')
        else:row['status']='RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
        ops.save(receipt,row);ledger['submissions'][-1]=row;ops.save(ledger_path,ledger)
        print(json.dumps(row));assert row['status']=='SUBMITTED'


if __name__=='__main__':main()
