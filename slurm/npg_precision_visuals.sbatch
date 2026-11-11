#!/usr/bin/env bash
#SBATCH --job-name=lqr-npg-plots
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
set -euo pipefail
supplement=$1
runtime=/scratch/user/changze/lqr_experiments/results/npg-precision-e7ce4b139191d361/runtime/$SLURM_JOB_ID
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$supplement"
sha256sum -c NPG_VISUAL_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/npg_precision_visuals.py
