"""Dispatch the eight lower B* rungs through the unchanged X12 actor."""
import argparse
import json
import os
import resource
import time
from pathlib import Path

import numpy as np

import actor_paths as actor
import estimation
import frozen_engine as engine
from virtual_task_store_v2 import TaskStore, file_sha, install_io_only, verify_archive


HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CONFIG=HERE/'config-x14f-full-v1.json'
LOGICAL=Path('/scratch/user/changze/lqr_experiments/results/x12-20261106/x14f-full-virtual-only')


def run(stage,index):
    engine.require_compute()
    assert index==int(os.environ['SLURM_ARRAY_TASK_ID']) and not LOGICAL.exists()
    config=json.loads(CONFIG.read_bytes())
    sources=config['scientific_sources']
    assert all(file_sha(path)==sources[name] for name,path in
               [('formal_driver.py',__file__),('actor_paths.py',actor.__file__),('estimation.py',estimation.__file__),
                ('frozen_engine.py',engine.__file__)])
    entries=config['all_schedules']
    assert len(entries)==8 and [r['rung'] for r in entries]==config['rungs']
    assert all(row['batches']==actor.schedules(3276800,row['rung'],16,8) for row in entries)
    group=config['formal_groups'][index if stage=='pilot' else index//32]
    algorithm=group['runs'][0]['algorithm']
    if stage=='pilot':
        system,seed=config['timing_system'],config['timing_seed']
        model=estimation.model('S',60,system)
        meta=dict(certificate=model['certificate'],source='X12 timing model constructor')
    else:
        slot=index%32
        system=config['formal_systems'][slot//4]
        seed=config['formal_sampling_seeds'][slot%4]
        meta=config['model_registry'][f'n60-s{system}']
        path=HERE/meta['path']
        assert file_sha(path)==meta['sha256']
        with np.load(path,allow_pickle=False) as archive:
            model={name:archive[name] for name in archive.files}
        model['certificate']=meta['certificate']
    assert model['A'].shape==(60,60) and model['basis'].shape==(60,2) and not model['K0'].any()
    prefix=f'x14f-full-{stage}-{index:03d}'
    store=TaskStore(ROOT/(prefix+'.tar'),ROOT/(prefix+'.jsonl'),LOGICAL/prefix,64*2**20)
    base=dict(experiment='X12' if stage=='formal' else 'X12_RESOURCE_ONLY',n=60,m=60,r=2,system=system,seed=seed)
    header=dict(group=group,index=index%32,spec=base,model=meta,job=os.environ['SLURM_ARRAY_JOB_ID'],
                config_sha256=file_sha(CONFIG),source_sha256=file_sha(__file__),actor_sha256=file_sha(actor.__file__),
                engine_sha256=file_sha(engine.__file__))
    store.save_json(store.root/'BEGIN.json',header)
    original=install_io_only(engine,actor,store)
    paths=[]
    start=time.monotonic()
    try:
        for run,entry in zip(group['runs'],entries,strict=True):
            assert run['rung']==entry['rung'] and run['algorithm']==algorithm
            spec=dict(base,rung=run['rung'],rung_label=run['rung_label'])
            label=f"{algorithm}-{run['rung_label']}"
            dest=store.root/label
            expected=entry['primitive_per_arm_per_algorithm']
            batches=entry['batches']
            assert all(16*(sum(batches[alg])+17*len(batches[alg]))==expected for alg in batches)
            result=actor.run(model,spec,dict(H=16,nu=1.,burn_blocks=16,eta=.2,schedules=batches),algorithm,dest)
            assert result['primitive_transitions']==dict(dense=expected,truncated=expected)
            assert len(result['records'])==2*(len(batches[algorithm])+1)
            paths.append(dict(algorithm=algorithm,rung=run['rung'],path=label,primitive_per_arm=expected,
                              done_sha256=store.sha(dest/'DONE.json')))
        cache=Path(os.environ['TMPDIR'])
        files=list(cache.rglob('*'))
        assert cache.is_relative_to(ROOT) and len(files)+1<=21
        assert sum(p.stat().st_size for p in files if p.is_file())<=64*2**20
        body=time.monotonic()-start
        store.save_json(store.root/'DONE.json',dict(header,status='COMPLETE',paths=paths,seconds=body))
        final=dict(header,index=index,status='COMPLETE',algorithm=algorithm,system=system,seed=seed,paths=paths,
                   body_seconds=body,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   observation_transitions=2*sum(r['primitive_per_arm'] for r in paths),automatic_retries=0)
    except Exception as exc:
        store.save_json(store.root/'HARD_FAILURE.json',dict(header,error=repr(exc),completed_paths=paths,automatic_retry=False))
        raise
    finally:
        proof=store.close()
        engine.sha,engine.save,actor.save_npz=original
    if stage=='pilot':
        verify_archive(store.archive,proof['members'])
    proof.pop('journal_sha256')
    with store.journal.open('ab') as stream:
        stream.write((json.dumps(dict(proof,kind='TASK_FINAL',**final))+'\n').encode())
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(dict(final,archive_sha256=proof['archive_sha256'])),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['pilot','formal'])
    parser.add_argument('index',type=int)
    args=parser.parse_args()
    run(args.stage,args.index)
