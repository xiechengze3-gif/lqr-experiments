"""Serial local calibration with paired raw/truncated NPG and atomic checkpoints.

The 5x2 calibration is exploratory. Exact values are diagnostics only, never
used by the learner to stop or allocate samples. Restarting replays at most
one unfinished actor stage / fixed-policy task; completed stages are reused.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get('LQR_PROJECT_ROOT', str(Path(__file__).resolve().parents[1])))
ENGINE = ROOT / 'local_runs' / 'npg300-20261009' / 'engine'
sys.path.insert(0, str(ENGINE))
import numpy as np
import psutil
from dense_scaling import atomic_json, evaluate, targets, eta, trunc, rng_for, require_compute
from npg_budget_system import system
from npg_batched_collector import collect


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance(config):
    return dict(config_sha256=sha(config),runner_sha256=sha(__file__),
                engine_sha256=sha(ENGINE/'dense_scaling.py'),
                system_sha256=sha(ENGINE/'npg_budget_system.py'),
                collector_sha256=sha(ENGINE/'npg_batched_collector.py'))


def save_checkpoint(path, states, rows, next_stage, identity):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    arrays = dict(next_stage=np.array(next_stage),identity=np.array(json.dumps(identity,sort_keys=True)),
                  rows=np.array(json.dumps(rows,allow_nan=False)))
    for method, state in states.items():
        for key in ('k','x','total','failed'):
            arrays[method+'_'+key] = np.asarray(state[key])
    with tmp.open('wb') as stream:
        np.savez(stream, **arrays)
    os.replace(tmp,path)


def actor(task, schedule, out, identity, max_stages=None, deadline=None):
    """Interleave the paired methods so both arms progress on each budget stage."""
    s=system(task); n=task['n']; checkpoint=Path(out)/'checkpoint.npz'
    states={m:dict(k=s['K0'].copy(),x=np.zeros(n),total=0,failed=False) for m in ('raw','truncated')}
    initial,_=evaluate(s,s['K0'])
    rows=[dict(method=m,stage=0,N=0,transitions=0,**initial) for m in states]
    first=0
    if checkpoint.exists():
        with np.load(checkpoint,allow_pickle=False) as data:
            assert json.loads(str(data['identity'])) == identity, 'Checkpoint provenance changed.'
            first=int(data['next_stage']); rows=json.loads(str(data['rows']))
            for m in states:
                states[m]=dict(k=data[m+'_k'].copy(),x=data[m+'_x'].copy(),
                               total=int(data[m+'_total']),failed=bool(data[m+'_failed']))
    finished=0
    for stage in range(first,len(schedule)):
        count=schedule[stage]; stage_start=time.monotonic()
        for method,state in states.items():
            if state['failed']:
                rows.append(dict(method=method,stage=stage+1,N=count,transitions=state['total'],
                                 observed=False,stable=False,gap=None))
                continue
            quality,p=evaluate(s,state['k']); true=targets(s,state['k'],16,p)
            _,x,z,_,gram,used=next(collect(s,state['k'],state['x'],[count],16,1.,
                rng_for(663897,n,task['system_seed'],task['trial_seed'],stage),burn=1024))
            assert used==1024+(count+1)*16
            estimate=z if method=='raw' else trunc(z,task['r'])
            error=estimate-true['Z']
            state['k']-=2*eta(s)*(s['R']@state['k']+estimate)
            state['x']=x;state['total']+=used
            updated,_=evaluate(s,state['k']);state['failed']=not updated['stable']
            rows.append(dict(method=method,stage=stage+1,N=count,transitions=state['total'],observed=True,
                before_gap=quality['gap'],critic_error_fro2=float(np.sum(error*error)),
                critic_error_op=float(np.linalg.norm(error,2)),gram_condition=float(np.linalg.cond(gram)),**updated))
        if task['r']==n:
            a,b=rows[-2:];assert a['stable']==b['stable']
            if a['stable']:np.testing.assert_allclose(a['gap'],b['gap'],rtol=1e-7,atol=1e-8)
        save_checkpoint(checkpoint,states,rows,stage+1,identity)
        progress=dict(task=task,status='RUNNING',completed_stages=stage+1,planned_stages=len(schedule),
            latest=rows[-2:],stage_seconds=time.monotonic()-stage_start,
            pid=os.getpid(),rss_bytes=psutil.Process().memory_info().rss,**identity)
        atomic_json(Path(out)/'progress.json',progress)
        print(json.dumps(progress),flush=True)
        finished+=1
        if max_stages is not None and finished>=max_stages: return None
        if deadline is not None and time.monotonic()>=deadline:
            raise TimeoutError('Runtime limit reached at a saved paired actor stage.')
    result=dict(task=task,status='COMPLETE',records=rows,diagnostics=s['diagnostics'],
        planned_total_transitions=sum(1024+(c+1)*16 for c in schedule),**identity)
    atomic_json(Path(out)/'result.json',result)
    return states


def critic(task, prefixes, out, identity):
    path=Path(out)/'result.json'
    if path.exists():
        old=json.loads(path.read_text()); assert old['identity']==identity;return
    s=system(task);quality,p=evaluate(s,s['K0']);truth=targets(s,s['K0'],16,p);rows=[]
    started=time.monotonic();diagnostic_seconds=0.
    for count,x,z,_,gram,used in collect(s,s['K0'],np.zeros(task['n']),prefixes,16,1.,
            rng_for(963000,task['n'],task['system_seed'],task['trial_seed']),burn=1024):
        elapsed=time.monotonic()-started-diagnostic_seconds;diag_start=time.monotonic()
        methods=[]
        for m,estimate in (('raw',z),('truncated',trunc(z,task['r']))):
            error=estimate-truth['Z'];update,_=evaluate(s,s['K0']-2*eta(s)*(s['R']@s['K0']+estimate))
            methods.append(dict(method=m,critic_error_fro2=float(np.sum(error*error)),
                                critic_error_op=float(np.linalg.norm(error,2)),one_update=update))
        if task['r']==task['n']:
            np.testing.assert_allclose(methods[0]['critic_error_fro2'],methods[1]['critic_error_fro2'],rtol=1e-12)
        rows.append(dict(N=count,primitive_transitions=used,collector_seconds=elapsed,
                         gram_condition=float(np.linalg.cond(gram)),methods=methods))
        atomic_json(Path(out)/'progress.json',dict(task=task,status='RUNNING',records=rows,identity=identity))
        print(json.dumps(dict(phase='critic',task=task,N=count,collector_seconds=elapsed)),flush=True)
        diagnostic_seconds+=time.monotonic()-diag_start
    atomic_json(path,dict(task=task,status='COMPLETE',records=rows,identity=identity,
                         diagnostics=s['diagnostics'],fixed_policy=True))


def selfcheck(out):
    task=dict(n=6,m=6,r=2,system_seed=17,trial_seed=3)
    identity=dict(test='resumed actor must equal uninterrupted actor',runner_sha256=sha(__file__))
    schedule=[512,1024,2048]
    full=actor(task,schedule,Path(out)/'full',identity)
    for _ in schedule:actor(task,schedule,Path(out)/'resumed',identity,max_stages=1)
    resumed=actor(task,schedule,Path(out)/'resumed',identity)
    for method in full:
        np.testing.assert_array_equal(full[method]['k'],resumed[method]['k'])
        np.testing.assert_array_equal(full[method]['x'],resumed[method]['x'])
        assert full[method]['total']==resumed[method]['total']
    a=json.loads((Path(out)/'full'/'result.json').read_text())
    b=json.loads((Path(out)/'resumed'/'result.json').read_text())
    assert a['records']==b['records']
    atomic_json(Path(out)/'verification.json',dict(status='PASS',test=identity['test'],
        runner_sha256=sha(__file__),engine_sha256=sha(ENGINE/'dense_scaling.py')))
    print('LOCAL_RESUME_EQUIVALENCE_PASS',flush=True)


def run(config_path, out):
    cfg=json.loads(Path(config_path).read_text()); identity=provenance(config_path)
    out=Path(out);begin=time.monotonic()
    feasibility=out/'feasibility'/'feasibility.json'
    assert json.loads(feasibility.read_text())['status']=='PASS', 'Run corrected local feasibility first.'
    checked=json.loads((out/'resume_check'/sha(__file__)[:16]/'verification.json').read_text())
    assert checked['status']=='PASS' and checked['runner_sha256']==identity['runner_sha256']
    assert checked['engine_sha256']==identity['engine_sha256']
    completed=[]
    deadline=begin+cfg['max_wall_hours']*3600
    atomic_json(out/'study_progress.json',dict(status='RUNNING',completed_tasks=completed,
        total_tasks=len(cfg['tasks']),pid=os.getpid(),**identity))
    for i,task in enumerate(cfg['tasks']):
        target=out/task['phase']/f'task-{i:03d}'
        if (target/'result.json').exists():
            old=json.loads((target/'result.json').read_text())
            checked=old['identity'] if task['phase']=='critic' else {k:old[k] for k in identity}
            assert checked==identity
        elif task['phase']=='critic':
            critic(task,cfg['critic_prefixes'],target,identity)
        else:
            actor(task,cfg['schedules'][task['profile']],target,identity,deadline=deadline)
        completed.append(i)
        atomic_json(out/'study_progress.json',dict(status='RUNNING',completed_tasks=completed,
            total_tasks=len(cfg['tasks']),latest_task=task,pid=os.getpid(),elapsed_seconds=time.monotonic()-begin,**identity))
        from npg_300_local_report import report
        report(out)
        if time.monotonic()>=deadline:
            raise TimeoutError('Runtime limit reached at a completed calibration task.')
    atomic_json(out/'study_progress.json',dict(status='COMPLETE',completed_tasks=completed,
        total_tasks=len(cfg['tasks']),elapsed_seconds=time.monotonic()-begin,**identity))
    print('LOCAL_CALIBRATION_COMPLETE',flush=True)


if __name__=='__main__':
    require_compute();parser=argparse.ArgumentParser()
    parser.add_argument('--config');parser.add_argument('--output',required=True)
    parser.add_argument('--selfcheck',action='store_true');args=parser.parse_args()
    if args.selfcheck:selfcheck(args.output)
    else:
        out=Path(args.output);lock=out/'worker.lock.json';proc=psutil.Process()
        if lock.exists():
            old=json.loads(lock.read_text())
            try:
                previous=psutil.Process(old['pid'])
                if previous.is_running() and abs(previous.create_time()-old['created'])<1:
                    raise RuntimeError('A local calibration worker is already running.')
            except psutil.NoSuchProcess:pass
            lock.unlink()
        with lock.open('x') as stream:
            json.dump(dict(pid=os.getpid(),created=proc.create_time()),stream)
        try:
            run(args.config,out)
        except Exception as exc:
            state='CHECKPOINTED_RUNTIME_LIMIT' if isinstance(exc,TimeoutError) else 'FAILED'
            progress=json.loads((out/'study_progress.json').read_text()) if (out/'study_progress.json').exists() else {}
            atomic_json(out/'study_progress.json',dict(**{k:v for k,v in progress.items() if k!='status'},
                status=state,error=str(exc)))
            raise
        finally:
            lock.unlink(missing_ok=True)
