"""Verify legacy replay, then round-robin adaptive runs in eight-update chunks."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');tmp.replace(path)


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();cfg=json.loads(a.manifest.read_text());a.output.mkdir(parents=True,exist_ok=True)
    import msvcrt
    lock=(a.output/'pipeline.lock').open('a+b');lock.seek(0)
    if lock.read(1)==b'':lock.write(b'0');lock.flush()
    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    from historical_npg100 import identity
    ident=identity(a.manifest);base=Path(__file__).parent;status=a.output/'pipeline_status.json'
    save(status,dict(status='RUNNING',phase='verification',pid=os.getpid(),identity=ident))
    existing=json.loads((a.output/'verification.json').read_text()) if (a.output/'verification.json').exists() else {}
    if existing.get('status')!='PASS' or existing.get('identity')!=ident:
        with (a.output/'verify.log').open('ab') as log:
            result=subprocess.run([sys.executable,'-B',str(base/'historical_npg100.py'),'verify',
                '--manifest',str(a.manifest),'--output',str(a.output)],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            save(status,dict(status='FAILED_PREFLIGHT',exit_code=result.returncode,identity=ident));raise SystemExit(result.returncode)
    def priority(case):
        t=case['original_task']
        return (0 if t['r']==4 else 1,t['system_seed'],0 if case['benchmark']=='rank80' else 1,
                t.get('level',0),t['r'])
    order=sorted(cfg['tasks'],key=priority);started=time.monotonic();cycle=0
    while True:
        complete=[t['id'] for t in cfg['tasks'] if (a.output/'adaptive/raw'/f"case-{t['id']:03d}.json").exists()]
        if len(complete)==len(cfg['tasks']):break
        cycle+=1
        for case in order:
            if case['id'] in complete:continue
            save(status,dict(status='RUNNING',phase='learning',pid=os.getpid(),cycle=cycle,case=case,
                completed_adaptive=complete,planned_adaptive=len(cfg['tasks']),identity=ident,seconds=time.monotonic()-started))
            logpath=a.output/'logs'/f"case-{case['id']:03d}.log";logpath.parent.mkdir(parents=True,exist_ok=True)
            with logpath.open('ab') as log:
                result=subprocess.run([sys.executable,'-B',str(base/'historical_npg100.py'),'run',
                    '--manifest',str(a.manifest),'--output',str(a.output),'--case-id',str(case['id']),
                    '--max-stages',str(cfg['dispatch_chunk_updates'])],stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:
                save(status,dict(status='FAILED_RUN',case=case,exit_code=result.returncode,identity=ident));raise SystemExit(result.returncode)
            with (a.output/'report.log').open('ab') as log:
                result=subprocess.run([sys.executable,'-B',str(base/'historical_npg100_report.py'),
                    '--manifest',str(a.manifest),'--output',str(a.output)],stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:
                save(status,dict(status='FAILED_REPORT',exit_code=result.returncode,identity=ident));raise SystemExit(result.returncode)
    save(status,dict(status='COMPLETE',planned_adaptive=len(cfg['tasks']),completed_adaptive=complete,
        identity=ident,seconds=time.monotonic()-started))


if __name__=='__main__':main()
