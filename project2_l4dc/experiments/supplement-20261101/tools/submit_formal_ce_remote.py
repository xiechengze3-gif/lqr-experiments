"""Submit only the explicitly accepted X1 CE array, with all-night cost reservation."""
import json,subprocess,time
from pathlib import Path
import submit_pilot_remote as ops
ROOT=Path(__file__).resolve().parents[1]
approval=json.loads((ROOT/'X1/ACCEPTED_CE.json').read_text())
assert approval['decision']=='ACCEPTED' and approval['scope']=='CE_ONLY'
receipt=ops.OUT/'submissions/X1-formal-CE.json';assert not receipt.exists(),'Inspect receipt; never replay uncertain sbatch'
ledger=ops.status();bound=32*3/60
assert ledger['requested_total_bound_SU']+bound<=ops.CAP
balance=ops.run(['myproject']);line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x)
assert float(line.split('|')[6].strip())>bound
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t','3','--array=0-31%8','-J','l4dc-X1-CE-formal',
     '-o',str(ops.OUT/'logs/CE-formal-%A_%a.out'),str(ROOT/'slurm/run.sbatch')]
record=dict(experiment='X1',stage='FORMAL',scope='CE_ONLY',job=None,requested_bound_SU=bound,
            wall_minutes=3,bundles=32,cpus=1,memory_MiB=2048,approval=approval,command=cmd,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,record);ledger['jobs'].append(record);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();record['job']=job;ops.write(receipt,record);ledger['jobs'][-1]=record;ops.write(ops.LEDGER,ledger)
print(json.dumps({'job':job,'scope':'CE_ONLY','requested_bound_SU':bound,'cumulative_requested_bound_SU':ledger['requested_total_bound_SU']}))
