"""Formal release cannot be built without X4's own explicit acceptance receipt."""
import hashlib,io,json,tarfile
from control import ROOT,review,sha

checked=review();approval=json.loads((ROOT/'X4/ACCEPTED.json').read_text())
assert approval['decision']=='ACCEPTED' and approval['task_sha256']==checked['task_sha256']
slug='supplement-20261101-x4-formal-v23'
shell='''#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
release=/scratch/user/changze/lqr_experiments/releases/supplement-20261101-x4-formal-v23
base=/scratch/user/changze/lqr_experiments
cache=$base/cache/supplement-20261101
temp=$base/tmp/supplement-20261101/job-${SLURM_JOB_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B x4_formal.py
'''.encode()
names=['engine.py','robustness_x4.py','x4_formal.py','configs/X4_v1.json','X4/ACCEPTED.json','X4/SOURCE_POLICY_MANIFEST.json',
       'tools/submit_pilot_remote.py','tools/submit_x4_formal.py']
contents={name:(ROOT/name).read_bytes() for name in names};contents['slurm/run.sbatch']=shell
hashes={name:hashlib.sha256(payload).hexdigest() for name,payload in contents.items()}
contents['SHA256SUMS']=''.join(h+'  '+name+'\n' for name,h in hashes.items()).encode()
archive=ROOT/'packages'/(slug+'.tar.gz');assert not archive.exists()
with tarfile.open(archive,'w:gz') as tf:
    for name,payload in contents.items():
        info=tarfile.TarInfo(name);info.size=len(payload);tf.addfile(info,io.BytesIO(payload))
manifest=dict(name=slug,archive=str(archive),archive_sha256=sha(archive),source_hashes=hashes,stage='FORMAL',scope='X4_OFFLINE_DIAGNOSTIC')
(ROOT/'packages'/(slug+'.manifest.json')).write_bytes((json.dumps(manifest,indent=2)+'\n').encode());print(json.dumps(manifest,indent=2))
