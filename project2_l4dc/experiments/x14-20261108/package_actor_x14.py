"""Package unchanged X9 sources and independent X14 launch controls."""
import ast
import hashlib
import io
import json
import tarfile
from pathlib import Path

from freeze_protocol import ROOT, EXPERIMENTS, X9, X9_SOURCES


REMOTE = '/scratch/user/changze/lqr_experiments/tmp/x14-20261108'
PYTHON = '/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    protocol = (ROOT / 'PROTOCOL_v1.md').read_bytes()
    assert b'Frozen input hashes' in protocol
    payload = {f'source-v1/{name}': (X9/name).read_bytes() for name in X9_SOURCES}
    assert {Path(n).name:sha(b) for n,b in payload.items()} == X9_SOURCES
    for name in ('run_actor_x14.py','admit_x14.py','config-x14a-v1.json','config-x14b-v1.json'):
        payload['source-v1/'+name if name.startswith('run_') else name] = (ROOT/name).read_bytes()
    payload['source-v1/virtual_task_store_v2.py'] = (EXPERIMENTS/'x12-20261106/virtual_task_store_v2.py').read_bytes()
    config = json.loads(payload['config-x14a-v1.json'])
    for name, h in config['baseline_sources'].items():
        data = (X9/name).read_bytes()
        assert sha(data)==h
        payload['source-v1/'+name]=data
    for row in config['baseline_models'].values():
        data=(X9/row['path']).read_bytes()
        assert sha(data)==row['sha256']
        payload['source-v1/'+row['path']]=data
    payload['PROTOCOL_v1.md']=protocol
    for item in ('a','b'):
        for stage in ('pilot','formal'):
            script=f'''#!/bin/bash
set -euo pipefail
umask 077
r={REMOTE}
cd "$r"
sha256sum -c SHA256SUMS >/dev/null
export TMPDIR="$r/cache-${{SLURM_JOB_ID:?}}-${{SLURM_ARRAY_TASK_ID:?}}"
mkdir "$TMPDIR"
export TMP="$TMPDIR" TEMP="$TMPDIR" XDG_CACHE_HOME="$TMPDIR" NUMBA_CACHE_DIR="$TMPDIR/numba" MPLCONFIGDIR="$TMPDIR/mpl"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
exec {PYTHON} -B "$r/source-v1/run_actor_x14.py" {item} {stage} --config "$r/config-x14{item}-v1.json" --output "$r" --index "$SLURM_ARRAY_TASK_ID"
'''
            payload[f'{item}-{stage}.sbatch']=script.encode()
    for name, data in payload.items():
        if name.endswith('.py'):
            ast.parse(data, filename=name)
    files = {n:sha(b) for n,b in payload.items()}
    payload['SHA256SUMS']=''.join(f'{h}  {n}\n' for n,h in files.items()).encode()
    package=ROOT/'actor-x14-release-v1.tar.gz'
    with tarfile.open(package,'x:gz') as tf:
        for n,b in payload.items():
            member=tarfile.TarInfo(n)
            member.size=len(b)
            member.mode=0o600
            tf.addfile(member,io.BytesIO(b))
    manifest=dict(status='ACTOR_RELEASE_FROZEN', archive_sha256=sha(package.read_bytes()),
                  manifest_sha256=sha(payload['SHA256SUMS']), files=files, remote_root=REMOTE)
    with (ROOT/'ACTOR_RELEASE_v1.json').open('x',encoding='utf-8') as f:
        json.dump(manifest,f,indent=2)
    print(json.dumps({k:v for k,v in manifest.items() if k!='files'}))


if __name__=='__main__':
    main()
