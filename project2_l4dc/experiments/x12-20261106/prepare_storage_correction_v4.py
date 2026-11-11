"""Freeze the corrected zero-observation pilot, in a fresh MDT0 namespace."""
import argparse,ast,hashlib,io,json,tarfile
from pathlib import Path
R=Path(__file__).resolve().parent;C=R.parents[1]
ROOT='/home/changze/lqr-x12-storage-correction-20261107-v4'
OLD='/home/changze/lqr-x12-recovery-20261107-v2/pilot-release-v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(x):return (json.dumps(x,indent=2)+'\n').encode()
def put(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(b)
def main(a):
    review=(C/'CLAUDE_TASK.md').read_bytes();assert hashlib.sha256(review).hexdigest()==a.expected_review_sha256
    assert b'X12 storage-failure recovery: ruling (01:40Z 11/07)' in review
    evidence=json.loads((R/'FAILED_STORAGE_IO_E_VERIFIED_v2.json').read_text(encoding='utf-8-sig'))
    assert evidence['status']=='FAILED_STORAGE_IO_ALL_MEMBERS_VERIFIED_ON_E' and evidence['files']==260
    files={n:(R/n).read_bytes() for n in ['virtual_task_store_v2.py','pilot_virtual_store_v4.py']}
    # Only submission metadata changes; no alteration of old deployed source.
    submit=(R/'submit_storage_pilot_v2.py').read_text(encoding='utf-8')
    submit=submit.replace('/home/changze/lqr-x12-recovery-20261107-v2',ROOT).replace("REL=ROOT/'pilot-release-v2'","REL=ROOT")
    submit=submit.replace('submit_storage_pilot_v2.py','submit_storage_correction_v4.py').replace('pilot-plan-v2.json','pilot-plan-v4.json')
    submit=submit.replace('storage-io-v2','storage-io-v4').replace('storage-pilot-v2','pilot-out-v4')
    before="    assert len(rows)==76 and sum(r['state']=='FAILED' for r in rows)==64\n    actual=sum(r['actual_SU'] for r in rows)"
    after="""    assert len(rows)==76 and sum(r['state']=='FAILED' for r in rows)==64
    io=call(['sacct','-X','-n','-P','-j','20424737','--format=JobID,State,ElapsedRaw,AllocTRES']).strip().split('|')
    assert io[:3]==['20424737','FAILED','16'] and 'billing=1' in io[3]
    rows.append(dict(job=io[0],state='FAILED',elapsed_seconds=16,actual_SU=16/3600))
    actual=sum(r['actual_SU'] for r in rows)
    assert cfg['failed_io_evidence_verified_on_E'] and cfg['named_reference_files']==0
    assert call(['lfs','getdirstripe','-i',str(ROOT)]).strip()=='0'
    rawquota=call(['lfs','quota','-v','-p','31181','/home/changze'])
    mdt=next(line.split() for line in rawquota.splitlines() if 'fs01-MDT0000' in line)
    assert int(mdt[7])-int(mdt[5])>=32
"""
    assert submit.count(before)==1;submit=submit.replace(before,after)
    submit=submit.replace("    dest.mkdir(parents=True)","    subprocess.check_call(['lfs','mkdir','-i','0','-c','1',str(dest)])")
    submit=submit.replace("historical_summed_requests_SU=prior['cumulative_requested_SU']","historical_summed_requests_SU=prior['cumulative_requested_SU']+5/60")
    submit=submit.replace("quota_snapshot=quota,df=df,df_inodes=di,","quota_snapshot=quota,raw_project_quota=rawquota,df=df,df_inodes=di,")
    submit=submit.replace("str(ROOT/'logs/storage-io-v4-%j.out')","str(ROOT/'storage-io-v4-%j.out')")
    ast.parse(submit);files['submit_storage_correction_v4.py']=submit.encode()
    plan=dict(status='CORRECTED_ZERO_OBSERVATION_STORAGE_PILOT',evidence_verified_on_E=True,
              evidence_archive_sha256='051d016a353fc4c743e9f7aee5ae6f8ddb0d3a17212d13c1fcd8081f65f9b4f2',
              failed_io_evidence_verified_on_E=True,failed_io_manifest_sha256=evidence['manifest_sha256'],
              home_project=31181,output_MDT=0,immutable_fixture_directory=OLD+'/fixtures',
              named_reference_files=0,original_disk_fixture_bytes_are_reference=True,new_training_transitions=0,
              requested_SU=5/60,wall_minutes=5,cpus=1,memory_MiB=2048,automatic_retries=0)
    files['pilot-plan-v4.json']=enc(plan);files['CLAUDE_TASK_authorized.md']=review
    sbatch='''#!/usr/bin/env bash
set -euo pipefail
umask 077
root=__ROOT__
node=/tmp/changze-x12-storage-v4-${SLURM_JOB_ID:?}
mkdir "$node"
mkdir "$node/tmp" "$node/cache"
export TMPDIR="$node/tmp" TMP="$node/tmp" TEMP="$node/tmp" XDG_CACHE_HOME="$node/cache"
export NUMBA_CACHE_DIR="$node/cache/numba" MPLCONFIGDIR="$node/cache/matplotlib"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$root"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B pilot_virtual_store_v4.py --fixtures "__OLD__/fixtures" --out "$root/pilot-out-v4"
'''
    files['pilot.sbatch']=sbatch.replace('__ROOT__',ROOT).replace('__OLD__',OLD).encode()
    hashes={n:hashlib.sha256(b).hexdigest() for n,b in files.items()}
    files['SHA256SUMS']=''.join(h+'  '+n+'\n' for n,h in hashes.items()).encode()
    folder=R/'storage-correction-release-v4';archive=R/'x12-storage-correction-v4.tar.gz';assert not folder.exists() and not archive.exists()
    assert (C/'CLAUDE_TASK.md').read_bytes()==review
    for n,b in files.items():put(folder/n,b)
    with tarfile.open(archive,'x:gz') as tf:
        for n,b in files.items():
            m=tarfile.TarInfo(n);m.size=len(b);tf.addfile(m,io.BytesIO(b))
    result=dict(status='STORAGE_CORRECTION_V4_FROZEN_NOT_SUBMITTED',archive=str(archive),archive_sha256=sha(archive),
                manifest_sha256=sha(folder/'SHA256SUMS'),review_sha256=a.expected_review_sha256,remote_root=ROOT,files=hashes,
                requested_SU=5/60,new_training_transitions=0,existing_cluster_files_unchanged=True)
    put(R/'STORAGE_CORRECTION_MANIFEST_v4.json',enc(result));print(json.dumps({k:v for k,v in result.items() if k!='files'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-review-sha256',required=True);main(p.parse_args())
