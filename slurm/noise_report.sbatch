#!/usr/bin/env bash
#SBATCH --job-name=lqr-noise-report
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:30:00
set -euo pipefail
supplement=$1
result=$2
mkdir -p "$result/runtime/$SLURM_JOB_ID/tmp" "$result/runtime/$SLURM_JOB_ID/cache/matplotlib"
export TMPDIR="$result/runtime/$SLURM_JOB_ID/tmp" TEMP="$result/runtime/$SLURM_JOB_ID/tmp" TMP="$result/runtime/$SLURM_JOB_ID/tmp"
export XDG_CACHE_HOME="$result/runtime/$SLURM_JOB_ID/cache" MPLCONFIGDIR="$result/runtime/$SLURM_JOB_ID/cache/matplotlib" MPLBACKEND=Agg
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$supplement"
sha256sum -c NOISE_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/noise_report.py --report "$result/report" --output "$result/report"
