"""Append-only task tar: original NPZ/JSON byte streams, zero loose stage files.

This is an I/O adapter only. It does not import/call collectors or learners.
Directories are logical tar namespaces; existing cluster files are never
deleted, renamed, overwritten or compacted by this module.
"""
import hashlib,io,json,os,re,tarfile
from pathlib import Path,PurePosixPath

def digest(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

class VirtualPath:
    def __init__(self,store,relative='.'):
        self.store=store;self.relative=PurePosixPath(relative)
        assert not self.relative.is_absolute() and '..' not in self.relative.parts
    def __truediv__(self,part):
        assert isinstance(part,str) and '\\' not in part and ':' not in part
        return type(self)(self.store,self.relative/part)
    def __str__(self):return str(self.store.logical_root/self.relative.as_posix())
    def __fspath__(self):return str(self)
    @property
    def name(self):return self.relative.name
    @property
    def parent(self):return type(self)(self.store,self.relative.parent)
    def with_suffix(self,suffix):return type(self)(self.store,self.relative.with_suffix(suffix))
    def resolve(self):return Path(str(self)).resolve()
    def exists(self):return self.relative.as_posix() in self.store.members or self.relative.as_posix() in self.store.directories
    def mkdir(self,parents=False,exist_ok=False):
        key=self.relative.as_posix()
        assert exist_ok or not self.exists(),'Never overwrite a virtual result namespace.'
        if parents:
            for p in self.relative.parents:self.store.directories.add(p.as_posix())
        self.store.directories.add(key)

class TaskStore:
    def __init__(self,archive,journal,logical_root,maximum_bytes):
        self.archive=Path(archive);self.journal=Path(journal);self.logical_root=Path(logical_root).resolve()
        assert self.archive.parent==self.journal.parent and self.archive.parent.is_dir()
        assert not self.archive.exists() and not self.journal.exists(),'Reconcile an existing attempt; never replay.'
        assert maximum_bytes>0
        self.maximum_bytes=int(maximum_bytes);self.members={};self.directories={'.'};self.peak_buffer_bytes=0
        self.journal_bytes=0;self.commits=0;self.closed=False
        self.tf=tarfile.open(self.archive,'x:',format=tarfile.USTAR_FORMAT)
        self.log=self.journal.open('xb')
        self.root=VirtualPath(self)
    def _key(self,path):
        assert isinstance(path,VirtualPath) and path.store is self
        key=path.relative.as_posix();p=PurePosixPath(key)
        assert key!='.' and not p.is_absolute() and '..' not in p.parts and ':' not in key and '\\' not in key
        return key
    def write_bytes(self,path,payload):
        key=self._key(path);assert key not in self.members,'Never replace an existing raw member.'
        assert isinstance(payload,bytes)
        projected=self.tf.offset+512+((len(payload)+511)//512)*512+10240
        assert projected<=self.maximum_bytes,'Declared per-task archive bound exceeded; stop without deletion.'
        m=tarfile.TarInfo(key);m.size=len(payload);m.mode=0o600;m.mtime=0
        self.tf.addfile(m,io.BytesIO(payload))
        self.members[key]=dict(path=key,bytes=len(payload),sha256=digest(payload))
        self.peak_buffer_bytes=max(self.peak_buffer_bytes,len(payload))
        return self.members[key]
    def save_npz(self,path,**values):
        # Same NumPy serializer/kwargs order as the frozen disk helper.
        import numpy as np
        buffer=io.BytesIO();np.savez_compressed(buffer,**values)
        return self.write_bytes(path,buffer.getvalue())
    def save_json(self,path,data):
        result=self.write_bytes(path,(json.dumps(data,indent=2)+'\n').encode('utf-8'))
        if re.fullmatch(r'checkpoint-\d{3}\.json',path.name):
            self.commit(dict(kind='COMPLETE_STAGE',path=result['path'],sha256=result['sha256'],
                             primitive_transitions=data['total_primitive_transitions']))
        elif path.name in ['DONE.json','HARD_FAILURE.json']:
            self.commit(dict(kind=path.name,path=result['path'],sha256=result['sha256']))
        return result
    def sha(self,path):
        if isinstance(path,VirtualPath):return self.members[self._key(path)]['sha256']
        return file_sha(path)
    def commit(self,event):
        # Append-only: no temporary journal, replacement, move, or deletion.
        self.tf.fileobj.flush();os.fsync(self.tf.fileobj.fileno())
        item=dict(sequence=self.commits,archive_offset=self.tf.offset,**event)
        b=(json.dumps(item,sort_keys=True)+'\n').encode('utf-8');self.log.write(b)
        self.log.flush();os.fsync(self.log.fileno());self.journal_bytes+=len(b);self.commits+=1
    def close(self):
        assert not self.closed
        self.commit(dict(kind='END_OF_PROCESS',members=len(self.members)))
        self.tf.close();self.log.close();self.closed=True
        return dict(archive_sha256=file_sha(self.archive),archive_bytes=self.archive.stat().st_size,
                    journal_sha256=file_sha(self.journal),journal_bytes=self.journal.stat().st_size,
                    members=list(self.members.values()),peak_serialization_buffer_bytes=self.peak_buffer_bytes,
                    physical_store_files=2,physical_loose_stage_files=0,no_deletion_or_overwrite=True)

def install_io_only(engine,actor,store):
    """Numerical function objects stay unchanged; replace only named I/O helpers."""
    original=(engine.sha,engine.save,actor.save_npz)
    def save(path,data):
        assert isinstance(path,VirtualPath),'Training outputs must use the registered virtual store.'
        return store.save_json(path,data)
    engine.sha=store.sha;engine.save=save;actor.save_npz=store.save_npz
    return original

def verify_archive(archive,expected):
    by={x['path']:x for x in expected};assert len(by)==len(expected)
    with tarfile.open(archive,'r:') as tf:
        members=tf.getmembers();assert len(members)==len(by) and {m.name for m in members}==set(by)
        for m in members:
            assert m.isfile();data=tf.extractfile(m).read()
            assert len(data)==by[m.name]['bytes'] and digest(data)==by[m.name]['sha256']
    return len(by)
