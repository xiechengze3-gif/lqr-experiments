"""Bounded second continuation for a specifically audited interrupted recovery."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from ce500_random_a_recovery_submit import metadata,read,sha,write


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--batch',type=int,required=True);p.add_argument('--failed-array',required=True)
    args=p.parse_args();cfg=read(args.manifest);out=Path(cfg['output']);plan=read(out/'formal_plan.json')
    originals=read(out/'submission-formal.json');original_ids=[originals['jobs']['rank_'+str(r)] for r in cfg['ranks']]
    attempts=[read(p) for p in out.glob('recovery-plan-*.json')]
    entries=[c for q in attempts for c in q['cases']]
    interrupted=subprocess.check_output(['sacct','-j',args.failed_array,'-X','-n','-P',
        '--format=JobIDRaw,JobID,State,ElapsedRaw,TimelimitRaw,NodeList'],text=True)
    rows=[q.split('|') for q in interrupted.splitlines() if q]
    assert rows and all(q[2] in ('TIMEOUT','FAILED','COMPLETED') for q in rows)
    cases=[];complete=[]
    for q in rows:
        if q[2]=='COMPLETED':continue
        task=int(q[1].rsplit('_',1)[1]);rank=cfg['ranks'][task//30];seed=cfg['confirm_seeds'][task%30]
        history=[c for c in entries if c['task']==task];assert len(history)==1,'At most one explicitly planned second continuation'
        stem=f'ce-r{rank:03d}-s{seed:04d}';cp=out/'checkpoints'/(stem+'.npz');meta=metadata(cp)
        assert meta['identity']==read(out/'verification.json')['identity']
        budgets=plan['budgets_by_rank'][str(rank)]
        if (out/'raw'/(stem+'.json')).exists() and (out/'estimates'/(stem+'.npz')).exists() and meta['done']==budgets[-1]:
            complete.append(dict(task=task,rank=rank,seed=seed,failed_id=q[0],science_complete=True));continue
        nxt=next((v for v in budgets if v>meta['done']),meta['done'])
        cases.append(dict(task=task,rank=rank,seed=seed,failed_id=q[0],failed_state=q[2],
            previous_recovery_job=q[0],done=meta['done'],checkpoint_sha256=sha(cp),remaining_OLS=budgets[-1]-meta['done'],
            wall_minutes=12,receipt_path=f'recovery-receipts/continuation-{args.batch:02d}/{stem}.json',
            checkpoint_backup_path=f'recovery-checkpoints/continuation-{args.batch:02d}/{stem}.npz',
            discarded_uncommitted_transition_lower_bound=0,discarded_uncommitted_transition_upper_bound=nxt-meta['done']))
    assert cases,'Nothing unfinished needs this second continuation'
    ledger=subprocess.check_output(['sacct','-j',','.join(original_ids),'-X','-n','-P',
        '--format=JobIDRaw,JobID,State,ElapsedRaw,TimelimitRaw'],text=True)
    released=0
    for line in ledger.splitlines():
        q=line.split('|')
        if len(q)<5 or q[2] not in ('COMPLETED','TIMEOUT','FAILED','OUT_OF_MEMORY'):continue
        task=int(q[1].rsplit('_',1)[1]);rank=cfg['ranks'][task//30]
        minutes=next(v['formal_wall_minutes'] for v in plan['resource_measurements'] if v['rank']==rank)
        released+=(minutes*60-int(q[3]))/3600
    prior_ids=[v for p in out.glob('submission-recovery-*.json') for v in read(p)['jobs'].values()]
    recledger=subprocess.check_output(['sacct','-j',','.join(prior_ids),'-X','-n','-P',
        '--format=JobIDRaw,JobID,State,ElapsedRaw,TimelimitRaw'],text=True)
    released_recovery=sum((int(q[4])*60-int(q[3]))/3600 for q in
        (line.split('|') for line in recledger.splitlines()) if len(q)>=5 and q[2] in ('COMPLETED','TIMEOUT','FAILED','OUT_OF_MEMORY'))
    newreserve=sum(c['wall_minutes']/60 for c in cases)
    reserved=sum(q['reserved_recovery_SU'] for q in attempts)+newreserve-released_recovery
    bound=plan['total_worst_case_SU_bound']-plan['recovery_SU_bound']-released+.25+reserved
    record=dict(status='inspected',batch=args.batch,cases=cases,science_complete_resource_failures=complete,
        reserved_recovery_SU=newreserve,released_original_wall_core_hours=released,
        released_prior_recovery_wall_core_hours=released_recovery,revised_worst_case_SU_bound=bound,total_SU_cap=60,
        amendment='Only these already interrupted recoveries may have a second continuation; original data/RNG/rows preserved; all lost sampling costs add by interruption; lower concurrency and longer bounded wall',
        excluded_hosts=['c136','c176','c189','c197','c258','c294','c306'],concurrency=6,
        source_sha256=sha(Path(__file__)))
    assert bound<60,(bound,'No jobs submitted')
    destination=out/f'recovery-plan-{args.batch:02d}.json';receipt=out/f'submission-recovery-{args.batch:02d}.json'
    assert not destination.exists() and not receipt.exists()
    write(destination,record);submission=dict(status='submitting',jobs={},cases=[c['task'] for c in cases],plan=str(destination))
    write(receipt,submission)
    cmd=['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short','--exclude='+','.join(record['excluded_hosts']),
        '-t','00:12:00','--array='+','.join(str(c['task']) for c in cases)+'%6','-J','ce500-rnda-continue2',
        '-o',str(out/'logs/recovery-%A_%a.out'),str(Path(__file__).resolve().parents[1]/'slurm/ce500_random_a_recover.sbatch'),'recover',str(destination)]
    job=subprocess.check_output(cmd,text=True).strip();assert job.isdigit()
    submission['jobs']['second_continuation']=job;submission['status']='submitted';write(receipt,submission)
    print(json.dumps(dict(cases=len(cases),job=job,revised_SU_bound=bound,plan=str(destination)),indent=2))


if __name__=='__main__':main()
