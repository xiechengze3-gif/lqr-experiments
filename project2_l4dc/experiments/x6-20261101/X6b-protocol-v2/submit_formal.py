"""Immutable X6b formal array submission with explicit Claude acceptance.

No automatic retry; reserve the complete group's requested SU before sbatch.
"""
import argparse
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path
import remote_ops as ops


def main():
    p=argparse.ArgumentParser();p.add_argument('--group',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent;assert root.parent==ops.BASE/'releases';ops.verify(root)
    approved=json.loads((root/'approval.json').read_text())
    task=root/'CLAUDE_TASK_approved.md';assert ops.sha(task)==approved['task_sha256']
    quote=approved['exact_quote'];assert 'ACCEPTED' in quote and 'X6b' in quote
    assert quote in task.read_text(encoding='utf-8-sig') and approved['authorized_action']=='X6b FORMAL'
    config=json.loads((root/'formal-config.json').read_text());plan=json.loads((root/'formal-plan.json').read_text())
    assert config['status']=='FORMAL_FROZEN' and ops.sha(root/'formal-config.json')==plan['formal_config_sha256']
    assert plan['formal_requested_SU']+plan['prior_requested_SU']+plan['reserved_report_SU']<=400
    for name,digest in config['scientific_sources'].items():assert ops.sha(root/name)==digest
    group=next(g for g in config['formal_groups'] if g['id']==a.group)
    assert group['tasks']==32 and group['cpus']==1 and group['memory_MiB']==2048
    assert 1<=group['wall_minutes']<=720 and group['partition'] in ['short','medium']
    identifier=root.name+'-'+group['id'];receipt=ops.OUT/'submissions'/(identifier+'.json')
    with (ops.OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert not receipt.exists(),'Inspect the existing receipt; never replay sbatch.'
        ledger_path=ops.OUT/'budget/ledger.json';ledger=json.loads(ledger_path.read_text())
        bound=32*group['wall_minutes']/60;assert abs(bound-group['requested_bound_SU'])<1e-9
        assert ledger['cap_requested_SU']==400 and ledger['cumulative_requested_SU']+bound<=400
        prior=sum(r['requested_bound_SU'] for r in ledger['submissions']
                  if r['experiment']=='X6b' and r['stage']=='FORMAL')
        assert prior+bound<=plan['formal_requested_SU']+1e-8
        eq=json.loads((ops.OUT/'X6b/resource-v1/equivalence/equivalence.json').read_text())
        assert eq['status']=='PASS' and eq['actor_sha256']==config['scientific_sources']['actor_paths.py']
        assert ops.sha(ops.OUT/'X6b/population-v1/population.json')==config['population_result_sha256']
        for n in config['n_values']:
            proof=json.loads((ops.OUT/f'X6b/resource-v1/timing-n{n}/timing.json').read_text())
            assert proof['status']=='COMPLETE_RESOURCE_ONLY' and len(proof['rows'])==16
        balance=subprocess.check_output(['myproject'],text=True)
        line=next(x for x in balance.splitlines() if '|'+ops.ACCOUNT+'|' in x)
        assert float(line.split('|')[6].strip())>=bound
        cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p',group['partition'],'--ntasks=1',
             '--cpus-per-task=1','--mem=2048M','-t',str(group['wall_minutes']),
             '--array=0-31%'+str(group['concurrency']),'-J',identifier,
             '-o',str(ops.OUT/'logs'/(identifier+'-%A_%a.out')),str(root/'run.sbatch'),a.group]
        row=dict(id=identifier,experiment='X6b',stage='FORMAL',job=None,
            status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',epoch=time.time(),requested_bound_SU=bound,
            command=cmd,approval=approved,plan=dict(group,stage='FORMAL',experiment='X6b'),
            release=str(root),release_manifest_sha256=ops.sha(root/'SHA256SUMS'),
            balance_snapshot=balance,automatic_retries=0)
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
