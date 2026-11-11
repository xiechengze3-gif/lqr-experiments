#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=ce-npg-arguments-20261028
release=$base/releases/$name
out=$base/results/$name
cache=$base/cache/$name
temp=$base/tmp/$name
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
printf '%s  %s\n' 'b2a1be2e61e9615831cc739bbe4c2416154b5e8ee0fcf0ad9ea1493c8c83a426' "$out/visual-review.py" | sha256sum -c -
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B "$out/visual-review.py"
