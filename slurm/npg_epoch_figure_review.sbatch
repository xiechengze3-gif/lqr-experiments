#!/usr/bin/env bash
#SBATCH --job-name=lqr-epoch-figure
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
result=/scratch/user/changze/lqr_experiments/results/npg-epoch-1661b50a636f09aa
runtime="$result/runtime/figure-$SLURM_JOB_ID"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache"
export MPLCONFIGDIR="$result/runtime/20058099-single/cache/matplotlib"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B \
  "$result/source/npg_epoch_figure_review.py" --root "$result"
