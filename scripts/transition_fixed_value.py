"""Stop only the superseded, checkpointed 50d process tree; preserve artifacts."""
import argparse
import json
import os
import time
from pathlib import Path
import psutil


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');tmp.replace(path)


def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True)
    p.add_argument('--release',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--script-names',nargs='+',default=['adaptive50_pipeline.py','adaptive50_bootstrap.py','adaptive50_run.py'])
    p.add_argument('--new-manifest',default='configs/fixed_value_suite.json')
    p.add_argument('--reason',default='User requested fixed-budget value comparison and broader controlled cases.')
    p.add_argument('--replacement-status',default='REPLACED_BY_FIXED_VALUE_PROTOCOL')
    a=p.parse_args();study=str(a.study.resolve()).replace('\\','/').lower()
    release=str(a.release.resolve()).replace('\\','/').lower()
    whitelist=set(a.script_names)
    targets=[]
    for proc in psutil.process_iter(['pid','cmdline']):
        try:
            if proc.pid==os.getpid():continue
            args=proc.info['cmdline'] or [];joined=' '.join(args).replace('\\','/').lower()
            scripts=[Path(arg).name for arg in args if arg.endswith('.py')]
            # Only the interpreter's first script argument is an entrypoint;
            # later --script-names arguments must never identify this helper.
            entrypoint=scripts[0] if scripts else None
            if study in joined and release in joined and entrypoint in whitelist:
                targets.append((proc,entrypoint,proc.create_time()))
        except (psutil.AccessDenied,psutil.NoSuchProcess):continue
    targets.sort(key=lambda x:0 if 'pipeline' in x[1] or 'bootstrap' in x[1] else 1)
    stopped=[]
    for proc,script,created in targets:
        try:
            # Guard against Windows PID reuse before terminating this specific process.
            if proc.create_time()!=created:raise RuntimeError('PID reused')
            proc.terminate();proc.wait(timeout=5)
            stopped.append(dict(pid=proc.pid,script=script,status='terminated'))
        except psutil.NoSuchProcess:stopped.append(dict(pid=proc.pid,script=script,status='already_exited'))
    path=a.study/'pipeline_status.json';status=json.loads(path.read_text())
    status.update(status=a.replacement_status,reason=a.reason,
                  stopped_processes=stopped,checkpoints_preserved=True)
    save(path,status)
    boot=a.study/'bootstrap_status.json'
    if boot.exists():
        previous=json.loads(boot.read_text())
        previous.update(status='STOPPED_FOR_PROTOCOL_CHANGE',reason=status['reason']);save(boot,previous)
    completed={algorithm:len(list((a.study/algorithm/'raw').glob('task-*.json')))
               for algorithm in ('CE','LSTD_PI','DIRECT_PI','NPG')}
    save(a.receipt,dict(status='TRANSITION_COMPLETE',old_study=str(a.study),stopped_processes=stopped,
        completed_preserved=completed,checkpoint_count=len(list(a.study.glob('*/checkpoints/*.npz'))),
        results_deleted=False,new_manifest=a.new_manifest))
    print(json.dumps(dict(status='TRANSITION_COMPLETE',stopped=len(stopped),completed_preserved=completed)))


if __name__=='__main__':main()
