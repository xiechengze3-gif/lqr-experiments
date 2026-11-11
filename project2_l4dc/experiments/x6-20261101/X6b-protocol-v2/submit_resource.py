"""Only the23:10-authorized resource PILOT, capped at4 requested SU."""
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path
import remote_ops as ops


def main():
    root=Path(__file__).resolve().parent;ops.verify(root)
    plan=json.loads((root/'job_plan.json').read_text())
    approved=json.loads((root/'approval.json').read_text())
    config=json.loads((root/'resolved-config.json').read_text())
    assert plan['experiment']=='X6b' and plan['stage']=='PILOT'
    assert plan['cpus']==1 and plan['memory_MiB']==2048 and 1<=plan['wall_minutes']<=120
    assert approved['experiment']=='X6b' and approved['accepted_stage']=='PROTOCOL'
    task=root/'CLAUDE_TASK_approved.md'
    assert ops.sha(task)==approved['task_sha256']
    quote=approved['exact_quote'];assert 'ACCEPTED' in quote and 'X6b' in quote
    assert quote in task.read_text(encoding='utf-8-sig')
    assert ops.sha(root/'PROTOCOL_SHA256SUMS')==approved['protocol_manifest_sha256']
    population=ops.OUT/'X6b/population-v1/population.json'
    assert ops.sha(population)==config['population_result_sha256']
    p=json.loads(population.read_text());assert p['status']=='POPULATION_READY'
    assert p['population']['selected_T']==dict(NPG=config['selected_NPG_T'],PI=config['selected_PI_T'])
    receipt=ops.OUT/'submissions'/(plan['id']+'.json')
    with (ops.OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert not receipt.exists(),'No automatic replay; reconcile the existing receipt.'
        ledger_path=ops.OUT/'budget/ledger.json';ledger=json.loads(ledger_path.read_text())
        bound=plan['wall_minutes']/60
        assert ledger['cap_requested_SU']==400 and ledger['cumulative_requested_SU']+bound<=400
        prior=sum(r['requested_bound_SU'] for r in ledger['submissions']
                  if r['experiment']=='X6b' and r['stage']=='PILOT')
        assert prior+bound<=4
        if plan['component']!='equivalence':
            proof=json.loads((ops.OUT/'X6b/resource-v1/equivalence/equivalence.json').read_text())
            assert proof['status']=='PASS' and proof['actor_sha256']==ops.sha(root/'actor_paths.py')
            assert proof['source_sha256']==ops.sha(root/'resource_actor.py')
            eq=[r for r in ledger['submissions'] if r['experiment']=='X6b'
                and r['stage']=='PILOT' and r['plan']['component']=='equivalence' and r.get('job')]
            assert len(eq)==1
            states=subprocess.check_output(['sacct','-X','-j',str(eq[0]['job']),'-n','-P','--format=State'],text=True)
            parsed=[line.split('|')[0].strip() for line in states.splitlines() if line.strip()]
            assert parsed and all(state=='COMPLETED' for state in parsed)
        balance=subprocess.check_output(['myproject'],text=True)
        line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x)
        assert float(line.split('|')[6].strip())>=bound
        cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','--ntasks=1',
            '--cpus-per-task=1','--mem=2048M','-t',str(plan['wall_minutes']),
            '--array=0-0%1','-J',plan['id'],
            '-o',str(ops.OUT/'logs'/(plan['id']+'-%A_%a.out')),str(root/'run.sbatch')]
        row=dict(id=plan['id'],experiment='X6b',stage='PILOT',job=None,
            status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',epoch=time.time(),
            requested_bound_SU=bound,command=cmd,approval=approved,plan=plan,
            release=str(root),release_manifest_sha256=ops.sha(root/'SHA256SUMS'),
            balance_snapshot=balance,automatic_retries=0)
        ops.save(receipt,row);ledger['submissions'].append(row)
        ledger['cumulative_requested_SU']+=bound;ops.save(ledger_path,ledger)
        result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        row.update(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
        if result.returncode==0 and re.fullmatch(r'\d+(;[^\s]+)?',result.stdout.strip()):
            row.update(job=result.stdout.strip().split(';')[0],status='SUBMITTED')
        else:row['status']='RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
        ops.save(receipt,row);ledger['submissions'][-1]=row;ops.save(ledger_path,ledger)
        print(json.dumps(row));assert row['status']=='SUBMITTED'


if __name__=='__main__':main()
