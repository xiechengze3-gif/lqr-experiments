"""Verify, measure, compute references, then start the full frozen queue."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def write(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');tmp.replace(path)


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();start=time.monotonic();script=Path(__file__).parent/'adaptive50_run.py'
    if (a.output/'benchmark.json').exists():
        shutil.copyfile(a.output/'benchmark.json',a.output/'benchmark-initial-preflight.json')
    for phase in ('verify','verify-resume','benchmark','reference','production'):
        write(a.output/'bootstrap_status.json',dict(status='RUNNING',phase=phase,pid=os.getpid(),seconds=time.monotonic()-start))
        if phase=='production':
            command=[sys.executable,'-B',str(script.parent/'adaptive50_pipeline.py'),'--manifest',str(a.manifest),'--output',str(a.output)]
        else:
            command=[sys.executable,'-B',str(script),phase,'--manifest',str(a.manifest),'--output',str(a.output)]
        with (a.output/f'{phase}.log').open('ab') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode!=0:
            write(a.output/'bootstrap_status.json',dict(status='FAILED',phase=phase,exit_code=result.returncode,
                log=str(a.output/f'{phase}.log'),seconds=time.monotonic()-start))
            raise SystemExit(result.returncode)
    write(a.output/'bootstrap_status.json',dict(status='COMPLETE',pid=os.getpid(),seconds=time.monotonic()-start))


if __name__=='__main__':main()
