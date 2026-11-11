"""Rebuild only the cancelled own report pipeline after full150-task coverage."""
import argparse
import json
from pathlib import Path
import subprocess
import time


def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--submit',action='store_true')
    p.add_argument('--queue-after-recoveries',action='store_true')
    p.add_argument('--retry-rejected-empty',action='store_true')
    a=p.parse_args();cfg=read(a.manifest);out=Path(cfg['output']);release=a.manifest.resolve().parents[1]
    formal=read(out/'submission-formal.json');pilot=read(out/'submission-pilot.json');prep=read(out/'submission-preflight.json')
    ids=[prep['job']]+list(pilot['jobs'].values())+list(formal['jobs'].values());recovery_ids=[]
    for path in out.glob('submission-recovery-*.json'):
        rr=read(path)
        if 'cases' not in rr:continue
        assert rr['status']=='submitted';recovery_ids+=list(rr['jobs'].values())
    ids+=recovery_ids
    ledger=subprocess.check_output(['sacct','-j',','.join(ids),'-X','-n','-P','-o','JobIDRaw,JobID,State,ElapsedRaw,AllocCPUS'],text=True)
    (out/'accounting/before-final-pipeline.psv').write_text(ledger)
    rows=[s.split('|') for s in ledger.splitlines() if s.strip()]
    terminal=('COMPLETED','TIMEOUT','CANCELLED','FAILED','OUT_OF_MEMORY')
    assert all(q[2] in terminal or (a.queue_after_recoveries and q[1].split('_')[0] in recovery_ids and q[2] in ('RUNNING','PENDING','COMPLETING')) for q in rows),'Wait for original attempts to finish'
    assert all(q[2]=='COMPLETED' or (a.queue_after_recoveries and q[2] in ('RUNNING','PENDING','COMPLETING')) for q in rows if q[1].split('_')[0] in recovery_ids),'Inspect failed recovery; do not replay'
    old_pipeline=[formal['jobs'][k] for k in ('formal_audits','formal_report','archive')]
    assert all(q[2]=='CANCELLED' for q in rows if q[1].split('_')[0] in old_pipeline)
    ident=read(out/'verification.json')['identity'];plan=read(out/'formal_plan.json');coverage=[];pending=[]
    recovery_tasks={c['task']:c for path in out.glob('recovery-plan-*.json') for c in read(path)['cases']}
    for rank in cfg['ranks']:
        for seed in cfg['confirm_seeds']:
            stem=f'ce-r{rank:03d}-s{seed:04d}';rawpath=out/'raw'/(stem+'.json')
            if rawpath.exists():
                raw=read(rawpath);assert raw['identity']==ident and raw['budgets']==plan['budgets_by_rank'][str(rank)]
                assert len(raw['records'])==2*len(raw['budgets'])
                assert (out/'estimates'/(stem+'.npz')).exists() and (out/'checkpoints'/(stem+'.npz')).exists()
            else:
                task=cfg['ranks'].index(rank)*30+cfg['confirm_seeds'].index(seed)
                assert a.queue_after_recoveries and task in recovery_tasks
                c=recovery_tasks[task];assert c['rank']==rank and c['seed']==seed and (out/'checkpoints'/(stem+'.npz')).exists()
                pending.append([rank,seed])
            coverage.append([rank,seed])
    spent=sum(int(q[3])*int(q[4])/3600 for q in rows)
    remaining=6*.5+.25+1/3
    active_parents={q[1].split('_')[0] for q in rows if q[2] not in terminal}
    active_recovery_bound=sum(read(Path(q['plan']))['reserved_recovery_SU'] for path in out.glob('submission-recovery-*.json') if 'plan' in (q:=read(path)) and any(j in active_parents for j in q['jobs'].values()))
    bound=spent+remaining+active_recovery_bound+.25
    assert len(coverage)==150 and bound<60,(spent,bound)
    result=dict(status='ready',filename='submission-recovery-final-pipeline.json',jobs={},epoch=time.time(),coverage=coverage,
        retained_cancelled_original_pipeline=old_pipeline,recovery_jobs=recovery_ids,
        all_original_attempts_terminal=True,all_recoveries_terminal=not bool(active_parents),
        scientific_outputs_pending_afterok_recoveries=pending,
        full150_runtime_coverage_required_by_audits=True,active_recovery_wall_bound_SU=active_recovery_bound,
        measured_allocated_core_hours_before_pipeline=spent,
        pipeline_wall_limit_SU=remaining,total_worst_case_SU_bound=bound,total_SU_cap=60,
        reason='Original dependents were cancelled by Slurm after predecessor timeouts. Rebuild only these own audits/report/archive, with complete150-task planned coverage and afterok dependencies on all recoveries; audits require every final output.')
    if not a.submit:print(json.dumps(result,indent=2));return
    receipt=out/result['filename']
    if receipt.exists():
        assert a.retry_rejected_empty and read(receipt)['jobs']=={},'Inspect existing pipeline receipt before replay'
        names='ce500-eqm-audit-final,ce500-eqm-report-final,ce500-eqm-archive-final'
        found=subprocess.check_output(['sacct','-u','changze','-S','2026-10-20','-X','-n','-P','--name',names,'-o','JobID,State'],text=True)
        assert not found.strip(),'A job may have been submitted; do not replay'
        history=out/'accounting/final-pipeline-rejected-dependency.json';assert not history.exists()
        previous=read(receipt);previous['failure']='Slurm rejected afterok references to completed jobs no longer retained by scheduler; no job ID returned; sacct and squeue verified no new report pipeline.';write(history,previous)
    write(receipt,result)
    def submit(key,args):
        job=subprocess.check_output(['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short','--exclude=c136,c294']+args,cwd=release,text=True).strip()
        assert job.isdigit();result['jobs'][key]=job;write(receipt,result);return job
    dependencies=['--dependency=afterok:'+':'.join(sorted(active_parents))] if active_parents else []
    audit=submit('formal_audits',['-t','30','--array=0-5%6']+dependencies+['-J','ce500-eqm-audit-final',
        '-o',str(out/'logs/audit-%A_%a.out'),'slurm/ce500_equal_modes.sbatch','audit-shard'])
    report=submit('formal_report',['-t','15','--dependency=afterok:'+audit,'-J','ce500-eqm-report-final',
        '-o',str(out/'logs/confirm-report-%j.out'),'slurm/ce500_equal_modes_final_report.sbatch'])
    submit('archive',['-t','20','--dependency=afterok:'+report,'-J','ce500-eqm-archive-final',
        '-o',str(out/'logs/archive-%j.out'),'slurm/ce500_equal_modes_archive.sbatch'])
    result['status']='submitted';write(receipt,result);print(json.dumps({k:v for k,v in result.items() if k!='coverage'},indent=2))


if __name__=='__main__':main()
