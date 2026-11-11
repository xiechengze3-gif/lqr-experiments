"""Saved-byte I/O pilot only: no collector, learner, model solve or trajectories."""
import argparse,datetime,hashlib,io,json,os,platform,re,socket,tarfile,time
try:import resource
except ImportError:resource=None
from pathlib import Path
import numpy as np
from virtual_task_store_v2 import TaskStore,verify_archive,file_sha,digest

def file_reference(values,folder,index):
    # A real seekable FileIO reference without a named cluster file, where
    # memfd is available. Windows preliminary checks use new E-only files.
    if hasattr(os,'memfd_create'):
        fd=os.memfd_create('x12-npz-io-reference',0)
        with os.fdopen(fd,'w+b') as stream:
            np.savez_compressed(stream,**values);stream.seek(0);return stream.read(),'anonymous_memfd_FileIO'
    p=folder/('reference-'+str(index).zfill(4)+'.npz')
    assert not p.exists();np.savez_compressed(p,**values)
    return p.read_bytes(),'new_named_preliminary_reference_files'

def main(a):
    assert not a.out.exists(),'Preserve an existing pilot, never overwrite.'
    a.out.mkdir(parents=True);begin=time.monotonic();results=[];checked=0;fixture_resave_equal=0;backends=set()
    for alg in ['NPG','PI']:
        archive=a.fixtures/('x12-raw-timing-'+alg+'-v1.tar.gz')
        manifest=archive.with_suffix('.json');m=json.loads(manifest.read_text(encoding='utf-8-sig'))
        assert m['status']=='SEALED_COMPLETE_X12_RAW_SNAPSHOT' and m['scope']=='pilot-timing' and m['algorithm']==alg
        assert file_sha(archive)==m['archive_sha256']
        entries={x['path']:x for x in m['files']};prefix='timing-v1/'+alg+'/'
        store=TaskStore(a.out/(alg+'.tar'),a.out/(alg+'.jsonl'),a.out/('logical-'+alg),a.maximum_task_bytes)
        input_paths=[];npz_count=json_count=0;max_original_member=0
        with tarfile.open(archive,'r:gz') as source:
            for item in source:
                name=item.name
                if not name.startswith(prefix):continue
                relative=name[len(prefix):];parts=relative.split('/')
                if len(parts)!=2 or not re.fullmatch(r'r[0-9]+',parts[0]):continue
                leaf=parts[1]
                if not (leaf.endswith('.npz') or leaf.endswith('.json')):continue
                data=source.extractfile(item).read();assert digest(data)==entries[name]['sha256'] and len(data)==entries[name]['bytes']
                max_original_member=max(max_original_member,len(data));folder=store.root/parts[0]
                if not folder.exists():folder.mkdir(parents=True)
                target=folder/leaf
                if leaf.endswith('.npz'):
                    with np.load(io.BytesIO(data),allow_pickle=False) as old:
                        values={k:old[k].copy(order='K') for k in old.files}
                    before={k:(v.dtype.str,v.shape,v.flags.c_contiguous,v.flags.f_contiguous,v.tobytes(order='A')) for k,v in values.items()}
                    reference,backend=file_reference(values,a.out,checked);backends.add(backend)
                    meta=store.save_npz(target,**values)
                    assert meta['sha256']==digest(reference),'BytesIO differs from real FileIO serializer.'
                    if meta['sha256']==digest(data):fixture_resave_equal+=1
                    assert before=={k:(v.dtype.str,v.shape,v.flags.c_contiguous,v.flags.f_contiguous,v.tobytes(order='A')) for k,v in values.items()},'Serializer mutated an input array.'
                    npz_count+=1
                else:
                    d=json.loads(data.decode('utf-8'));meta=store.save_json(target,d)
                    assert meta['sha256']==digest(data),'JSON byte stream differs from frozen encoder.'
                    json_count+=1
                input_paths.append(relative);checked+=1
        T=16 if alg=='NPG' else 8
        assert len(set(p.split('/')[0] for p in input_paths))==9
        assert npz_count==9*3*T and json_count==9*(T+1)
        result=store.close();assert verify_archive(store.archive,result['members'])==len(input_paths)
        final=dict(status='COMPLETE',archive_sha256=result['archive_sha256'],archive_bytes=result['archive_bytes'],members=result['members'])
        with store.journal.open('ab') as f:
            f.write((json.dumps(final)+'\n').encode('utf-8'));f.flush();os.fsync(f.fileno())
        result['journal_sha256']=file_sha(store.journal);result['journal_bytes']=store.journal.stat().st_size
        # Physical files from TaskStore are exactly archive+journal; no stage
        # file or logical directory is created by the virtual writer.
        assert not (a.out/('logical-'+alg)).exists()
        result.update(algorithm=alg,fixture_sha256=m['archive_sha256'],npz_reference_comparisons=npz_count,
                      json_original_byte_comparisons=json_count,max_original_member_bytes=max_original_member)
        results.append(result)
    active_compute=bool(os.environ.get('SLURM_JOB_ID')) and not socket.gethostname().startswith('login')
    status='ACTIVE_GRACE_IO_PILOT_PASS' if active_compute and backends=={'anonymous_memfd_FileIO'} else 'LOCAL_PRELIMINARY_IO_CHECK_PASS_NEEDS_ACTIVE_GRACE_PILOT'
    d=dict(status=status,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seconds=time.monotonic()-begin,
           numpy_version=np.__version__,python_version=platform.python_version(),host=socket.gethostname(),job=os.environ.get('SLURM_JOB_ID'),
           reference_backends=sorted(backends),all_npz_fileio_vs_memory_byte_comparisons=checked-sum(r['json_original_byte_comparisons'] for r in results),
           npz_old_fixture_resave_byte_identical=fixture_resave_equal,results=results,
           peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource is not None else None,
           physical_store_files_per_task=2,physical_loose_stage_files_per_task=0,
           future_final_done_files_per_task=0,future_Slurm_logs_per_task=1,
           no_collector_learner_or_model_solve_called=True,new_training_transitions=0,old_source_unchanged=True,no_deletion=True,
           source_sha256=file_sha(Path(__file__)),store_source_sha256=file_sha(Path(__file__).with_name('virtual_task_store_v2.py')))
    with (a.out/'DONE.json').open('x',encoding='utf-8') as f:json.dump(d,f,indent=2)
    print(json.dumps({k:v for k,v in d.items() if k!='results'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fixtures',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--maximum-task-bytes',type=int,default=96*1024*1024);main(p.parse_args())
