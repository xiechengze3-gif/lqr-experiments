"""Freeze a few-file home I/O pilot; consumes verified E fixtures, not old runs."""
import argparse,ast,hashlib,io,json,tarfile
from pathlib import Path
R=Path(__file__).resolve().parent;C=R.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encode(d):return (json.dumps(d,indent=2)+'\n').encode()
def new(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(b)
def main(a):
    review=(C/'CLAUDE_TASK.md').read_bytes();assert hashlib.sha256(review).hexdigest()==a.expected_review_sha256
    assert b'X12 storage-failure recovery: ruling (01:40Z 11/07)' in review
    evidence=json.loads((R/'delivery-failed-formal-v1.verified.json').read_text(encoding='utf-8-sig'))
    assert evidence['status']=='VERIFIED_FAILED_X12_PARTIAL_EVIDENCE_ON_E' and evidence['files']==16705
    files={n:(R/n).read_bytes() for n in ['virtual_task_store_v2.py','pilot_virtual_store_v3.py','submit_storage_pilot_v2.py']}
    for n,b in files.items():ast.parse(b.decode(),filename=n)
    fixture={}
    for alg in ['NPG','PI']:
        for suffix in ['tar.gz','tar.json']:
            name='x12-raw-timing-'+alg+'-v1.'+suffix;p=R/'raw-downloads-v1'/name
            fixture[name]=sha(p);files['fixtures/'+name]=p.read_bytes()
    cfg=dict(experiment='X12_STORAGE_CORRECTION',scope='SAVED_BYTES_ONLY_ZERO_NEW_OBSERVATIONS',
             evidence_verified_on_E=True,evidence_archive_sha256=evidence['archive_sha256'],evidence_receipt_sha256=sha(R/'delivery-failed-formal-v1.verified.json'),
             fixtures=fixture,virtual_store_sha256=sha(R/'virtual_task_store_v2.py'),pilot_sha256=sha(R/'pilot_virtual_store_v3.py'),
             tasks=1,cpus=1,memory_MiB=2048,wall_minutes=5,requested_SU=5/60,new_training_transitions=0,
             all64_future_storage_gate_fraction=.8,report_reserved_SU=8,actual_cap_SU=230,exposure_cap_SU=300,
             complete_old_paths_only_reused=True,incomplete_paths_restart_from_K0=True,mid_path_resume=False,no_deletion=True,
             resource_rule='Keep original per-algorithm historical body floor; add max(60seconds,totalmeasuredIOpilotseconds) before1.20guard+30s/minuterounding.',
             byte_rule='Actual hosted reused bytes +1.50times maximum measured per-path encoded bytes times missing paths/algorithm +320KiB/taskmetadata +256MiBreport +128MiBfixedoverhead; subtract only already-hosted declared bytes from remaining growth.',
             file_rule='Append-only tar+journal per task, final completion in journal, Slurm log;3/task,zero loose stage files. Include fixed sources,cache peak,report;forecast all64 <80%current free slots.',
             read_fresh_review_before_each_stage=True)
    files['pilot-plan-v2.json']=encode(cfg);files['CLAUDE_TASK_authorized.md']=review
    files['RECOVERY_PROTOCOL_DRAFT_v2.md']=(R/'RECOVERY_PROTOCOL_DRAFT_v2.md').read_bytes()
    sbatch='''#!/usr/bin/env bash
set -euo pipefail
root=/home/changze/lqr-x12-recovery-20261107-v2
release=$root/pilot-release-v2
export TMPDIR="$root/tmp" TMP="$root/tmp" TEMP="$root/tmp" XDG_CACHE_HOME="$root/cache"
export NUMBA_CACHE_DIR="$root/cache/numba" MPLCONFIGDIR="$root/cache/matplotlib"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B pilot_virtual_store_v3.py --fixtures "$release/fixtures" --out "$root/results/storage-pilot-v2"
'''
    files['pilot.sbatch']=sbatch.encode()
    hashes={n:hashlib.sha256(b).hexdigest() for n,b in files.items()}
    files['SHA256SUMS']=''.join(h+'  '+n+'\n' for n,h in hashes.items()).encode()
    folder=R/'storage-pilot-release-v2';archive=R/'x12-storage-pilot-v2.tar.gz';assert not folder.exists() and not archive.exists()
    assert (C/'CLAUDE_TASK.md').read_bytes()==review
    for n,b in files.items():new(folder/n,b)
    with tarfile.open(archive,'x:gz',compresslevel=1) as tf:
        for n,b in files.items():
            p=tarfile.TarInfo(n);p.size=len(b);tf.addfile(p,io.BytesIO(b))
    result=dict(status='STORAGE_IO_PILOT_FROZEN_NOT_SUBMITTED',archive=str(archive),archive_sha256=sha(archive),files=hashes,
                source_manifest_sha256=sha(folder/'SHA256SUMS'),review_sha256=a.expected_review_sha256,requested_SU=5/60,new_training_transitions=0)
    new(R/'STORAGE_PILOT_MANIFEST_v2.json',encode(result));print(json.dumps({k:v for k,v in result.items() if k!='files'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-review-sha256',required=True);main(p.parse_args())
