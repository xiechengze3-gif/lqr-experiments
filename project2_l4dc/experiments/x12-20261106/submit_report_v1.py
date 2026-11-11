"""Once-only bounded X12 saved-data report, after all 64 formal allocations."""
import datetime,fcntl,json,re,subprocess
from pathlib import Path
import remote_followon_v1 as ops
def main():
    root=Path(__file__).resolve().parent
    assert root==ops.B/'releases/x12-20261106-report-v1';ops.verify(root)
    gate=ops.load(root/'gate.json');assert gate['status']=='ALL_PILOT_COST_GATES_PASS'
    assert gate['actual_forecast_SU']<=230 and gate['requested_upper_SU']<=300
    coverage=ops.load(root/'FORMAL_COVERAGE_v1.json')
    assert coverage['status']=='FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS' and coverage['bundles']==64 and coverage['paired_paths']==576
    assert coverage['config_sha256']==ops.sha(root/'formal-config.json')
    assert ops.sha(ops.O/'formal-v1/FORMAL_COVERAGE_v1.json')==ops.sha(root/'FORMAL_COVERAGE_v1.json')
    assert not (ops.O/'report-v1').exists()
    dest=ops.O/'submissions/followon-report-v1';assert not dest.exists(),'Prior attempt; never replay.'
    jobs=[dict(role='inspect-n60',tasks=1,partition='medium',wall_minutes=180,requested_SU=3,script='report-inspect.sbatch'),
          dict(role='aggregate',tasks=1,partition='medium',wall_minutes=300,requested_SU=5,script='report-aggregate.sbatch')]
    with (ops.O/'followon-submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        lp,d=ops.ledger();prior=ops.require_complete(d);ops.empty_queue()
        assert abs(d['cumulative_requested_SU']+8-gate['requested_upper_SU'])<1e-8
        assert d['cumulative_requested_SU']+8<=300
        dest.mkdir();ops.save(dest/'PREFLIGHT.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            prior_allocations=prior,prior_ledger_sha256=ops.sha(lp),coverage_sha256=ops.sha(root/'FORMAL_COVERAGE_v1.json'),
            requested_report_SU=8,own_queue_empty=True,new_training_transitions=0,automatic_retries=0))
        submitted=[];dependency=None
        for spec in jobs:
            name='x12-report-v1-'+spec['role'];money=ops.balance(spec['requested_SU'])
            assert 'State=UP' in ops.call(['scontrol','show','partition','medium','-o'])
            assert not ops.call(['sacct','-X','--array','-n','-P','-u','changze','-S','2026-11-06T00:00:00','--name='+name,'--format=JobID']).strip()
            command=['sbatch','--parsable','--account='+ops.ACCOUNT,'--partition=medium','--ntasks=1','--cpus-per-task=1','--mem=2048M',
                     '--time='+str(spec['wall_minutes']),'--no-requeue','--job-name='+name,'--output='+str(ops.O/'logs'/(name+'-%j.out'))]
            if dependency:command.append('--dependency=afterok:'+dependency)
            command.append(str(root/spec['script']))
            row=dict(spec,stage='report',job=None,status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',command=command,cpus=1,memory_MiB=2048,
                     release=str(root),balance_snapshot=money,dependency=dependency)
            ops.save(dest/(spec['role']+'-BEGIN.json'),row)
            d=dict(d,allocations=d['allocations']+[row],cumulative_requested_SU=d['cumulative_requested_SU']+spec['requested_SU'],
                   report_reserved_SU=5 if dependency is None else 0)
            lp,d=ops.nextledger(lp,d)
            response=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            result=dict(row,returncode=response.returncode,stdout=response.stdout,stderr=response.stderr)
            ops.save(dest/(spec['role']+'-RESPONSE.json'),result)
            assert response.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',response.stdout.strip()),'Uncertain/rejected sbatch; stop, never replay.'
            dependency=response.stdout.strip().split(';')[0];result.update(job=dependency,status='SUBMITTED_ONCE')
            ops.save(dest/(spec['role']+'-SUBMITTED.json'),result)
            d=dict(d,allocations=d['allocations'][:-1]+[result]);lp,d=ops.nextledger(lp,d);submitted.append(result)
            print(json.dumps(dict(status='SUBMITTED_ONCE',stage='report',role=spec['role'],job=dependency,requested_SU=spec['requested_SU'])),flush=True)
        result=dict(status='X12_REPORT_SUBMITTED_ONCE',jobs=submitted,requested_upper_SU=d['cumulative_requested_SU'],
                    requested_cap_SU=300,original_actual_forecast_SU=gate['actual_forecast_SU'],actual_forecast_cap_SU=230,
                    new_training_transitions=0,automatic_retries=0)
        ops.save(dest/'DONE.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
