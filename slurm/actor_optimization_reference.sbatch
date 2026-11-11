#!/usr/bin/env bash
#SBATCH --job-name=lqr-optimization-reference
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:30:00
set -euo pipefail
release=$1
supplement=$2
result=$3
mkdir -p "$result/runtime/$SLURM_JOB_ID/tmp" "$result/runtime/$SLURM_JOB_ID/cache" "$result/report"
export TMPDIR="$result/runtime/$SLURM_JOB_ID/tmp" TEMP="$result/runtime/$SLURM_JOB_ID/tmp" TMP="$result/runtime/$SLURM_JOB_ID/tmp"
export XDG_CACHE_HOME="$result/runtime/$SLURM_JOB_ID/cache" NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$supplement"
sha256sum -c OPTIMIZATION_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/actor_optimization_reference.py --manifest "$release/configs/dense_actor.json" --output "$result/report/actor_optimization_reference.csv"
