"""Explicitly accepted, zero-training X4 formal diagnostic only."""
import hashlib,json,time
from pathlib import Path
import submit_pilot_remote as ops

root=Path(__file__).resolve().parents[1];approval=json.loads((root/'X4/ACCEPTED.json').read_text())
assert approval['decision']=='ACCEPTED' and approval['experiment']=='X4'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(root/'configs/X4_v1.json')==approval['config_sha256'] and sha(root/'robustness_x4.py')==approval['source_sha256']
sources=json.loads((root/'X4/SOURCE_POLICY_MANIFEST.json').read_text());assert sources['source_files']==96
for d in sources['items']:
    assert sha(Path(d['path']))==d['json_sha256'] and sha(Path(d['archive']))==d['archive_sha256']
receipt=ops.OUT/'submissions/X4-formal-diagnostic-v23.json';assert not receipt.exists()
ledger=ops.status();bound=5/60;assert ledger['requested_total_bound_SU']+bound<=ops.CAP
balance=ops.run(['myproject']);line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x);assert float(line.split('|')[6].strip())>bound
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t','5','-J','l4dc-X4-formal-diagnostic',
     '-o',str(ops.OUT/'logs/X4-formal-diagnostic-%j.out'),str(root/'slurm/run.sbatch')]
r=dict(experiment='X4',stage='FORMAL',scope='OFFLINE_DIAGNOSTIC',job=None,requested_bound_SU=bound,command=cmd,
  approval=approval,balance_snapshot=balance,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps(dict(job=job,stage='FORMAL',scope='X4_OFFLINE_DIAGNOSTIC',requested_bound_SU=bound,cumulative_requested_bound_SU=ledger['requested_total_bound_SU'])))
