#!/usr/bin/env bash
#SBATCH --job-name=lqr-research-delivery
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
set -euo pipefail
supplement=$1
result=/scratch/user/changze/lqr_experiments/results/dense-delivery-7f5c6de07fb244ab
mkdir -p "$result/runtime/$SLURM_JOB_ID/tmp" "$result/runtime/$SLURM_JOB_ID/cache"
export TMPDIR="$result/runtime/$SLURM_JOB_ID/tmp" TEMP="$result/runtime/$SLURM_JOB_ID/tmp" TMP="$result/runtime/$SLURM_JOB_ID/tmp"
export XDG_CACHE_HOME="$result/runtime/$SLURM_JOB_ID/cache" MPLCONFIGDIR="$result/runtime/$SLURM_JOB_ID/cache/matplotlib"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$supplement"
sha256sum -c DELIVERY_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/research_delivery.py
