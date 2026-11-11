import json,time
from pathlib import Path
import submit_pilot_remote as ops
ROOT=Path(__file__).resolve().parents[1]
assert len(list((ops.OUT/'X1/ce_bundles').glob('*.json')))==32
receipt=ops.OUT/'submissions/X1-report-CE.json';assert not receipt.exists()
ledger=ops.status();bound=5/60;assert ledger['requested_total_bound_SU']+bound<=ops.CAP
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t','5','-J','l4dc-X1-CE-report',
     '-o',str(ops.OUT/'logs/CE-report-%j.out'),str(ROOT/'slurm/run.sbatch')]
r=dict(experiment='X1',stage='REPORT',scope='CE_ONLY',job=None,requested_bound_SU=bound,command=cmd,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps({'job':job,'scope':'CE_ONLY','stage':'REPORT','requested_bound_SU':bound,'cumulative_requested_bound_SU':ledger['requested_total_bound_SU']}))
