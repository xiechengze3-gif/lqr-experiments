"""Accepted conditional NPG formal dispatch, qualified dense pilots and measured plan."""
import hashlib,json,time
from pathlib import Path
import submit_pilot_remote as ops

root=Path(__file__).resolve().parents[1];plan=json.loads((root/'job_plan.json').read_text());exp=plan['experiment']
assert plan['stage']=='FORMAL' and plan['scope']=='NPG' and exp in ['X2','X3']
approval=json.loads((root/exp/'ACCEPTED_NPG.json').read_text())
assert approval['decision']=='ACCEPTED_CONDITIONS_SATISFIED' and approval['measured_plan_fits_cap']
for relative,digest in approval['source_hashes'].items():
    assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==digest
cfg=json.loads((root/plan['config']).read_text());assert cfg['phase']=='FORMAL'
for case in cfg['cases']:
    qpath=ops.OUT/exp/f'pilot-npg-base{cfg["base"]}'/f'QUALIFICATION-n{case["n"]}.json'
    q=json.loads(qpath.read_text());assert q['status']=='QUALIFIED' and not q['truncated_performance_used']
    for item in q['files']:assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
if exp=='X3':
    measure=json.loads((ops.OUT/'X3/pilot-npg-large'/f'BASE{cfg["base"]}_COMPLETE.json').read_text())
    assert measure['status']=='COMPLETE'
receipt=ops.OUT/'submissions'/(plan['id']+'.json');assert not receipt.exists()
ledger=ops.status();bound=plan['bundles']*plan['wall_minutes']/60
assert ledger['requested_total_bound_SU']+bound<=ops.CAP
balance=ops.run(['myproject']);line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x);assert float(line.split('|')[6].strip())>bound
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p',plan['partition'],'-t',str(plan['wall_minutes']),
     '--array=0-'+str(plan['bundles']-1)+'%'+str(plan['concurrency']),'-J','l4dc-'+exp+'-NPG-formal',
     '-o',str(ops.OUT/'logs'/(plan['id']+'-%A_%a.out')),str(root/'slurm/run.sbatch')]
r=dict(experiment=exp,stage='FORMAL',scope='NPG',job=None,requested_bound_SU=bound,command=cmd,plan=plan,
       approval=approval,balance_snapshot=balance,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps(dict(job=job,experiment=exp,scope='NPG',requested_bound_SU=bound,cumulative_requested_bound_SU=ledger['requested_total_bound_SU'])))
