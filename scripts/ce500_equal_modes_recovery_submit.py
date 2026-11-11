"""Login-node stdlib inspection, bounded sparse submissions, no blind replay."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zipfile


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def metadata(p):
    with zipfile.ZipFile(p) as z:data=z.read('meta.npy')
    offset,length=(10,struct.unpack('<H',data[8:10])[0]) if data[6]==1 else (12,struct.unpack('<I',data[8:12])[0])
    header=ast.literal_eval(data[offset:offset+length].decode('latin1'));assert header['shape']==()
    return json.loads(data[offset+length:].decode('utf-32-le').rstrip('\x00'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--batch',type=int,required=True)
    p.add_argument('--submit',action='store_true');a=p.parse_args();cfg=read(a.manifest);out=Path(cfg['output']);release=a.manifest.resolve().parents[1]
    plan=read(out/'formal_plan.json');formal=read(out/'submission-formal.json');ids=[formal['jobs']['rank_'+str(r)] for r in cfg['ranks']]
    ledger=subprocess.check_output(['sacct','-j',','.join(ids),'-X','-n','-P','-o','JobIDRaw,JobID,State,ElapsedRaw,TimelimitRaw'],text=True)
    (out/'accounting'/f'before-recovery-{a.batch:02d}.psv').write_text(ledger)
    existing=[read(q) for q in out.glob('recovery-plan-*.json')];covered={c['task'] for q in existing for c in q['cases']}
    released=0.;cases=[];complete_failures=[];closed=0
    wall={2:12,4:12,8:8,32:15,500:20}
    for line in ledger.splitlines():
        f=line.split('|')
        if len(f)<5 or f[2] not in ('COMPLETED','TIMEOUT','FAILED','OUT_OF_MEMORY'):continue
        task=int(f[1].rsplit('_',1)[1]);rank=cfg['ranks'][task//30];seed=cfg['confirm_seeds'][task%30]
        original=next(q['formal_wall_minutes'] for q in plan['resource_measurements'] if q['rank']==rank)
        released+=(original*60-int(f[3]))/3600;closed+=1
        if f[2]=='COMPLETED' or task in covered:continue
        stem=f'ce-r{rank:03d}-s{seed:04d}';cp=out/'checkpoints'/(stem+'.npz');meta=metadata(cp)
        assert meta['identity']==read(out/'verification.json')['identity']
        budgets=plan['budgets_by_rank'][str(rank)];raw=out/'raw'/(stem+'.json');fit=out/'estimates'/(stem+'.npz')
        if raw.exists() and fit.exists() and meta['done']==budgets[-1]:
            complete_failures.append(dict(task=task,rank=rank,seed=seed,failed_id=f[0],science_complete=True));continue
        nxt=next((b for b in budgets if b>meta['done']),meta['done'])
        cases.append(dict(task=task,rank=rank,seed=seed,failed_id=f[0],failed_state=f[2],done=meta['done'],
            checkpoint_sha256=sha(cp),remaining_OLS=budgets[-1]-meta['done'],wall_minutes=wall[rank],
            discarded_uncommitted_transition_lower_bound=0,discarded_uncommitted_transition_upper_bound=nxt-meta['done']))
    oldreserve=plan['recovery_SU_bound'];reserved=sum(q['reserved_recovery_SU'] for q in existing)+sum(c['wall_minutes']/60 for c in cases)
    # Terminal resumes release their unused wall reservation, just as original attempts do.
    prior_ids=[]
    for path in out.glob('submission-recovery-*.json'):
        q=read(path)
        if 'cases' in q:prior_ids+=list(q['jobs'].values())
    released_recovery=0.
    if prior_ids:
        prior_ledger=subprocess.check_output(['sacct','-j',','.join(prior_ids),'-X','-n','-P','-o','JobIDRaw,JobID,State,ElapsedRaw,TimelimitRaw'],text=True)
        (out/'accounting'/f'prior-resumes-before-recovery-{a.batch:02d}.psv').write_text(prior_ledger)
        for line in prior_ledger.splitlines():
            f=line.split('|')
            if len(f)>=5 and f[2] in ('COMPLETED','TIMEOUT','FAILED','OUT_OF_MEMORY'):
                released_recovery+=(int(f[4])*60-int(f[3]))/3600
        reserved-=released_recovery
    bound=plan['total_worst_case_SU_bound']-oldreserve-released+.45+.25+reserved
    result=dict(status='inspected',batch=a.batch,cases=cases,science_complete_resource_failures=complete_failures,
        closed_original_tasks=closed,released_original_wall_core_hours=released,reserved_recovery_SU=sum(c['wall_minutes']/60 for c in cases),
        released_prior_recovery_wall_core_hours=released_recovery,
        revised_worst_case_SU_bound=bound,total_SU_cap=60,original_five_long_resume_reserve_replaced=True,
        resume_limit='At most one per interrupted task, at most150 tasks, and measured aggregate bound must remain below60SU',
        pending_rank8_extension_SU_bound=.45,timeout_overrun_additional_SU_reserve=.25,
        source_sha256=sha(Path(__file__)))
    assert bound<60,(bound,'No jobs submitted; requires budget revision');assert len(covered)+len(cases)<=150
    if not a.submit:print(json.dumps(result,indent=2));return
    dest=out/f'recovery-plan-{a.batch:02d}.json';receiptpath=out/f'submission-recovery-{a.batch:02d}.json'
    assert not dest.exists() and not receiptpath.exists(),'Inspect receipts before replay'
    assert cases,'No unfinished scientific runs require recovery';write(dest,result)
    receipt=dict(status='submitting',jobs={},plan=str(dest),cases=[c['task'] for c in cases]);write(receiptpath,receipt)
    for rank in cfg['ranks']:
        group=[c for c in cases if c['rank']==rank]
        if not group:continue
        cmd=['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short','--exclude=c136,c294',
            '-t',str(wall[rank]),'--array='+','.join(str(c['task']) for c in group)+'%'+str(min(21,len(group))),
            '-J','ce500-eqm-resume-r'+str(rank),'-o',str(out/'logs/recovery-%A_%a.out'),
            'slurm/ce500_equal_modes_recover.sbatch',str(dest)]
        job=subprocess.check_output(cmd,cwd=release,text=True).strip();assert job.isdigit()
        receipt['jobs']['rank_'+str(rank)]=job;write(receiptpath,receipt)
    receipt['status']='submitted';write(receiptpath,receipt);print(json.dumps(dict(plan=result,receipt=receipt),indent=2))


if __name__=='__main__':main()
