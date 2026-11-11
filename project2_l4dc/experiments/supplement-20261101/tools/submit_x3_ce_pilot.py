import json,time
from pathlib import Path
import submit_pilot_remote as ops
root=Path(__file__).resolve().parents[1];receipt=ops.OUT/'submissions/X3-CE-pilot.json';assert not receipt.exists()
ledger=ops.status();bound=.25;assert ledger['requested_total_bound_SU']+bound<=ops.CAP
balance=ops.run(['myproject']);line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x);assert float(line.split('|')[6].strip())>bound
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t','15','-J','l4dc-X3-CE-pilot',
     '-o',str(ops.OUT/'logs/X3-CE-pilot-%j.out'),str(root/'slurm/run.sbatch')]
r=dict(experiment='X3',stage='PILOT',scope='CE_FIXED_FITS_AND_C5',job=None,requested_bound_SU=bound,command=cmd,balance_snapshot=balance,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps({'job':job,'scope':'X3_CE_PILOT_C5','trajectories':24,'requested_bound_SU':bound,'cumulative_requested_bound_SU':ledger['requested_total_bound_SU']}))
