import json,time
from pathlib import Path
import submit_pilot_remote as ops
root=Path(__file__).resolve().parents[1];receipt=ops.OUT/'submissions/X2-CE-pilot.json';assert not receipt.exists()
ledger=ops.status();bound=1.;assert ledger['requested_total_bound_SU']+bound<=ops.CAP
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t','15','--array=0-3%2','-J','l4dc-X2-CE-pilot',
     '-o',str(ops.OUT/'logs/X2-CE-pilot-%A_%a.out'),str(root/'slurm/run.sbatch')]
r=dict(experiment='X2',stage='PILOT',scope='CE_ONLY',job=None,requested_bound_SU=bound,command=cmd,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps({'job':job,'scope':'X2_CE_PILOT','bundles':4,'cells_per_bundle':7,'requested_bound_SU':bound,'cumulative_requested_bound_SU':ledger['requested_total_bound_SU']}))
