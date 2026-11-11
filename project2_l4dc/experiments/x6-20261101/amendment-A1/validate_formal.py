"""Stdlib file/metadata validation; safe on login node. No matrix evaluation."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',required=True,type=Path)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--job',required=True)
    p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    assert a.job.isdigit() and not a.out.exists()
    cfg=a.release/'config-X6a-v2.json'
    config=json.loads(cfg.read_text(encoding='utf-8-sig'))
    raw=subprocess.check_output(['sacct','-X','-j',a.job,'-n','-P',
                                 '--format=JobID%48,State,ElapsedRaw,AllocTRES'],text=True)
    allocation=[]
    for line in raw.splitlines():
        values=line.split('|')
        if len(values)<4:continue
        job,state,elapsed,tres=values[:4];job=job.strip()
        assert job.split('_')[0]==a.job and '.' not in job
        assert state=='COMPLETED',f'{job}: {state}'
        allocation.append(dict(job=job,state=state,elapsed_seconds=int(elapsed),tres=tres))
    assert len(allocation)==40
    models=0;artifacts=0;stein=0;ce=0;transitions=0;seconds=[]
    for index,task in enumerate(config['formal_tasks']):
        folder=a.root/'formal'/('task-'+str(index))
        done=json.loads((folder/'DONE.json').read_text())
        assert done['status']=='COMPLETE' and done['task']==task
        for spec in task['cells']:
            cell=folder/(spec['family']+'-n'+str(spec['n']))
            receipt=json.loads((cell/'receipt.json').read_text())
            assert receipt['status']=='COMPLETE' and not receipt['timing_only']
            assert receipt['spec']==spec
            assert receipt['config_sha256']==sha(cfg)
            assert receipt['source_sha256']==sha(a.release/'estimation.py')
            assert receipt['engine_sha256']==sha(a.release/'frozen_engine.py')
            assert sha(cell/'model.npz')==receipt['model_sha256'];models+=1
            expected={(algorithm,N) for algorithm,budgets in [
                ('Stein',config['stein_blocks_by_n'][str(spec['n'])]),('CE',config['blocks'])]
                for N in budgets}
            assert {(r['algorithm'],r['N']) for r in receipt['rows']}==expected
            assert len(receipt['artifacts'])==len(expected)
            for artifact in receipt['artifacts']:
                path=cell/artifact['path']
                assert path.parent==cell and sha(path)==artifact['sha256']
                artifacts+=1
            for row in receipt['rows']:
                required=(row['N']+17)*config['horizon'][spec['family']] if row['algorithm']=='Stein' else row['N']+512
                assert row['actual_transitions']==required
                stein+=row['algorithm']=='Stein';ce+=row['algorithm']=='CE'
            transitions+=(max(config['stein_blocks_by_n'][str(spec['n'])])+17)*config['horizon'][spec['family']]
            transitions+=max(config['blocks'])+512
            seconds.append(receipt['seconds'])
    assert models==320 and artifacts==3520 and stein==1920 and ce==1600
    result=dict(status='COMPLETE_METADATA_AND_HASHES',formal_job=a.job,
        allocations=allocation,bundles=40,models=models,raw_estimates=artifacts,
        stein_prefixes=stein,ce_prefixes=ce,primitive_transitions=transitions,
        zero_learning_updates=True,evaluation_transitions=0,
        config_sha256=sha(cfg),source_sha256=sha(a.release/'estimation.py'),
        analysis_sha256=sha(a.release/'analyze_saved.py'),
        maximum_cell_seconds=max(seconds),scientific_matrix_validation='DEFERRED_TO_REPORT',
        checker_sha256=sha(Path(__file__)))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='allocations'}))


if __name__=='__main__':main()
