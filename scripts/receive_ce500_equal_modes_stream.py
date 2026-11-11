"""Receive closed archive chunks while later chunks are still being written.

Each extracted file must match the immutable scientific manifest immediately;
local archive hashes are reconciled with the official receipt before completion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import time


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--temp',type=Path,required=True)
    p.add_argument('--manifest-sha256',required=True);p.add_argument('--archive-job',required=True);a=p.parse_args()
    assert str(a.output.resolve()).lower().startswith('e:\\chatgpt\\results\\lqr_experiments\\')
    assert str(a.temp.resolve()).lower().startswith('e:\\chatgpt\\temp\\lqr_experiments\\')
    a.output.mkdir(parents=True,exist_ok=True);a.temp.mkdir(parents=True,exist_ok=True)
    assert shutil.disk_usage(a.output).free>14*1024**3,'Need14GiB free before streaming scientific artifacts'
    base='/scratch/user/changze/lqr_experiments';name='ce500-equal-modes-20261020';remote=base+'/results/'+name
    client=['E:/ChatGPT/Cache/putty/0.85/pscp.exe','-load','Grace-Codex-Downstream','-batch','-share','-sftp']
    def fetch(source,dest,quiet=False):
        return subprocess.run(client+['changze@grace.hprc.tamu.edu:'+source,str(dest)],
            stdout=subprocess.DEVNULL if quiet else None,stderr=subprocess.DEVNULL if quiet else None).returncode==0
    mp=a.output/'artifact_sha256.json'
    if not mp.exists() or sha(mp)!=a.manifest_sha256:assert fetch(remote+'/artifact_sha256.json',mp)
    assert sha(mp)==a.manifest_sha256;manifest=json.loads(mp.read_text(encoding='utf-8'))
    groups={'common':[]}
    for rank in (2,4,8,32,500):
        for lo in range(200,230,5):groups[f'r{rank:03d}-s{lo:03d}-{lo+4:03d}']=[]
    for rel in manifest:
        group='common';parts=Path(rel).parts
        if parts and parts[0] in ('raw','policies','checkpoints','estimates') and len(parts)>1:
            stem=parts[1].split('.')[0]
            if stem.startswith('ce-r') and '-s' in stem:
                rank=int(stem[4:7]);seed=int(stem.split('-s')[1])
                if 200<=seed<230:
                    lo=200+((seed-200)//5)*5;group=f'r{rank:03d}-s{lo:03d}-{lo+4:03d}'
        groups[group].append(rel)
    statepath=a.output/'local-transfer-state.json'
    state=json.loads(statepath.read_text()) if statepath.exists() else dict(status='receiving',manifest_sha256=a.manifest_sha256,chunks={})
    assert state['manifest_sha256']==a.manifest_sha256
    logpath=a.temp/'archive-progress.log';progress={};began=time.monotonic()
    for group,members in groups.items():
        if group in state['chunks']:
            assert all(sha(a.output/r)==manifest[r] for r in members)
            print(json.dumps(dict(group=group,status='reused_per_file_verified')),flush=True);continue
        while group not in progress:
            assert time.monotonic()-began<3600,'Archive readiness timeout; preserve state and resume after inspecting job'
            assert fetch(remote+'/logs/archive-'+a.archive_job+'.out',logpath,True)
            for line in logpath.read_text(encoding='utf-8',errors='replace').splitlines():
                if line.startswith('{'):
                    q=json.loads(line)
                    if 'group' in q:progress[q['group']]=q
            if group not in progress:
                print(json.dumps(dict(group=group,status='waiting_for_archive_to_close')),flush=True);time.sleep(20)
        q=progress[group];assert q['files']==len(members)
        filename=group+('.tar.gz' if group=='common' else '.tar');archive=a.temp/filename
        if not archive.exists() or archive.stat().st_size!=q['bytes']:
            assert fetch(base+'/exports/'+name+'/'+filename,archive)
        assert archive.stat().st_size==q['bytes'];digest=sha(archive)
        with tarfile.open(archive) as bundle:
            expected=set(members)|({'artifact_sha256.json'} if group=='common' else set())
            mm=bundle.getmembers();assert {m.name for m in mm}==expected
            for m in mm:
                assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
                assert (a.output/m.name).resolve().is_relative_to(a.output.resolve())
            if group=='common':assert hashlib.sha256(bundle.extractfile('artifact_sha256.json').read()).hexdigest()==a.manifest_sha256
            bundle.extractall(a.output,filter='data')
        assert all(sha(a.output/r)==manifest[r] for r in members)
        state['chunks'][group]=dict(status='per_file_verified_official_archive_hash_pending',files=len(members),archive_sha256=digest,archive_bytes=q['bytes'])
        statepath.write_text(json.dumps(state,indent=2)+'\n')
        assert archive.resolve().is_relative_to(a.temp.resolve());archive.unlink()
        print(json.dumps(dict(group=group,status='per_file_verified',files=len(members))),flush=True)
    receiptpath=a.output/'archive_receipt.json'
    for _ in range(30):
        if fetch(base+'/exports/'+name+'/receipt.json',receiptpath,True):break
        time.sleep(10)
    receipt=json.loads(receiptpath.read_text());assert receipt['status']=='complete' and receipt['manifest_sha256']==a.manifest_sha256
    assert receipt['file_count']==len(manifest) and len(receipt['chunks'])==len(groups)
    for q in receipt['chunks']:
        saved=state['chunks'][q['group']];assert saved['archive_sha256']==q['sha256'] and saved['files']==len(q['files'])
        assert set(q['files'])==set(groups[q['group']]);saved['status']='verified'
    assert all(sha(a.output/rel)==digest for rel,digest in manifest.items())
    state.update(status='complete',verified_scientific_files=len(manifest),all_official_archive_hashes_verified=True)
    statepath.write_text(json.dumps(state,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',files=len(manifest),chunks=len(groups),official_archive_checksums_verified=True)),flush=True)


if __name__=='__main__':main()
