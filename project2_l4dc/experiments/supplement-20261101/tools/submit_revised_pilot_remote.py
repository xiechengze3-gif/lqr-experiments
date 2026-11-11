import argparse,json,time
from pathlib import Path
import submit_pilot_remote as ops
p=argparse.ArgumentParser();p.add_argument('--base',type=int,choices=[2048,8192,32768],required=True);p.add_argument('--review-sha',required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1];cfg=json.loads((root/f'configs/X1_actor_base{a.base}_v2.json').read_text())
assert len(a.review_sha)==64 and cfg['eta']>0 and len(cfg['npg_batches'])==96 and len(cfg['pi_batches'])==8
receipt=ops.OUT/f'submissions/X1-revised-pilot-base{a.base}.json';assert not receipt.exists()
ledger=ops.status();factor=a.base/2048;wall=int(5*factor);bound=18*wall/60
# Based on the maximum COMPLETE previous paired run63.552194s at88,850,304 transitions/arm.
primitive=sum((17+b)*32 for b in cfg['npg_batches']);pair_seconds=63.552194*primitive/88850304
formal_wall=int(__import__('math').ceil((9*2*pair_seconds*1.30+60)/60));formal_bound=32*formal_wall/60
assert ledger['requested_total_bound_SU']+bound+formal_bound<ops.CAP,'Measured full formal grid cannot fit; do not spend on this candidate'
cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','-t',str(wall),'--array=0-17%4','-J','l4dc-X1-revised-base'+str(a.base),
     '-o',str(ops.OUT/f'logs/revised-base{a.base}-%A_%a.out'),str(root/'slurm/run.sbatch'),str(a.base)]
r=dict(experiment='X1',stage='PILOT',scope='REVISED_ACTOR',base_blocks=a.base,job=None,requested_bound_SU=bound,
       projected_formal_bound_SU=formal_bound,review_task_sha256=a.review_sha,command=cmd,submission_epoch=time.time(),automatic_retries=0)
ops.write(receipt,r);ledger['jobs'].append(r);ledger['requested_total_bound_SU']+=bound;ops.write(ops.LEDGER,ledger)
job=ops.run(cmd).strip();assert job.isdigit();r['job']=job;ops.write(receipt,r);ledger['jobs'][-1]=r;ops.write(ops.LEDGER,ledger)
print(json.dumps(dict(job=job,base=a.base,pilot_cases=18,pilot_requested_bound_SU=bound,projected_formal_bound_SU=formal_bound,cumulative_requested_bound_SU=ledger['requested_total_bound_SU'])))
