"""Seal/copy failed X12 evidence only. Never deletes, resumes, or simulates."""
import argparse,datetime,hashlib,io,json,subprocess,tarfile
from pathlib import Path,PurePosixPath
BASE=Path('/scratch/user/changze/lqr_experiments');OUT=BASE/'results/x12-20261106'
TRANSIT=Path('/home/changze/lqr-x12-failure-transit-20261107-v1')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def pack():
    assert Path(__file__).resolve()==TRANSIT/'backup_failed_formal_v1.py'
    archive=TRANSIT/'x12-failed-formal-v1.tar.gz';manifest=archive.with_suffix('.json');partial=archive.with_suffix('.building')
    assert not archive.exists() and not manifest.exists() and not partial.exists(),'Existing attempt; reconcile, never repack.'
    raw=subprocess.check_output(['sacct','-X','--array','-n','-P','-j','20424516,20424517','--format=JobID,State,ExitCode,ElapsedRaw,AllocTRES'],text=True)
    rows=[s.split('|')[:5] for s in raw.splitlines() if s];assert len(rows)==64 and all(r[1]=='FAILED' for r in rows)
    quota=subprocess.check_output(['/sw/local/bin/showquota'],text=True)
    # The measured home headroom is checked again, without creating a probe.
    line=next(s for s in quota.splitlines() if s.startswith('/home/changze'))
    cells=line.split();assert cells[-1]=='10000' and int(cells[-2])<=9900
    assert cells[1].endswith('G') and float(cells[1][:-1])<=8
    paths=[]
    for prefix in ['formal-v1','formal-models-v1','budget','submissions','logs','deployments','failures']:
        paths.extend(p for p in (OUT/prefix).rglob('*') if p.is_file())
    release=BASE/'releases/x12-20261106-formal-v1'
    paths.extend(p for p in release.rglob('*') if p.is_file())
    assert paths and len(paths)==len(set(paths)) and all(not p.is_symlink() for p in paths)
    total=sum(p.stat().st_size for p in paths);assert total<3*1024**3,'Home transit bound exceeded; stop, no cleanup.'
    entries=[]
    def add(tf,name,payload):
        m=tarfile.TarInfo(name);m.size=len(payload);tf.addfile(m,io.BytesIO(payload))
        entries.append(dict(path=name,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest()))
    with tarfile.open(partial,'x:gz',compresslevel=1) as tf:
        for p in sorted(paths):
            if p.is_relative_to(OUT):name='results/'+p.relative_to(OUT).as_posix()
            else:name='provenance/formal-release-v1/'+p.relative_to(release).as_posix()
            add(tf,name,p.read_bytes())
        add(tf,'evidence/slurm-all64-failed.json',(json.dumps(dict(rows=rows,quota_snapshot=quota),indent=2)+'\n').encode())
        add(tf,'evidence/backup_failed_formal_v1.py',Path(__file__).read_bytes())
    partial.rename(archive)
    result=dict(status='SEALED_FAILED_X12_PARTIAL_EVIDENCE',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                files=entries,archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),
                source_sha256=sha(Path(__file__)),failed_allocations=64,whole_tasks_completed=0,
                original_source_unchanged=True,no_deletion=True,new_training_transitions=0,Grace_SU=0,
                note='Failed partial attempt, not a completed formal dataset. Home transit uses a few files because scratch file quota is full.')
    with manifest.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(status=result['status'],archive=str(archive),manifest=str(manifest),files=len(entries),
                         archive_bytes=result['archive_bytes'],archive_sha256=result['archive_sha256'],manifest_sha256=sha(manifest),source_sha256=result['source_sha256'])))
def unpack(a):
    assert not a.destination.exists(),'Never merge/overwrite an earlier evidence copy.'
    d=json.loads(a.manifest.read_text(encoding='utf-8-sig'));assert d['status']=='SEALED_FAILED_X12_PARTIAL_EVIDENCE'
    assert a.archive.stat().st_size==d['archive_bytes'] and sha(a.archive)==d['archive_sha256']
    expected={x['path']:x for x in d['files']};assert len(expected)==len(d['files'])
    with tarfile.open(a.archive,'r:gz') as tf:
        members=tf.getmembers();assert len(members)==len(expected) and {m.name for m in members}==set(expected)
        for m in members:
            p=PurePosixPath(m.name);assert m.isfile() and not p.is_absolute() and '..' not in p.parts and ':' not in m.name and '\\' not in m.name
            b=tf.extractfile(m).read();assert len(b)==expected[m.name]['bytes'] and hashlib.sha256(b).hexdigest()==expected[m.name]['sha256']
        a.destination.mkdir(parents=True)
        for m in members:
            target=a.destination/m.name;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(tf.extractfile(m).read())
    result=dict(status='VERIFIED_FAILED_X12_PARTIAL_EVIDENCE_ON_E',files=len(members),archive_sha256=d['archive_sha256'],
                manifest_sha256=sha(a.manifest),failed_allocations=64,whole_tasks_completed=0,new_training_transitions=0,no_deletion=True)
    with a.destination.with_suffix('.verified.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['pack','unpack']);p.add_argument('--archive',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--destination',type=Path)
    a=p.parse_args();pack() if a.mode=='pack' else unpack(a)
