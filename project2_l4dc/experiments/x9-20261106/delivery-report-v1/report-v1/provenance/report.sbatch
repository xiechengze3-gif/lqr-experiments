#!/usr/bin/env bash
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/x9-20261106-report-v1
cache=$base/cache/x9-20261106
temp=$base/tmp/x9-20261106/job-${SLURM_ARRAY_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
python=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python" -B analyze_x9.py --config formal-config.json
"$python" -B render_report.py --config formal-config.json
"$python" -B copy_report_provenance.py
"$python" -B transfer_report.py pack --archive "$base/tmp/x9-20261106/x9-report-v1.tar.gz"
