"""Bounded pilot/report jobs only. Formal runs cannot use this path."""
import json,time
from pathlib import Path
import submit_pilot_remote as ops
root=Path(__file__).resolve().parents[1];plan=json.loads((root/'job_plan.json').read_text())
assert plan['stage'] in ('PILOT','REPORT')
receipt=ops.OUT/'submissions'/(plan['id']+'.json');assert not receipt.exists()
ledger=ops.status();bound=plan['wall_minutes']/60
assert ledger['requested_total_bound_SU']+bound<=ops.CAP
balance=ops.run(['myproject']);line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x);assert float(line.split('|')[6].strip())>bound
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t',str(plan['wall_minutes']),'-J','l4dc-'+plan['id'],
     '-o',str(ops.OUT/'logs'/(plan['id']+'-%j.out')),str(root/'slurm/run.sbatch')]
r=dict(experiment=plan['experiment'],stage=plan['stage'],scope=plan['scope'],job=None,requested_bound_SU=bound,command=cmd,balance_snapshot=balance,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps({'job':job,'id':plan['id'],'stage':plan['stage'],'requested_bound_SU':bound,'cumulative_requested_bound_SU':ledger['requested_total_bound_SU']}))
