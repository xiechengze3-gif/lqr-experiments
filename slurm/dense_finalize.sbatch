#!/usr/bin/env bash
#SBATCH --job-name=lqr-dense-final
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:30:00
set -euo pipefail
supplement=$1
overview=$2
precision=$3
mkdir -p "$overview/runtime/$SLURM_JOB_ID/tmp" "$overview/runtime/$SLURM_JOB_ID/cache/matplotlib"
export TMPDIR="$overview/runtime/$SLURM_JOB_ID/tmp" TEMP="$overview/runtime/$SLURM_JOB_ID/tmp" TMP="$overview/runtime/$SLURM_JOB_ID/tmp"
export XDG_CACHE_HOME="$overview/runtime/$SLURM_JOB_ID/cache" MPLCONFIGDIR="$overview/runtime/$SLURM_JOB_ID/cache/matplotlib" MPLBACKEND=Agg
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$supplement"
sha256sum -c FINAL_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/finalize_dense.py --overview "$overview" --precision "$precision" --output "$overview/report"
