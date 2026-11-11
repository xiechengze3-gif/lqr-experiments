"""Execute a reviewed subset of an immutable calibration manifest.

Reuses the identical frozen collector/actor functions and original provenance.
Subset selection and runner provenance are recorded separately, so completed
scientific records are never relabeled as a different experiment.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
import psutil
import numpy as np

PROJECT=Path(os.environ['LQR_PROJECT_ROOT'])
FROZEN=PROJECT/'local_runs'/'npg300-20261009'
sys.path.insert(0,str(FROZEN))
from npg_300_local_study import actor, critic, provenance, sha, atomic_json, require_compute
from npg_300_local_report import report


def run(out):
    out=Path(out);scope_path=out/'active_scope.json';scope=json.loads(scope_path.read_text())
    cfg_path=out/'config.json';cfg=json.loads(cfg_path.read_text());identity=provenance(cfg_path)
    assert scope['config_sha256']==identity['config_sha256']
    assert scope['worker_sha256']==identity['runner_sha256']
    checked=json.loads((out/'resume_check'/identity['runner_sha256'][:16]/'verification.json').read_text())
    assert checked['status']=='PASS' and checked['runner_sha256']==identity['runner_sha256']
    assert json.loads((out/'feasibility'/'feasibility.json').read_text())['status']=='PASS'
    scope_identity=dict(scope_sha256=sha(scope_path),scope_runner_sha256=sha(__file__),**identity)
    lock=out/'worker.lock.json';proc=psutil.Process()
    if lock.exists():
        old=json.loads(lock.read_text())
        try:
            previous=psutil.Process(old['pid'])
            if previous.is_running() and abs(previous.create_time()-old['created'])<1:
                raise RuntimeError('A calibration worker is already running.')
        except psutil.NoSuchProcess:pass
        lock.unlink()
    with lock.open('x') as stream:json.dump(dict(pid=os.getpid(),created=proc.create_time()),stream)
    begin=time.monotonic();completed=[]
    try:
        for index in scope['task_ids']:
            task=cfg['tasks'][index];target=out/task['phase']/f'task-{index:03d}'
            atomic_json(out/'study_progress.json',dict(status='RUNNING',scope=scope['name'],
                completed_tasks=completed,total_tasks=len(scope['task_ids']),active_task_id=index,
                active_task=task,pid=os.getpid(),elapsed_seconds=time.monotonic()-begin,**scope_identity))
            path=target/'result.json'
            if path.exists():
                old=json.loads(path.read_text())
                checked=old['identity'] if task['phase']=='critic' else {k:old[k] for k in identity}
                assert checked==identity
            elif task['phase']=='critic':critic(task,cfg['critic_prefixes'],target,identity)
            else:actor(task,cfg['schedules'][task['profile']],target,identity)
            completed.append(index)
            atomic_json(out/'study_progress.json',dict(status='RUNNING',scope=scope['name'],
                completed_tasks=completed,total_tasks=len(scope['task_ids']),latest_task=task,
                pid=os.getpid(),elapsed_seconds=time.monotonic()-begin,**scope_identity))
            report(out)
        atomic_json(out/'study_progress.json',dict(status='COMPLETE',scope=scope['name'],
            completed_tasks=completed,total_tasks=len(scope['task_ids']),
            elapsed_seconds=time.monotonic()-begin,**scope_identity))
        print('LOCAL_SCOPED_CALIBRATION_COMPLETE',flush=True)
    except Exception as exc:
        atomic_json(out/'study_progress.json',dict(status='FAILED',scope=scope['name'],error=str(exc),
            completed_tasks=completed,total_tasks=len(scope['task_ids']),pid=os.getpid(),**scope_identity))
        raise
    finally:lock.unlink(missing_ok=True)


if __name__=='__main__':
    require_compute();parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    run(parser.parse_args().output)
