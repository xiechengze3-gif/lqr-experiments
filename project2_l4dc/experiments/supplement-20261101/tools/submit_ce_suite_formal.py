"""Receipt-first accepted X2/X3 CE formal dispatch, with global SU reservation."""
import hashlib,json,time
from pathlib import Path
import submit_pilot_remote as ops

root=Path(__file__).resolve().parents[1];plan=json.loads((root/'job_plan.json').read_text())
exp=plan['experiment'];assert exp in ['X2','X3'] and plan['stage']=='FORMAL' and plan['scope']=='CE_ONLY'
approval=json.loads((root/exp/'ACCEPTED_CE.json').read_text());assert approval['decision']=='ACCEPTED' and approval['scope']=='CE_ONLY'
for relative,digest in approval['source_hashes'].items():
    assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==digest
assert approval['config_sha256']==hashlib.sha256((root/plan['config']).read_bytes()).hexdigest()
receipt=ops.OUT/'submissions'/(plan['id']+'.json');assert not receipt.exists(),'Inspect existing receipt; never resubmit'
ledger=ops.status();bound=plan['bundles']*plan['wall_minutes']/60
assert ledger['requested_total_bound_SU']+bound<=ops.CAP
balance=ops.run(['myproject']);line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x);assert float(line.split('|')[6].strip())>bound
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t',str(plan['wall_minutes']),
     '--array=0-'+str(plan['bundles']-1)+'%8','-J','l4dc-'+exp+'-CE-formal',
     '-o',str(ops.OUT/'logs'/(plan['id']+'-%A_%a.out')),str(root/'slurm/run.sbatch')]
r=dict(experiment=exp,stage='FORMAL',scope='CE_ONLY',job=None,requested_bound_SU=bound,command=cmd,
   approval=approval,plan=plan,balance_snapshot=balance,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps(dict(job=job,experiment=exp,scope='CE_ONLY',requested_bound_SU=bound,cumulative_requested_bound_SU=ledger['requested_total_bound_SU'])))
