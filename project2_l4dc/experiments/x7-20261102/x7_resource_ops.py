"""Stdlib-only deployment and once-only accepted X7 resource submission."""
import argparse,fcntl,hashlib,json,re,subprocess,tarfile,time
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/x7-20261102'
TMP=BASE/'tmp/x7-20261102'
ACCOUNT='132685389143'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def verify(root):
    for line in (root/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert sha(root/name)==digest,name

def deploy(name,digest):
    assert re.fullmatch(r'x7-20261102-resource-v\d+',name)
    archive=TMP/(name+'.tar.gz');target=BASE/'releases'/name
    assert sha(archive)==digest and not target.exists(),'Inspect existing archive/release;no replay.'
    with tarfile.open(archive,'r:gz') as tf:
        members=tf.getmembers()
        assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
        target.mkdir();tf.extractall(target,members=members)
    verify(target)
    print(json.dumps(dict(status='DEPLOYED_VERIFIED',name=name,archive_sha256=digest)))

def submit(root):
    root=Path(root).resolve()
    assert root.parent==BASE/'releases';verify(root)
    cfg=json.loads((root/'config-protocol-v1.json').read_text())
    approval=json.loads((root/'approval.json').read_text())
    plan=json.loads((root/'resource-plan.json').read_text())
    assert cfg['experiment']=='X7' and cfg['status']=='PROTOCOL_FROZEN' and cfg['cap_requested_SU']==15
    for name,digest in cfg['scientific_sources'].items():assert sha(root/name)==digest
    assert approval['authorized_action']=='X7_RESOURCE_PILOT'
    task=root/'CLAUDE_TASK_approved.md';quote=approval['exact_quote']
    assert sha(task)==approval['task_sha256'] and quote in task.read_text(encoding='utf-8-sig')
    assert all(word in quote for word in ['X7','PROTOCOL','ACCEPTED'])
    assert sha(root/'PROTOCOL_MANIFEST.json')==approval['protocol_manifest_sha256']
    protocol=json.loads((root/'PROTOCOL_MANIFEST.json').read_text())
    assert sha(root/'PROTOCOL_SHA256SUMS')==protocol['manifest_sha256']
    for name,digest in protocol['files'].items():assert sha(root/name)==digest,name
    assert sha(root/'config-protocol-v1.json')==approval['config_sha256']
    assert plan==dict(stage='PILOT',tasks=4,concurrency=4,cpus=1,memory_MiB=2048,
        wall_minutes=15,requested_bound_SU=1.,automatic_retries=0,resource_only=True)
    for name in ['budget','logs','submissions']:(OUT/name).mkdir(parents=True,exist_ok=True)
    receipt=OUT/'submissions'/(root.name+'.json')
    with (OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert not receipt.exists(),'Receipt exists;reconcile,no automatic replay.'
        ledger_path=OUT/'budget/ledger.json'
        ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else dict(
            study='X7',cap_requested_SU=15.,cumulative_requested_SU=0.,submissions=[])
        assert ledger['study']=='X7' and ledger['cap_requested_SU']==15
        assert not any(r['stage']=='PILOT' for r in ledger['submissions']),'Existing pilot;review before retry.'
        assert ledger['cumulative_requested_SU']+1<=15
        balance=subprocess.check_output(['myproject'],text=True)
        line=next(line for line in balance.splitlines() if '|'+ACCOUNT+'|' in line)
        assert float(line.split('|')[6].strip())>=1
        cmd=['sbatch','--parsable','-A',ACCOUNT,'-p','short','--ntasks=1',
            '--cpus-per-task=1','--mem=2048M','-t','15','--array=0-3%4',
            '-J',root.name,'-o',str(OUT/'logs'/(root.name+'-%A_%a.out')),str(root/'run-resource.sbatch')]
        row=dict(id=root.name,experiment='X7',stage='PILOT',status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',
            job=None,epoch=time.time(),requested_bound_SU=1.,plan=plan,command=cmd,
            approval=approval,release=str(root),balance_snapshot=balance,
            release_manifest_sha256=sha(root/'SHA256SUMS'),automatic_retries=0)
        save(receipt,row);ledger['submissions'].append(row);ledger['cumulative_requested_SU']+=1.
        save(ledger_path,ledger)
        result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        row.update(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
        if result.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',result.stdout.strip()):
            row.update(job=result.stdout.strip().split(';')[0],status='SUBMITTED')
        else:row['status']='RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
        save(receipt,row);ledger['submissions'][-1]=row;save(ledger_path,ledger)
        print(json.dumps(row));assert row['status']=='SUBMITTED'

if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    dep=sub.add_parser('deploy');dep.add_argument('name');dep.add_argument('sha256')
    run=sub.add_parser('submit');run.add_argument('release',type=Path)
    args=parser.parse_args()
    if args.action=='deploy':deploy(args.name,args.sha256)
    else:submit(args.release)
