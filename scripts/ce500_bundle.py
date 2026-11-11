"""Immutable per-group result bundles; allows local transfer during formal runs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile


def read(path):return json.loads(path.read_text())


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--kind',choices=['common','formal','final'],required=True)
    p.add_argument('--group',type=int,default=0);a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    cfg=read(a.manifest);out=Path(cfg['output']);base=out.parent.parent
    archive_root=base/'archives'/cfg['experiment'];archive_root.mkdir(parents=True,exist_ok=True)
    label=a.kind+(f'-{a.group:02d}' if a.kind=='formal' else '')
    destination=archive_root/(label+'.tar.gz');receipt=archive_root/(label+'.json')
    if receipt.exists():
        assert sha(destination)==read(receipt)['archive_sha256'];print(receipt.read_text());return
    chosen=set()
    if a.kind=='common':
        for d in ('systems','frozen','diagnostics','report-pilot'):
            chosen.update(p for p in (out/d).rglob('*') if p.is_file())
        chosen.update(p for p in out.glob('*.json') if p.is_file())
        seeds=cfg['pilot_seeds']
        chosen.update(p for p in (out/'logs').glob('*') if 'pilot-' in p.name or 'preflight-' in p.name)
    elif a.kind=='formal':
        seeds=cfg['confirm_seeds'][5*a.group:5*(a.group+1)];assert len(seeds)==5
    else:
        seeds=[]
        # All scientific jobs must have finished before this metadata snapshot.
        for d in ('report-confirm','identification-audit','accounting','documentation','frozen','logs','task_receipts'):
            chosen.update(p for p in (out/d).rglob('*') if p.is_file())
        chosen.update(p for p in out.glob('*.json') if p.is_file())
        files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*'))
               if p.is_file() and p.name!='artifact_sha256.json'}
        manifest=out/'artifact_sha256.json';manifest.write_text(json.dumps(files,indent=2)+'\n')
        chosen.add(manifest)
    for seed in seeds:
        for rank in cfg['ranks']:
            stem=f'ce-r{rank:03d}-s{seed:04d}'
            raw=out/'raw'/(stem+'.json');assert raw.exists()
            assert read(raw)['rank']==rank and read(raw)['seed']==seed
            chosen.add(raw)
            for d in ('checkpoints','estimates'):chosen.add(out/d/(stem+'.npz'))
            chosen.update(p for p in (out/'policies'/stem).rglob('*') if p.is_file())
    assert chosen and all(p.is_file() and p.is_relative_to(out) for p in chosen)
    files={str(p.relative_to(out)):sha(p) for p in sorted(chosen)}
    temporary=destination.with_suffix('.tmp.tar.gz')
    with tarfile.open(temporary,'w:gz',compresslevel=1) as bundle:
        for source in sorted(chosen):bundle.add(source,arcname=cfg['experiment']+'/'+str(source.relative_to(out)),recursive=False)
    os.replace(temporary,destination)
    result=dict(status='complete',kind=a.kind,group=a.group,archive=str(destination),
        archive_sha256=sha(destination),archive_bytes=destination.stat().st_size,
        files_sha256=files,slurm_job_id=os.environ['SLURM_JOB_ID'])
    receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files_sha256'}))


if __name__=='__main__':main()
