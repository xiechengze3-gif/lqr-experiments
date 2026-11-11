#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
name=project2-overnight-20261020
base=/scratch/user/changze/lqr_experiments
release=$base/releases/$name
result=$base/results/$name
cache=$base/cache/$name
temp=$base/tmp/$name
mkdir -p "$result/logs" "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS > "$result/logs/source-check-${SLURM_JOB_ID}.txt"
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
exec "$python_bin" -B scripts/project2_overnight.py "$1" --index "${SLURM_ARRAY_TASK_ID:-0}" --manifest "${2:-$release/configs/project2_overnight_20261020.json}"
