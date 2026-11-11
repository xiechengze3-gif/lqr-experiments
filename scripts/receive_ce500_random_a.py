"""Resume verified chunk downloads; keep one temporary archive on E: at a time."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--temp',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);a.temp.mkdir(parents=True,exist_ok=True)
    assert str(a.output.resolve()).lower().startswith('e:\\chatgpt\\results\\lqr_experiments\\')
    assert str(a.temp.resolve()).lower().startswith('e:\\chatgpt\\temp\\lqr_experiments\\')
    receipt=json.loads(a.receipt.read_text(encoding='utf-8'));assert receipt['status']=='complete'
    state_path=a.output/'local-transfer-state.json'
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else dict(
        status='receiving',manifest_sha256=receipt['manifest_sha256'],chunks={})
    assert state['manifest_sha256']==receipt['manifest_sha256']
    pending=[q for q in receipt['chunks'] if q['group'] not in state['chunks']]
    required=sum(q['bytes'] for q in pending)+max((q['bytes'] for q in pending),default=0)+256*1024**2
    assert shutil.disk_usage(a.output).free>required*1.05,('Insufficient E: space for verified extraction',required)
    manifest_path=a.output/'artifact_sha256.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else None
    for chunk in receipt['chunks']:
        if chunk['group'] in state['chunks']:
            assert manifest is not None
            assert all(sha(a.output/rel)==manifest[rel] for rel in chunk['files'])
            print(json.dumps(dict(group=chunk['group'],status='reused_verified')),flush=True)
            continue
        archive=a.temp/Path(chunk['path']).name
        if not archive.exists() or sha(archive)!=chunk['sha256']:
            subprocess.run(['E:/ChatGPT/Cache/putty/0.85/pscp.exe','-load','Grace-Codex-Downstream',
                '-batch','-share','-sftp','-q','changze@grace.hprc.tamu.edu:'+chunk['path'],str(archive)],check=True)
        assert archive.stat().st_size==chunk['bytes'] and sha(archive)==chunk['sha256']
        with tarfile.open(archive) as bundle:
            expected=set(chunk['files'])|({'artifact_sha256.json'} if chunk['group']=='common' else set())
            members=bundle.getmembers();assert {m.name for m in members}==expected
            for member in members:
                assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                assert (a.output/member.name).resolve().is_relative_to(a.output.resolve())
            if chunk['group']=='common':
                blob=bundle.extractfile('artifact_sha256.json').read()
                assert hashlib.sha256(blob).hexdigest()==receipt['manifest_sha256']
                manifest=json.loads(blob)
            assert manifest is not None
            bundle.extractall(a.output,filter='data')
        assert all(sha(a.output/rel)==manifest[rel] for rel in chunk['files'])
        state['chunks'][chunk['group']]=dict(status='verified',files=len(chunk['files']),archive_sha256=chunk['sha256'])
        state_path.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
        assert archive.resolve().is_relative_to(a.temp.resolve());archive.unlink()
        print(json.dumps(dict(group=chunk['group'],status='verified',files=len(chunk['files']))),flush=True)
    assert manifest is not None and len(manifest)==receipt['file_count']
    assert all(sha(a.output/rel)==digest for rel,digest in manifest.items())
    state.update(status='complete',verified_scientific_files=len(manifest))
    state_path.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PASS',verified_files=len(manifest),chunks=len(state['chunks']))),flush=True)


if __name__=='__main__':main()
