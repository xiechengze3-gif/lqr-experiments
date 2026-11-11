"""Create disjoint, checksummed transfer chunks after formal audit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID');cfg=json.loads(a.manifest.read_text());out=Path(cfg['output'])
    summary=json.loads((out/'report-confirm/summary.json').read_text());assert summary['audit']['status']=='PASS'
    assert summary['audit']['paired_tasks']==150
    export=out.parents[1]/'exports'/cfg['experiment'];export.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    # Archive's own growing log and future settlement files are transferred separately.
    excluded={f'logs/archive-{os.environ["SLURM_JOB_ID"]}.out','artifact_sha256.json','archive_receipt.json','completion.json'}
    files=sorted(p for p in out.rglob('*') if p.is_file() and str(p.relative_to(out)) not in excluded)
    manifest={str(p.relative_to(out)):sha(p) for p in files}
    (out/'artifact_sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
    groups={'common':[]}
    for rank in cfg['ranks']:
        for lo in range(200,230,5):groups[f'r{rank:03d}-s{lo:03d}-{lo+4:03d}']=[]
    for rel in manifest:
        group='common'
        parts=Path(rel).parts
        if parts and parts[0] in ('raw','policies','checkpoints','estimates') and len(parts)>1:
            stem=parts[1].split('.')[0]
            if stem.startswith('ce-r') and '-s' in stem:
                rank=int(stem[4:7]);seed=int(stem.split('-s')[1])
                if 200<=seed<230:
                    lo=200+((seed-200)//5)*5;group=f'r{rank:03d}-s{lo:03d}-{lo+4:03d}'
        groups[group].append(rel)
    receipts=[]
    for key,members in groups.items():
        archive=export/(key+('.tar.gz' if key=='common' else '.tar'))
        mode='w:gz' if key=='common' else 'w'
        with tarfile.open(archive,mode) as t:
            for rel in members:t.add(out/rel,arcname=rel,recursive=False)
            if key=='common':t.add(out/'artifact_sha256.json',arcname='artifact_sha256.json',recursive=False)
        receipts.append(dict(group=key,path=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=members))
        print(json.dumps(dict(group=key,bytes=archive.stat().st_size,files=len(members))),flush=True)
    result=dict(status='complete',experiment=cfg['experiment'],archive_job=os.environ['SLURM_JOB_ID'],
                manifest_sha256=sha(out/'artifact_sha256.json'),file_count=len(manifest),
                total_archive_bytes=sum(q['bytes'] for q in receipts),chunks=receipts,
                excluded_mutable_files=sorted(excluded),seconds=time.monotonic()-started)
    (export/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'archive_receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'completion.json').write_text(json.dumps(dict(status='scientific_work_complete',
        formal_seeds=30,ranks=cfg['ranks'],summary='report-confirm/summary.json',
        archive_manifest_sha256=result['manifest_sha256']),indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='chunks'}),flush=True)


if __name__=='__main__':main()
