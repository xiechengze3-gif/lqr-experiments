#!/usr/bin/env bash
#SBATCH --job-name=lqr-rank-preview
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
result=$1
runtime="$result/runtime/preview-$SLURM_JOB_ID"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH=/scratch/user/changze/lqr_experiments/releases/7f5c6de07fb244ab PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B "$result/source/npg_rank_preview.py" --output "$result"
