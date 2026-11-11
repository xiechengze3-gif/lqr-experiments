"""One worker, stage checkpoints, automatic incremental/final reports."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from adaptive50_run import identity, sha
from dense_scaling import atomic_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();cfg=json.loads(a.manifest.read_text());ident=identity(a.manifest)
    import msvcrt
    lock=(a.output/'pipeline.lock').open('a+b');lock.seek(0)
    if lock.read(1)==b'':lock.write(b'0');lock.flush()
    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    verification=json.loads((a.output/'verification.json').read_text())
    resume=json.loads((a.output/'resume_validation.json').read_text())
    bench=json.loads((a.output/'benchmark.json').read_text())
    assert verification['status']=='PASS' and resume['status']=='PASS' and bench['status']=='COMPLETE'
    assert verification['identity']==resume['identity']==bench['identity']==ident
    script=Path(__file__).parent/'adaptive50_run.py'
    report_script=Path(__file__).parent/'adaptive50_report.py'
    start=time.monotonic();done=[];failed=[]
    # Round robin through algorithms per system/initialization, so early reports
    # contain all four routes instead of finishing one route's entire grid first.
    for task in cfg['tasks']:
        for algorithm in cfg['algorithms']:
            final=a.output/algorithm/'raw'/f"task-{task['id']:03d}.json"
            if final.exists():done.append(dict(task_id=task['id'],algorithm=algorithm,reused=True));continue
            atomic_json(a.output/'pipeline_status.json',dict(status='RUNNING',pid=os.getpid(),
                task_id=task['id'],algorithm=algorithm,completed=done,infrastructure_failures=failed,
                seconds=time.monotonic()-start,identity=ident))
            log=a.output/'logs'/f"{algorithm}-{task['id']:03d}.log";log.parent.mkdir(parents=True,exist_ok=True)
            with log.open('ab') as stream:
                result=subprocess.run([sys.executable,'-B',str(script),'run','--manifest',str(a.manifest),
                    '--output',str(a.output),'--task-id',str(task['id']),'--algorithm',algorithm],
                    stdout=stream,stderr=subprocess.STDOUT)
            if result.returncode==0 and final.exists():done.append(dict(task_id=task['id'],algorithm=algorithm))
            else:failed.append(dict(task_id=task['id'],algorithm=algorithm,exit_code=result.returncode,log=str(log)))
            with (a.output/'report.log').open('ab') as stream:
                subprocess.run([sys.executable,'-B',str(report_script),'--manifest',str(a.manifest),
                    '--output',str(a.output)],stdout=stream,stderr=subprocess.STDOUT)
    atomic_json(a.output/'pipeline_status.json',dict(status='COMPLETE' if not failed else 'INFRASTRUCTURE_FAILURES',
        pid=os.getpid(),completed=done,infrastructure_failures=failed,seconds=time.monotonic()-start,identity=ident))
    print(json.dumps(dict(completed=len(done),infrastructure_failures=len(failed))),flush=True)


if __name__=='__main__':main()
