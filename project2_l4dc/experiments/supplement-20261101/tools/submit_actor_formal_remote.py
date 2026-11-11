import json,time
from pathlib import Path
import submit_pilot_remote as ops
root=Path(__file__).resolve().parents[1];approval=json.loads((root/'X1/ACCEPTED_ACTOR.json').read_text());assert approval['decision']=='ACCEPTED_CONDITIONS_SATISFIED'
receipt=ops.OUT/'submissions/X1-formal-ACTOR.json';assert not receipt.exists()
for alg in ('NPG','PI'):
    rows=[json.loads(p.read_text()) for p in (ops.OUT/'X1/pilot/revised-base2048'/alg).glob('*.json')]
    assert len(rows)==18 and all(all(r['stable'] for r in d['records'] if r['mode']=='dense') for d in rows)
    import statistics
    assert statistics.median([next(r for r in reversed(d['records']) if r['mode']=='dense')['relative_gap'] for d in rows])<=.5
ledger=ops.status();bound=16.;assert ledger['requested_total_bound_SU']+bound<=ops.CAP
balance=ops.run(['myproject']);line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x);assert float(line.split('|')[6].strip())>bound
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t','30','--array=0-31%8','-J','l4dc-X1-actor-formal',
     '-o',str(ops.OUT/'logs/X1-actor-formal-%A_%a.out'),str(root/'slurm/run.sbatch')]
r=dict(experiment='X1',stage='FORMAL',scope='ACTOR',job=None,requested_bound_SU=bound,approval=approval,command=cmd,balance_snapshot=balance,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps({'job':job,'scope':'X1_NPG_PI_FORMAL','bundles':32,'cases_per_bundle':9,'requested_bound_SU':bound,'cumulative_requested_bound_SU':ledger['requested_total_bound_SU']}))
