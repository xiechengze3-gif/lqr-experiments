"""Freeze the B* pilot-only X14c supplement and its Slurm wrappers."""
from pathlib import Path

from package_actor_x14 import PYTHON, REMOTE
from package_report_x14 import pack, sha


R=Path(__file__).resolve().parent


def main():
    files={f'bstar-v1/{name}':(R/name).read_bytes() for name in ('calibrate_bstar_x14.py','submit_bstar_x14.py')}
    for stage in ('bstar','report'):
        script=f'''#!/bin/bash
set -euo pipefail
umask 077
r={REMOTE}
cd "$r"
sha256sum -c estimation-v1/SHA256SUMS >/dev/null
sha256sum -c bstar-v1/SHA256SUMS >/dev/null
export TMPDIR="$r/cache-c-bstar-${{SLURM_JOB_ID:?}}-${{SLURM_ARRAY_TASK_ID:?}}"
mkdir "$TMPDIR"
export TMP="$TMPDIR" TEMP="$TMPDIR" XDG_CACHE_HOME="$TMPDIR" NUMBA_CACHE_DIR="$TMPDIR/numba" MPLCONFIGDIR="$TMPDIR/mpl"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$r:$r/estimation-v1:$r/source-v1"
exec {PYTHON} -B "$r/bstar-v1/calibrate_bstar_x14.py" {stage}
'''
        files[f'bstar-v1/c-{stage}.sbatch']=script.encode()
    files['bstar-v1/SHA256SUMS']=''.join(f'{sha(data)}  {name}\n' for name,data in files.items()).encode()
    pack('bstar-x14-release-v1',files)


if __name__=='__main__':
    main()
