"""Verify frozen sources, then execute fixed-budget comparisons and reports."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');tmp.replace(path)


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prioritize-npg',action='store_true')
    a=p.parse_args();cfg=json.loads(a.manifest.read_text());a.output.mkdir(parents=True,exist_ok=True)
    import msvcrt
    lock=(a.output/'pipeline.lock').open('a+b');lock.seek(0)
    if lock.read(1)==b'':lock.write(b'0');lock.flush()
    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    from fixed_value_run import identity
    ident=identity(a.manifest);runner=Path(__file__).parent/'fixed_value_run.py'
    reporter=Path(__file__).parent/'fixed_value_report.py';start=time.monotonic();done=[];failures=[]
    status_path=a.output/'pipeline_status.json'
    for phase in ('verify','reference'):
        save(status_path,dict(status='RUNNING',phase=phase,pid=os.getpid(),identity=ident))
        if phase=='verify' and (a.output/'verification.json').exists():
            proof=json.loads((a.output/'verification.json').read_text())
            if proof['status']=='PASS' and proof['identity']==ident:continue
        if phase=='reference' and (a.output/'population_reference.json').exists():
            proof=json.loads((a.output/'population_reference.json').read_text())
            if proof['status']=='COMPLETE' and proof['identity']==ident:continue
        with (a.output/f'{phase}.log').open('ab') as log:
            result=subprocess.run([sys.executable,'-B',str(runner),phase,'--manifest',str(a.manifest),
                '--output',str(a.output)],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode!=0:
            save(status_path,dict(status='FAILED_PREFLIGHT',phase=phase,exit_code=result.returncode,identity=ident))
            raise SystemExit(result.returncode)
    # Cover all cases at one seed first, before expanding independent systems/trials.
    priority=[0,2,6,5,7,4,3,1,8,9,10,11]
    order=sorted(cfg['tasks'],key=lambda t:(0 if t['profile']=='standard' and t['system_seed']==10 and t['trial_seed']==0 else 1,
        priority.index(t['scenario_index']),('standard','low','high').index(t['profile']),t['system_seed'],t['trial_seed']))
    algorithms=sorted(cfg['algorithms'],key=lambda alg:0 if alg=='NPG' else 1) if a.prioritize_npg else cfg['algorithms']
    for task in order:
        for algorithm in algorithms:
            final=a.output/algorithm/'raw'/f"task-{task['id']:03d}.json"
            if final.exists():
                existing=json.loads(final.read_text());assert existing['identity']==ident
                done.append(dict(task=task['id'],algorithm=algorithm,reused=True));continue
            save(status_path,dict(status='RUNNING',phase='learning',pid=os.getpid(),task=task,algorithm=algorithm,
                completed=done,infrastructure_failures=failures,seconds=time.monotonic()-start,identity=ident))
            log_path=a.output/'logs'/f"{algorithm}-{task['id']:03d}.log";log_path.parent.mkdir(parents=True,exist_ok=True)
            with log_path.open('ab') as log:
                result=subprocess.run([sys.executable,'-B',str(runner),'run','--manifest',str(a.manifest),
                    '--output',str(a.output),'--task-id',str(task['id']),'--algorithm',algorithm],stdout=log,stderr=subprocess.STDOUT)
            if result.returncode==0 and final.exists():done.append(dict(task=task['id'],algorithm=algorithm))
            else:failures.append(dict(task=task['id'],algorithm=algorithm,exit_code=result.returncode,log=str(log_path)))
            with (a.output/'report.log').open('ab') as log:
                result=subprocess.run([sys.executable,'-B',str(reporter),'--manifest',str(a.manifest),
                    '--output',str(a.output),'--scenario',task['scenario']],stdout=log,stderr=subprocess.STDOUT)
            if result.returncode!=0:failures.append(dict(phase='report',task=task['id'],exit_code=result.returncode))
    save(status_path,dict(status='COMPLETE' if not failures else 'INFRASTRUCTURE_FAILURES',pid=os.getpid(),
        completed=done,infrastructure_failures=failures,seconds=time.monotonic()-start,identity=ident))
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
