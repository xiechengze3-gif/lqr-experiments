"""Reserve a bounded pilot array; explicit resource-proof dependency, no formal path."""
import json,time
from pathlib import Path
import submit_pilot_remote as ops

root=Path(__file__).resolve().parents[1];plan=json.loads((root/'job_plan.json').read_text())
assert plan['stage']=='PILOT' and plan['scope']=='DENSE_ONLY_NPG_QUALIFICATION'
receipt=ops.OUT/'submissions'/(plan['id']+'.json');assert not receipt.exists()
ledger=ops.status();bound=plan['bundles']*plan['wall_minutes']/60
assert ledger['requested_total_bound_SU']+bound<=ops.CAP
balance=ops.run(['myproject']);line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x);assert float(line.split('|')[6].strip())>bound
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t',str(plan['wall_minutes']),
     '--array=0-'+str(plan['bundles']-1)+'%4','--dependency='+plan['dependency'],'-J','l4dc-'+plan['experiment']+'-NPG-pilot',
     '-o',str(ops.OUT/'logs'/(plan['id']+'-%A_%a.out')),str(root/'slurm/run.sbatch')]
r=dict(experiment=plan['experiment'],stage='PILOT',scope=plan['scope'],job=None,requested_bound_SU=bound,command=cmd,
       plan=plan,balance_snapshot=balance,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps(dict(job=job,scope=plan['scope'],requested_bound_SU=bound,cumulative_requested_bound_SU=ledger['requested_total_bound_SU'])))
