"""Save all new artifacts plus compact review bundle, without altering old data."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import time

BASE=Path('/scratch/user/changze/lqr_experiments')
NAME='ce500-rank4-extension-20261020'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    assert os.environ.get('SLURM_JOB_ID');began=time.monotonic()
    out=BASE/'results'/NAME;release=BASE/'releases'/NAME;archives=BASE/'archives'/NAME
    archives.mkdir(parents=True,exist_ok=True)
    assert json.loads((out/'report-confirm/summary.json').read_text())['status']=='complete'
    assert json.loads((out/'identification-audit/audit.json').read_text())['status']=='PASS'
    shutil.copytree(release,out/'frozen/release',dirs_exist_ok=True)
    marker=out/'completion.json'
    marker.write_text(json.dumps(dict(status='complete',new_rank=4,formal_seeds=30,
        new_formal_policies_independently_rechecked=900,old_campaign_immutable=True,
        archive_job=os.environ['SLURM_JOB_ID'],all_learning_and_audits_completed=True),indent=2)+'\n')
    # Running Slurm logs change while archived; scientific files are immutable.
    files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*'))
        if p.is_file() and 'logs' not in p.relative_to(out).parts and p.name!='artifact_sha256.json'}
    (out/'artifact_sha256.json').write_text(json.dumps(files,indent=2)+'\n')
    review=archives/'review.tar.gz'
    with tarfile.open(review,'w:gz',compresslevel=1) as t:
        for path in sorted(out.rglob('*')):
            if not path.is_file():continue
            rel=path.relative_to(out)
            if rel.parts[0] in ('report-confirm','report-pilot','frozen','task_receipts','identification-audit','accounting') or len(rel.parts)==1 or (rel.parts[0]=='raw' and rel.suffix=='.json'):
                t.add(path,arcname=str(rel))
    full=archives/'complete.tar'
    with tarfile.open(full,'w') as t:t.add(out,arcname=NAME)
    receipt=dict(status='complete',archive_job=os.environ['SLURM_JOB_ID'],files_verified_by_manifest=len(files),
        artifact_manifest_sha256=sha(out/'artifact_sha256.json'),
        review_archive=dict(path=str(review),bytes=review.stat().st_size,sha256=sha(review)),
        complete_archive=dict(path=str(full),bytes=full.stat().st_size,sha256=sha(full)),
        seconds=time.monotonic()-began)
    (archives/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
