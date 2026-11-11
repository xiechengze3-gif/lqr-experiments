"""Submit four saved-data audits and dependent aggregate; total upper exactly 8 SU."""
import datetime
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path
import actor_control as ops


def main():
    root=Path(__file__).resolve().parent
    assert root==ops.BASE/'releases/x10-20261106-b-report-v1'
    ops.verify(root)
    approval=json.loads((root/'report-approval.json').read_text())
    review=root/'CLAUDE_TASK_REPORT_authorized.md'
    assert ops.sha(review)==approval['review_sha256']
    assert approval['exact_report_heading'] in review.read_text(encoding='utf-8-sig')
    coverage_path=ops.OUT/'formal-v1/FORMAL_COVERAGE_v1.json'
    coverage=json.loads(coverage_path.read_text())
    assert ops.sha(coverage_path)==approval['formal_proof_sha256']
    assert coverage['bundles']==256 and coverage['paired_paths']==1280
    assert coverage['config_sha256']==ops.sha(root/'formal-config.json')==approval['formal_config_sha256']
    chain=json.loads((ops.OUT/'submissions/FORMAL_CHAIN_v1.json').read_text())
    for entry in chain['jobs']:
        states=ops.job_states(entry['job']);assert len(states)==32 and all(s[1]=='COMPLETED' for s in states)
    ops.require_x9_complete()
    own_queue=subprocess.check_output(['squeue','--me','-r','-h','-o','%i|%C|%j'],universal_newlines=True)
    own_rows=[line.split('|') for line in own_queue.splitlines() if line.strip()]
    # Count even pending X12 reservations conservatively. Four inspections may
    # run together; aggregate depends on all four. Never assume idle slots last.
    assert len(own_rows)+4<=64, 'Insufficient global64 reservation for report4.'
    assert all(row[2].startswith('x12-') for row in own_rows), 'Unknown own work: reconcile slots.'
    deadline=datetime.datetime(2026,11,9,0,0,tzinfo=datetime.timezone.utc)
    assert datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=3.5)<=deadline
    with (ops.OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=ops.OUT/'budget/ledger.json';ledger=json.loads(path.read_text())
        assert ledger['study']=='X10b' and ledger['requested_upper_cap_SU']==200
        assert ledger['cumulative_requested_SU']+8<=200+1e-9
        assert ledger['measured_forecast_actual_SU']<=160
        assert not any(r['stage']=='REPORT' for r in ledger['submissions']), 'Reconcile; never replay report chain.'
        assert not (ops.OUT/'report-v1').exists()
        # Four inspection jobs can overlap. Aggregate follows all four, total concurrency<=4.
        jobs=[];dependencies=[]
        for role,minutes in [('n72',90),('n48',90),('n36',90),('n24',90),('aggregate',120)]:
            name='x10-20261106-b-report-v1-'+role
            receipt=ops.OUT/'submissions'/(name+'.json');assert not receipt.exists()
            bound=minutes/60
            assert ledger['cumulative_requested_SU']+bound<=200+1e-9
            balance=subprocess.check_output(['myproject'],universal_newlines=True)
            account=next(line for line in balance.splitlines() if '|'+ops.ACCOUNT+'|' in line)
            assert float(account.split('|')[6].strip())>=bound
            command=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','--ntasks=1','--cpus-per-task=1',
                     '--mem=2048M','-t',str(minutes),'--array=0-0%1','-J',name,
                     '-o',str(ops.OUT/'logs'/(name+'-%A_%a.out'))]
            dependency=':'.join(dependencies) if role=='aggregate' else None
            if dependency:command.append('--dependency=afterok:'+dependency)
            command.append(str(root/('report-'+role+'.sbatch')))
            row=dict(id=name,stage='REPORT',role=role,experiment='X10b',job=None,
                     status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',command=command,epoch=time.time(),
                     requested_bound_SU=bound,dependency=dependency,approval=approval,release=str(root),
                     release_manifest_sha256=ops.sha(root/'SHA256SUMS'),balance_snapshot=balance,automatic_retries=0)
            ops.save(receipt,row);ledger['submissions'].append(row);ledger['cumulative_requested_SU']+=bound;ops.save(path,ledger)
            response=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
            row.update(returncode=response.returncode,stdout=response.stdout,stderr=response.stderr)
            if response.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',response.stdout.strip()):
                row.update(job=response.stdout.strip().split(';')[0],status='SUBMITTED')
            else:row['status']='RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
            ops.save(receipt,row);ledger['submissions'][-1]=row;ops.save(path,ledger)
            print(json.dumps(dict(role=role,status=row['status'],job=row['job'],requested_bound_SU=bound)),flush=True)
            assert row['status']=='SUBMITTED'
            if role!='aggregate':dependencies.append(row['job'])
            jobs.append(dict(role=role,job=row['job']))
        ledger['report_reserved_SU']=0;ops.save(path,ledger)
        target=ops.OUT/'submissions/REPORT_CHAIN_v1.json';assert not target.exists()
        result=dict(status='REPORT_CHAIN_SUBMITTED',jobs=jobs,requested_report_upper_SU=8,
                    cumulative_requested_upper_SU=ledger['cumulative_requested_SU'],actual_forecast_SU=ledger['measured_forecast_actual_SU'],
                    requested_upper_cap_SU=200,actual_forecast_cap_SU=160,global_concurrency=64,automatic_retries=0)
        ops.save(target,result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
