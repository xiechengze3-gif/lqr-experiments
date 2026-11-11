"""Conditional00:30 authorization:all formal complete -> frozen saved-data REPORT."""
import argparse
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path
import remote_ops as ops


def completed(jobs):
    text=subprocess.check_output(['sacct','-X','--array','-j',','.join(jobs),'-n','-P',
                                  '--format=JobID%48,State'],text=True)
    states={line.split('|')[0].strip():line.split('|')[1].strip() for line in text.splitlines() if line.strip()}
    for job,size in jobs.items():
        assert all(states.get(job+'_'+str(i))=='COMPLETED' for i in range(size))


def main():
    p=argparse.ArgumentParser();p.add_argument('--component',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent;assert root.parent==ops.BASE/'releases';ops.verify(root)
    config=json.loads((root/'formal-config.json').read_text());digest=ops.sha(root/'formal-config.json')
    approval=json.loads((root/'approval.json').read_text());plan=json.loads((root/'report-plan.json').read_text())
    assert approval['authorized_action']=='X6b REPORT_AFTER_COMPLETE'
    task=root/'CLAUDE_TASK_approved.md';assert ops.sha(task)==approval['task_sha256']
    text=task.read_text(encoding='utf-8-sig')
    assert approval['exact_quote'] in text and 'ACCEPTED' in approval['exact_quote']
    assert 'After all arrays complete, run' in text and 'the frozen REPORT' in text
    for name,value in config['scientific_sources'].items():assert ops.sha(root/name)==value
    proof_path=ops.OUT/'X6b/formal-v1/FORMAL_COMPLETE_v1.json'
    assert ops.sha(proof_path)==approval['formal_complete_sha256']
    proof=json.loads(proof_path.read_text());assert proof['status']=='COMPLETE_COVERAGE_COUNTS_SOURCES'
    assert proof['config_sha256']==digest and proof['counts']['tasks']==384 and proof['counts']['paired_paths']==1024
    component=next(j for j in plan['jobs'] if j['component']==a.component)
    assert component['cpus']==1 and component['memory_MiB']==2048 and component['tasks']==1
    assert component['wall_minutes']==(30 if a.component=='summary' else 90)
    receipt=ops.OUT/'submissions'/(root.name+'-'+a.component+'.json')
    with (ops.OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);assert not receipt.exists(),'No automatic replay; reconcile receipt.'
        ledger_path=ops.OUT/'budget/ledger.json';ledger=json.loads(ledger_path.read_text())
        bound=component['wall_minutes']/60
        assert ledger['cap_requested_SU']==400 and ledger['cumulative_requested_SU']+bound<=400
        prior=sum(r['requested_bound_SU'] for r in ledger['submissions'] if r['experiment']=='X6b' and r['stage']=='REPORT')
        assert prior+bound<=6.5+1e-9
        formal=[r for r in ledger['submissions'] if r['experiment']=='X6b' and r['stage']=='FORMAL']
        assert len(formal)==12 and all(r['status']=='SUBMITTED' for r in formal)
        assert all(r['approval']['formal_config_sha256']==digest for r in formal)
        completed({r['job']:32 for r in formal})
        if a.component=='summary':
            previous=[r for r in ledger['submissions'] if r['experiment']=='X6b' and r['stage']=='REPORT'
                      and r['plan']['component'].startswith('diagnostics-')]
            assert len(previous)==4 and {r['plan']['n'] for r in previous}==set(config['n_values'])
            assert all(r['status']=='SUBMITTED' for r in previous)
            completed({r['job']:1 for r in previous})
            for n in config['n_values']:
                validation=json.loads((ops.OUT/f'X6b/report-v1/diagnostics-n{n}/verification.json').read_text())
                assert validation['status']=='COMPLETE' and validation['source_sha256']==ops.sha(root/'analyze_actor.py')
                assert validation['config_sha256']==digest
        balance=subprocess.check_output(['myproject'],text=True)
        line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x)
        assert float(line.split('|')[6].strip())>=bound
        cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','--ntasks=1',
            '--cpus-per-task=1','--mem=2048M','-t',str(component['wall_minutes']),'--array=0-0%1',
            '-J',root.name+'-'+a.component,'-o',str(ops.OUT/'logs'/(root.name+'-'+a.component+'-%A_%a.out')),
            str(root/'run-report.sbatch'),a.component]
        row=dict(id=root.name+'-'+a.component,experiment='X6b',stage='REPORT',job=None,
            status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',epoch=time.time(),requested_bound_SU=bound,
            command=cmd,plan=component,approval=approval,release=str(root),
            release_manifest_sha256=ops.sha(root/'SHA256SUMS'),balance_snapshot=balance,automatic_retries=0)
        ops.save(receipt,row);ledger['submissions'].append(row);ledger['cumulative_requested_SU']+=bound
        ops.save(ledger_path,ledger)
        result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        row.update(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
        if result.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',result.stdout.strip()):
            row.update(job=result.stdout.strip().split(';')[0],status='SUBMITTED')
        else:row['status']='RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
        ops.save(receipt,row);ledger['submissions'][-1]=row;ops.save(ledger_path,ledger)
        print(json.dumps(row));assert row['status']=='SUBMITTED'


if __name__=='__main__':main()
