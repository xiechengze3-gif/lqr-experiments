"""Once-only conditionally approved X7 FORMAL/REPORT;stdlib control only."""
import argparse,fcntl,json,math,os,re,subprocess,tarfile,time
from pathlib import Path
import x7_resource_ops as ops


def completed(jobs):
    raw=subprocess.check_output(['sacct','-X','--array','-j',','.join(jobs),'-n','-P',
        '--format=JobID%48,State'],text=True)
    states={p[0]:p[1] for line in raw.splitlines() if len(p:=line.split('|'))>=2}
    for job,size in jobs.items():
        assert all(states.get(job+'_'+str(i))=='COMPLETED' for i in range(size))


def deploy(name,digest):
    assert re.fullmatch(r'x7-20261102-(formal|report)-v\d+',name)
    archive=ops.TMP/(name+'.tar.gz');target=ops.BASE/'releases'/name
    assert ops.sha(archive)==digest and not target.exists()
    with tarfile.open(archive,'r:gz') as tf:
        members=tf.getmembers()
        assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
        target.mkdir();tf.extractall(target,members=members)
    ops.verify(target)
    print(json.dumps(dict(status='DEPLOYED_VERIFIED',name=name,archive_sha256=digest)))


def submit(root,stage,component=None):
    root=Path(root).resolve()
    assert os.getuid()==31181 and root.parent==ops.BASE/'releases'
    ops.verify(root)
    approval=json.loads((root/'approval.json').read_text())
    task=root/'CLAUDE_TASK_approved.md';text=task.read_text(encoding='utf-8-sig')
    assert ops.sha(task)==approval['task_sha256'] and approval['exact_quote'] in text
    assert all(word in approval['exact_quote'] for word in ['X7','PROTOCOL','ACCEPTED'])
    cfg=json.loads((root/'formal-config.json').read_text())
    assert cfg['status']=='FORMAL_FROZEN' and cfg['cap_requested_SU']==15
    for name,digest in cfg['scientific_sources'].items():assert ops.sha(root/name)==digest,name
    baseline=json.loads((root/'config-protocol-v1.json').read_text())
    allowed={'stage','status','parent_protocol_config_sha256','resource_complete_sha256','model_registry'}
    assert {k:v for k,v in cfg.items() if k not in allowed}=={k:v for k,v in baseline.items() if k not in allowed}
    assert cfg['parent_protocol_config_sha256']==ops.sha(root/'config-protocol-v1.json')
    protocol=json.loads((root/'PROTOCOL_MANIFEST.json').read_text())
    assert ops.sha(root/'PROTOCOL_SHA256SUMS')==protocol['manifest_sha256']
    for name,digest in protocol['files'].items():assert ops.sha(root/name)==digest,name
    pilot_path=ops.OUT/'resource-v1/RESOURCE_COMPLETE_v1.json'
    assert ops.sha(pilot_path)==cfg['resource_complete_sha256']==approval['resource_proof_sha256']
    pilot=json.loads(pilot_path.read_text())
    assert pilot['status']=='COMPLETE_RESOURCE_ONLY' and pilot['zero_performance_readout']
    assert all(v==1. for v in pilot['effective_billing_cores'])
    assert cfg['model_registry']==pilot['model_registry'] and len(cfg['model_registry'])==32
    for model in cfg['model_registry'].values():assert ops.sha(model['path'])==model['sha256']
    if stage=='FORMAL':
        assert approval['authorized_action']=='X7_FORMAL_CONDITIONAL'
        assert 'FORMAL is ACCEPTED in advance IF' in text and '<= 12 SU' in text and 'RSS headroom >= 20%' in text
        plan=json.loads((root/'formal-plan.json').read_text())
        assert plan['formal_config_sha256']==ops.sha(root/'formal-config.json')
        assert plan['tasks']==32 and plan['concurrency']==8 and plan['cpus']==1 and plan['memory_MiB']==2048
        maximum=max(row['maximum_RSS_KiB'] for row in pilot['cases'])
        worst=sum(row['worst_full_path_seconds'] for row in pilot['cases'])
        assert maximum<=.8*2048*1024
        assert plan['wall_minutes']==math.ceil((1.3*worst+60)/60)
        bound=32*plan['wall_minutes']/60
        assert bound==plan['requested_bound_SU'] and bound<=12
        tasks=32;concurrency=8;minutes=plan['wall_minutes'];identifier=root.name
        run=[str(root/'run-formal.sbatch')]
    else:
        assert stage=='REPORT' and approval['authorized_action']=='X7_REPORT_AFTER_FORMAL'
        assert 'REPORT (<= 2 SU) is ACCEPTED' in text
        coverage_path=ops.OUT/'formal-v1/FORMAL_COMPLETE_v1.json'
        assert ops.sha(coverage_path)==approval['formal_complete_sha256']
        coverage=json.loads(coverage_path.read_text())
        assert coverage['status']=='COMPLETE_COVERAGE_COUNTS_SOURCES'
        assert coverage['counts']==dict(tasks=32,paths=128,outputs=10752,
            fit_policy_archives=768,primitive_transitions=37814272)
        assert coverage['config_sha256']==ops.sha(root/'formal-config.json')
        report_plan=json.loads((root/'report-plan.json').read_text())
        plan=next(p for p in report_plan['jobs'] if p['component']==component)
        assert plan['cpus']==1 and plan['memory_MiB']==2048 and plan['tasks']==1
        tasks=1;concurrency=1;minutes=plan['wall_minutes'];bound=minutes/60
        assert minutes==(40 if component=='summary' else 20)
        identifier=root.name+'-'+component
        run=[str(root/'run-report.sbatch'),component]
    receipt=ops.OUT/'submissions'/(identifier+'.json')
    with (ops.OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert not receipt.exists(),'Reconcile existing receipt;never replay.'
        ledger_path=ops.OUT/'budget/ledger.json';ledger=json.loads(ledger_path.read_text())
        assert ledger['study']=='X7' and ledger['cap_requested_SU']==15
        assert ledger['cumulative_requested_SU']+bound<=15
        resource=[r for r in ledger['submissions'] if r['stage']=='PILOT']
        assert len(resource)==1 and resource[0]['status']=='SUBMITTED' and resource[0]['job']==pilot['job']
        completed({pilot['job']:4})
        if stage=='FORMAL':
            assert not any(r['stage']=='FORMAL' for r in ledger['submissions'])
            assert ledger['cumulative_requested_SU']+bound+2<=15
        else:
            formal=[r for r in ledger['submissions'] if r['stage']=='FORMAL']
            assert len(formal)==1 and formal[0]['status']=='SUBMITTED'
            completed({formal[0]['job']:32})
            reports=[r for r in ledger['submissions'] if r['stage']=='REPORT']
            assert sum(r['requested_bound_SU'] for r in reports)+bound<=2+1e-9
            if component=='summary':
                diagnostic=[r for r in reports if r['plan']['component'].startswith('diagnostics-')]
                assert len(diagnostic)==4 and all(r['status']=='SUBMITTED' for r in diagnostic)
                completed({r['job']:1 for r in diagnostic})
                for n in cfg['n_values']:
                    for spectrum in cfg['spectra']:
                        proof=json.loads((ops.OUT/f'report-v1/diagnostics-n{n}-{spectrum}/verification.json').read_text())
                        assert proof['status']=='COMPLETE'
                        assert proof['source_sha256']==cfg['scientific_sources']['analyze_ce.py']
                        assert proof['config_sha256']==ops.sha(root/'formal-config.json')
        balance=subprocess.check_output(['myproject'],text=True)
        line=next(v for v in balance.splitlines() if '|'+ops.ACCOUNT+'|' in v)
        assert float(line.split('|')[6].strip())>=bound
        cmd=['sbatch','--parsable','-A',ops.ACCOUNT,'-p','short','--ntasks=1',
            '--cpus-per-task=1','--mem=2048M','-t',str(minutes),
            '--array=0-'+str(tasks-1)+'%'+str(concurrency),'-J',identifier,
            '-o',str(ops.OUT/'logs'/(identifier+'-%A_%a.out'))]+run
        row=dict(id=identifier,experiment='X7',stage=stage,job=None,
            status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY',epoch=time.time(),
            requested_bound_SU=bound,plan=plan,command=cmd,approval=approval,
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


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    d=sub.add_parser('deploy');d.add_argument('name');d.add_argument('sha256')
    f=sub.add_parser('submit-formal');f.add_argument('release',type=Path)
    r=sub.add_parser('submit-report');r.add_argument('release',type=Path);r.add_argument('--component',required=True)
    a=p.parse_args()
    if a.action=='deploy':deploy(a.name,a.sha256)
    elif a.action=='submit-formal':submit(a.release,'FORMAL')
    else:submit(a.release,'REPORT',a.component)
