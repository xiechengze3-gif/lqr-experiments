"""Restore the SAME full audits/archives after a real checkpointed job timeout.

No audit is reduced or cancelled. The failed learning attempt is retained.
"""
import argparse
import json
from pathlib import Path
import subprocess


def read(p):return json.loads(p.read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    cfg=read(a.manifest);out=Path(cfg['output']);release=a.manifest.resolve().parents[1]
    formal=read(out/'formal_submission.json');final=read(out/'final_bundle_submission.json');recovery=read(out/'recovery_plan.json')
    assert recovery['manual_resumes_for_task']==1 and recovery['rank']==32 and recovery['seed']==216
    assert not (out/'report_resource_revision.json').exists(),'The rejected audit reduction must remain unapplied'
    assert len(cfg['confirm_seeds'])==30 and len(read(out/'formal_plan.json')['budgets'])==15
    def states(ids):
        txt=subprocess.check_output(['sacct','-j',','.join(ids),'-X','-n','-P','-o','JobIDRaw,State,ElapsedRaw'],universal_newlines=True)
        return {f[0]:dict(state=f[1],elapsed=int(f[2] or 0)) for f in (q.split('|') for q in txt.splitlines()) if len(f)>=3}
    audit_ids=[formal['formal_report'],formal['identification_audit']]
    group3=next(q for q in formal['bundle_jobs'] if q['group']==3)
    snapshot=states(audit_ids+[group3['job_id'],final['final_bundle_job']])
    assert snapshot[group3['job_id']]==dict(state='CANCELLED',elapsed=0)
    assert snapshot[final['final_bundle_job']]==dict(state='CANCELLED',elapsed=0)
    assert all(snapshot[j]['state'] in ('PENDING','CANCELLED') for j in audit_ids),snapshot
    missing=[]
    for seed in cfg['confirm_seeds'][15:20]:
        for rank in cfg['ranks']:
            path=out/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json'
            if not path.exists():missing.append((rank,seed))
            else:
                raw=read(path);assert raw['identity']==read(out/'verification.json')['identity']
                assert raw['physical_transitions']==1048832 and len(raw['records'])==30
    assert not missing or missing==[(32,216)],missing
    text=subprocess.check_output(['squeue','-j',','.join(formal['arrays_by_rank'].values()),'-h','-o','%F'],universal_newlines=True)
    active=sorted(set(s.strip() for s in text.splitlines() if s.strip()),key=int)
    assert set(active)<=set(formal['arrays_by_rank'].values())
    resume_state=states([recovery['resume_array']])[recovery['resume_array']]
    assert resume_state['state'] in ('PENDING','RUNNING','COMPLETING','COMPLETED'),resume_state
    parts=['afterany:'+':'.join(active)] if active else []
    if resume_state['state']!='COMPLETED':parts.append('afterok:'+recovery['resume_array'])
    else:assert not missing,'A completed resume must have committed all25group outputs'
    dependency=','.join(parts)
    record=dict(status='prepared',failed_learning_job_retained=recovery['failed_job_id'],resume_job=recovery['resume_array'],
        snapshots=snapshot,missing_raw_only_resumed_task=missing,active_original_learning_arrays=active,
        full_audit_dependency=dependency,resume_state=resume_state,completed_resume_dependency_omitted=resume_state['state']=='COMPLETED',
        full_audit_unique_policy_rechecks=4050,full_rank_pair_checks=450,
        formal_tasks=150,seeds_per_rank=30,budgets_per_seed=15,audit_scope_unchanged=True,
        cancelled_by_Slurm_not_by_agent=[group3['job_id'],final['final_bundle_job']],
        purpose='Necessary recovery of original full audits/archives after TIMEOUT. No scancel, no reduced audit, no changed scientific source/data.')
    if not a.apply:
        (out/'dependent_recovery_plan.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2));return
    log=out/'dependent_recovery_execution.json'
    if log.exists():
        previous=read(log)
        assert previous.get('status')=='applying' and previous.get('new_jobs')==[] and 'formal_report' not in previous,'Inspect a partial mutation before retrying'
        backup=out/'dependent_recovery_execution_attempt1.json';assert not backup.exists()
        previous['site_error']='Completed resume ID already purged from controller; first dependency update rejected without mutation'
        backup.write_text(json.dumps(previous,indent=2)+'\n');log.unlink()
    def save():log.write_text(json.dumps(record,indent=2)+'\n')
    def submit(args):
        job=subprocess.check_output(['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short']+args,cwd=str(release),universal_newlines=True).strip()
        assert job.isdigit(),job
        return job
    record['status']='applying';record['new_jobs']=[];save()
    retired=[]
    for key,kind in [('formal_report','report'),('identification_audit','identification')]:
        old=formal[key]
        if snapshot[old]['state']=='PENDING':
            subprocess.run(['scontrol','update','JobId='+old,'Dependency='+dependency],check=True)
            record[key]=dict(job_id=old,action='dependency_only_update',scope='original full scope preserved');save()
        else:
            assert snapshot[old]['elapsed']==0
            args=['-t','02:00:00' if kind=='report' else '00:10:00','--dependency='+dependency,
                '-J','ce500-full-'+kind+'-recovery','-o',str(out/'logs'/('full-'+kind+'-recovery-%j.out'))]
            if kind=='report':args+=['slurm/ce500_report.sbatch','--phase','confirm','--plan',str(out/'formal_plan.json'),'--full-audit']
            else:args+=['slurm/ce500_identification_audit.sbatch','--phase','confirm']
            job=submit(args);record['new_jobs'].append(job);formal[key]=job;retired.append(old)
            record[key]=dict(job_id=job,previous_cancelled_job=old,action='same_full_scope_replacement');save()
    old_group=group3['job_id']
    group_args=['-t','00:10:00','-J','ce500-archive-g3-recovery',
        '-o',str(out.parent.parent/'accounting'/cfg['experiment']/'formal-03-recovery-%j.out')]
    if resume_state['state']!='COMPLETED':group_args+=['--dependency=afterok:'+recovery['resume_array']]
    job=submit(group_args+['slurm/ce500_bundle.sbatch','--kind','formal','--group','3'])
    group3['job_id']=job;record['new_jobs'].append(job);retired.append(old_group);record['replaced_group3']=dict(old=old_group,new=job);save()
    old_final=final['final_bundle_job'];retired.append(old_final)
    desired=[formal['formal_report'],formal['identification_audit']]+[q['job_id'] for q in formal['bundle_jobs']]
    terminal=states(desired);live=[j for j in desired if terminal[j]['state']!='COMPLETED']
    assert all(terminal[j]['state'] in ('PENDING','RUNNING','COMPLETING','COMPLETED') for j in desired),terminal
    new_final=submit(['-t','00:10:00','--dependency=afterok:'+':'.join(live),'-J','ce500-final-archive-recovery',
        '-o',str(out.parent.parent/'accounting'/cfg['experiment']/'final-archive-recovery-%j.out'),'slurm/ce500_finish.sbatch'])
    record['new_jobs'].append(new_final);record['replaced_final']=dict(old=old_final,new=new_final);save()
    backup=out/'formal_submission_before_timeout_recovery.json';assert not backup.exists()
    backup.write_text(json.dumps(read(out/'formal_submission.json'),indent=2)+'\n')
    (out/'final_bundle_submission_before_timeout_recovery.json').write_text(json.dumps(final,indent=2)+'\n')
    formal['recovery_jobs']=[recovery['resume_array']];formal['retired_auxiliary_jobs']=retired
    formal['full_audit_scope_retained_after_timeout']=True
    (out/'formal_submission.json').write_text(json.dumps(formal,indent=2)+'\n')
    final.update(final_bundle_job=new_final,expected_pre_final_jobs=186+1+len(retired),active_dependencies=live,
        original_cancelled_final_job=old_final,full_audit_scope_unchanged=True)
    (out/'final_bundle_submission.json').write_text(json.dumps(final,indent=2)+'\n')
    record.update(status='applied',retired_zero_runtime_auxiliary_jobs=retired,original_failed_learning_job_retained=True)
    save();print(json.dumps(record,indent=2))


if __name__=='__main__':main()
