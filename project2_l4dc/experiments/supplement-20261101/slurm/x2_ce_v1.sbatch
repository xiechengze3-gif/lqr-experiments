#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
release=/scratch/user/changze/lqr_experiments/releases/supplement-20261101-x2-ce-v1
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
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B ce_suite.py --config configs/X2_v1.json --phase pilot --bundle "${SLURM_ARRAY_TASK_ID:?}"
