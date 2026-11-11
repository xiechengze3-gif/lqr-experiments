"""Disk-backed original-coordinate PI observations with resumable collection."""
import gc
from pathlib import Path
import numpy as np
import rank_sweep100 as e
from dense_scaling import nominal_chunk, ce_chunk


def tag(k,x,count,identity):
    import hashlib
    return dict(identity=identity,count=count,k_sha256=hashlib.sha256(k.tobytes()).hexdigest(),
                x_sha256=hashlib.sha256(x.tobytes()).hexdigest())


def collect(s,k,x,count,cfg,seed,stage,folder,identity,hook=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);n=k.shape[1]
    expected=tag(k,x,count,identity);journal=folder/'collection.json'
    shapes={'z':(count,2*n),'next_z':(count,2*n),'costs':(count,)}
    pulse=e.rng_for(cfg['sampling_seed'],2,seed,stage,0)
    noise=e.rng_for(cfg['sampling_seed'],2,seed,stage,1)
    if journal.exists():
        meta=e.read(journal);assert meta['tag']==expected
        arrays={name:np.load(folder/(name+'.npy'),mmap_mode='r+') for name in shapes}
        pulse.bit_generator.state=meta['pulse_rng'];noise.bit_generator.state=meta['noise_rng']
        x=np.asarray(meta['x'],dtype=float)
    else:
        arrays={name:np.lib.format.open_memmap(folder/(name+'.npy'),mode='w+',dtype=float,shape=shape)
                for name,shape in shapes.items()}
        meta=dict(tag=expected,burn_done=False,filled=0,actual=0,x=x.tolist(),
                  pulse_rng=pulse.bit_generator.state,noise_rng=noise.bit_generator.state)
        e.atomic_json(journal,meta)
    assert all(arrays[name].shape==shape for name,shape in shapes.items())
    f=np.ascontiguousarray(s['A']-s['B']@k)

    def commit():
        for arr in arrays.values():arr.flush()
        meta.update(x=x.tolist(),pulse_rng=pulse.bit_generator.state,noise_rng=noise.bit_generator.state)
        e.atomic_json(journal,meta)
        if hook is not None:hook(meta)

    if not meta['burn_done']:
        x,_=nominal_chunk(f,x,noise.normal(size=(cfg['burn'],n)))
        meta.update(burn_done=True,actual=cfg['burn']);commit()
    for lo in range(meta['filled'],count,cfg.get('data_chunk',8192)):
        hi=min(count,lo+cfg.get('data_chunk',8192));size=hi-lo
        x,zz,yy=ce_chunk(f,s['B'],k,x,pulse.normal(scale=cfg['sigma'],size=(size,n)),
                         noise.normal(size=(size,n)))
        arrays['z'][lo:hi]=zz
        arrays['next_z'][lo:hi,:n]=yy;arrays['next_z'][lo:hi,n:]=-yy@k.T
        arrays['costs'][lo:hi]=np.einsum('ij,ij->i',zz[:,:n]@s['Q'],zz[:,:n])
        arrays['costs'][lo:hi]+=np.einsum('ij,ij->i',zz[:,n:]@s['R'],zz[:,n:])
        meta.update(filled=hi,actual=cfg['burn']+hi);commit()
    assert meta['actual']==count+cfg['burn']
    return x,arrays['z'],arrays['next_z'],arrays['costs'],meta['actual']


def release_observations(folder,temporary_root):
    folder=Path(folder).resolve();root=Path(temporary_root).resolve()
    assert root in folder.parents and folder.name.startswith('stage-')
    assert (folder/'fit.json').exists(),'Never remove observations before fitted-critic checkpoint'
    gc.collect()
    for name in ('z.npy','next_z.npy','costs.npy'):
        path=folder/name
        if path.exists():path.unlink()


def cleanup(folder,temporary_root):
    """Remove only this task's known transient files after a durable checkpoint."""
    folder=Path(folder).resolve();root=Path(temporary_root).resolve()
    assert root in folder.parents and folder.name.startswith('stage-')
    gc.collect()
    for name in ('z.npy','next_z.npy','costs.npy','collection.json','fit.npz','fit.json'):
        path=folder/name
        if path.exists():path.unlink()
    try:folder.rmdir()
    except OSError:pass
