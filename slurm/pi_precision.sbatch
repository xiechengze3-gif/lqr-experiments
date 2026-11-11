#!/usr/bin/env bash
#SBATCH --job-name=lqr-pi-precision
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=04:00:00
set -euo pipefail
release=$1
supplement=$2
result=$3
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/dense-* ) ;; *) exit 2 ;; esac
mkdir -p "$result/raw" "$result/runtime/$SLURM_JOB_ID/tmp" "$result/runtime/$SLURM_JOB_ID/cache"
export TMPDIR="$result/runtime/$SLURM_JOB_ID/tmp" TEMP="$result/runtime/$SLURM_JOB_ID/tmp" TMP="$result/runtime/$SLURM_JOB_ID/tmp"
export XDG_CACHE_HOME="$result/runtime/$SLURM_JOB_ID/cache" NUMBA_CACHE_DIR="$result/numba-cache"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c DENSE_SHA256SUMS
cd "$supplement"
sha256sum -c PI_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/pi_precision.py --manifest "$release/configs/dense_actor.json" --task-id "${SLURM_ARRAY_TASK_ID:?}" --output "$result/raw"
