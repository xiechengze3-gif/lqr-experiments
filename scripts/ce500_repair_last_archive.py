"""Restore only AUTO-cancelled last archive/final, keeping running full audits."""
import argparse
import json
from pathlib import Path
import subprocess


def read(p):return json.loads(p.read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    cfg=read(a.manifest);out=Path(cfg['output']);release=a.manifest.resolve().parents[1]
    formal=read(out/'formal_submission.json');final=read(out/'final_bundle_submission.json');rec=read(out/'recovery_plan.json')
    assert len(rec['additional_cases'])==2 and formal['recovery_attempts']==3
    resume=rec['additional_cases'][0]['resume_array'];group=next(q for q in formal['bundle_jobs'] if q['group']==5)
    def states(ids):
        txt=subprocess.check_output(['sacct','-j',','.join(ids),'-X','-n','-P','-o','JobIDRaw,State,ElapsedRaw'],universal_newlines=True)
        return {f[0]:dict(state=f[1],elapsed=int(f[2] or 0)) for f in (q.split('|') for q in txt.splitlines()) if len(f)>=3}
    snap=states([group['job_id'],final['final_bundle_job'],formal['formal_report'],formal['identification_audit']])
    assert snap[group['job_id']]==snap[final['final_bundle_job']]==dict(state='CANCELLED',elapsed=0)
    assert all(snap[j]['state'] in ('RUNNING','COMPLETING','COMPLETED') for j in (formal['formal_report'],formal['identification_audit']))
    rs=states([resume]);resume_done=all(q['state']=='COMPLETED' for q in rs.values());assert len(rs)==2
    missing=[]
    for seed in cfg['confirm_seeds'][25:30]:
        for rank in cfg['ranks']:
            path=out/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json'
            if not path.exists():missing.append((rank,seed))
            else:assert read(path)['identity']==read(out/'verification.json')['identity']
    assert set(missing)<=set((8,s) for s in (227,228))
    if resume_done:assert not missing
    result=dict(status='prepared',snapshot=snap,resume_array=resume,resume_already_completed=resume_done,
        missing_raw=missing,running_full_audits_UNCHANGED=[formal['formal_report'],formal['identification_audit']],
        full_policy_rechecks=4050,formal_tasks=150,seeds_per_rank=30,audit_scope_unchanged=True)
    plan=out/'last_archive_recovery.json';assert not plan.exists()
    if not a.apply:print(json.dumps(result,indent=2));return
    def save():plan.write_text(json.dumps(result,indent=2)+'\n')
    def submit(args):
        job=subprocess.check_output(['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short']+args,cwd=str(release),universal_newlines=True).strip()
        assert job.isdigit();return job
    result['status']='applying';save()
    args=['-t','00:10:00','-J','ce500-archive-g5-recovery','-o',str(out.parent.parent/'accounting'/cfg['experiment']/'formal-05-recovery-%j.out')]
    if not resume_done:args+=['--dependency=afterok:'+resume]
    old_group=group['job_id'];new_group=submit(args+['slurm/ce500_bundle.sbatch','--kind','formal','--group','5'])
    group['job_id']=new_group;result['new_group5']=new_group;save()
    desired=[formal['formal_report'],formal['identification_audit']]+[q['job_id'] for q in formal['bundle_jobs']]
    current=states(desired);assert all(q['state'] in ('RUNNING','PENDING','COMPLETING','COMPLETED') for q in current.values())
    alive=[j for j in desired if current[j]['state']!='COMPLETED']
    args=['-t','00:10:00','-J','ce500-final-archive-recovery2','-o',str(out.parent.parent/'accounting'/cfg['experiment']/'final-archive-recovery2-%j.out')]
    if alive:args+=['--dependency=afterok:'+':'.join(alive)]
    old_final=final['final_bundle_job'];new_final=submit(args+['slurm/ce500_finish.sbatch']);result['new_final']=new_final;save()
    (out/'formal_submission_before_additional_timeouts.json').write_text(json.dumps(read(out/'formal_submission.json'),indent=2)+'\n')
    (out/'final_bundle_submission_before_additional_timeouts.json').write_text(json.dumps(final,indent=2)+'\n')
    formal['retired_auxiliary_jobs']+= [old_group,old_final]
    assert len(set(formal['retired_auxiliary_jobs']))==4
    (out/'formal_submission.json').write_text(json.dumps(formal,indent=2)+'\n')
    final.update(final_bundle_job=new_final,expected_pre_final_jobs=193,active_dependencies=alive,
        full_audit_scope_unchanged=True,known_timeouts=3)
    (out/'final_bundle_submission.json').write_text(json.dumps(final,indent=2)+'\n')
    result.update(status='applied',retired_zero_runtime_jobs=formal['retired_auxiliary_jobs'],expected_total_job_records=194)
    save();print(json.dumps(result,indent=2))


if __name__=='__main__':main()
