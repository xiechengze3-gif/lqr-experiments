"""Stdlib-only login-node deployment/submission; never runs scientific code.

Submit only after local review of the latest channel. A durable receipt and
budget reservation precede sbatch; uncertain responses must be reconciled,
never retried by this tool. Existing releases and receipts are never replaced.
"""
import argparse
import fcntl
import hashlib
import json
import re
import subprocess
import tarfile
import time
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/x6-20261101'
ACCOUNT='132685389143'
CAP=400.


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)


def verify(root):
    for line in (root/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert sha(root/name)==expected,name


def deploy(name,digest):
    assert re.fullmatch(r'x6-20261101-[a-z0-9-]+',name)
    archive=BASE/'tmp/x6-20261101'/(name+'.tar.gz')
    target=BASE/'releases'/name
    assert sha(archive)==digest
    assert not target.exists(),'Existing release: inspect instead of replaying deployment.'
    with tarfile.open(archive,'r:gz') as tf:
        members=tf.getmembers()
        assert all(m.isfile() and not Path(m.name).is_absolute()
                   and '..' not in Path(m.name).parts for m in members)
        target.mkdir()
        tf.extractall(target,members=members)
    verify(target)
    print(json.dumps(dict(status='DEPLOYED_VERIFIED',name=name,archive_sha256=digest)))


def submit(root):
    root=root.resolve()
    assert root.parent==BASE/'releases'
    verify(root)
    plan=json.loads((root/'job_plan.json').read_text())
    assert plan['experiment']=='X6a'
    previous={'PILOT':'PROTOCOL','FORMAL':'PILOT','REPORT':'FORMAL'}[plan['stage']]
    approval=json.loads((root/'approval.json').read_text())
    assert approval['experiment']=='X6a' and approval['accepted_stage']==previous
    review=root/'CLAUDE_TASK_approved.md'
    assert approval['task_sha256']==sha(review)
    quote=approval['exact_quote']
    assert 'ACCEPTED' in quote and quote in review.read_text(encoding='utf-8-sig')
    assert approval['protocol_manifest_sha256']==sha(root/'PROTOCOL_SHA256SUMS')
    assert plan['cpus']==1 and plan['memory_MiB']==2048
    assert 1<=plan['wall_minutes']<=120 and 1<=plan['tasks']<=40
    bound=plan['tasks']*plan['wall_minutes']/60
    receipt=OUT/'submissions'/(plan['id']+'.json')
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert not receipt.exists(),'Receipt exists: reconcile; no automatic replay.'
        ledger_path=OUT/'budget/ledger.json'
        ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else dict(
            study='X6',cap_requested_SU=CAP,cumulative_requested_SU=0.,submissions=[])
        assert ledger['cap_requested_SU']==CAP
        if plan['stage']=='REPORT':
            # Claude's conditional REPORT authorization applies only after
            # the complete accepted FORMAL run passes metadata/hash validation.
            proof=OUT/'X6a/FORMAL_COMPLETE_v3.json'
            complete=json.loads(proof.read_text())
            assert complete['status']=='COMPLETE_METADATA_AND_HASHES'
            assert complete['bundles']==40 and complete['raw_estimates']==3520
            assert complete['stein_prefixes']==1920 and complete['ce_prefixes']==1600
            assert complete['analysis_sha256']==sha(root/'analyze_saved.py')
            assert complete['config_sha256']==sha(root/'config-X6a-v2.json')
            assert len(complete['allocations'])==40
            assert all(row['state']=='COMPLETED' for row in complete['allocations'])
        assert ledger['cumulative_requested_SU']+bound<=CAP
        balance=subprocess.check_output(['myproject'],universal_newlines=True)
        line=next(x for x in balance.splitlines() if '|'+ACCOUNT+'|' in x)
        assert float(line.split('|')[6].strip())>=bound
        logs=OUT/'logs';logs.mkdir(exist_ok=True)
        cmd=['sbatch','--parsable','-A',ACCOUNT,'-p','short',
             '--ntasks=1','--cpus-per-task=1','--mem=2048M',
             '-t',str(plan['wall_minutes']),
             '--array=0-'+str(plan['tasks']-1)+'%'+str(min(plan['concurrency'],plan['tasks'])),
             '-J',plan['id'],'-o',str(logs/(plan['id']+'-%A_%a.out')),
             str(root/'run.sbatch')]
        row=dict(id=plan['id'],stage=plan['stage'],experiment='X6a',job=None,
                 status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',command=cmd,
                 requested_bound_SU=bound,epoch=time.time(),automatic_retries=0,
                 plan=plan,approval=approval,balance_snapshot=balance,
                 release=str(root),release_manifest_sha256=sha(root/'SHA256SUMS'))
        save(receipt,row)
        ledger['submissions'].append(row)
        ledger['cumulative_requested_SU']+=bound
        save(ledger_path,ledger)
        result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        row.update(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
        if result.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',result.stdout.strip()):
            row.update(job=result.stdout.strip().split(';')[0],status='SUBMITTED')
        else:
            row['status']='RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
        save(receipt,row)
        ledger['submissions'][-1]=row;save(ledger_path,ledger)
        print(json.dumps(row))
        assert row['status']=='SUBMITTED'


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    d=sub.add_parser('deploy');d.add_argument('name');d.add_argument('sha256')
    s=sub.add_parser('submit');s.add_argument('release',type=Path)
    args=parser.parse_args()
    if args.command=='deploy':deploy(args.name,args.sha256)
    else:submit(args.release)


if __name__=='__main__':main()
