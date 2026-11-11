#!/usr/bin/env bash
#SBATCH --job-name=lqr-first-hit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
set -euo pipefail
: "${SLURM_JOB_ID:?Submit via Slurm}"
root=/scratch/user/changze/lqr_experiments
runtime="$root/results/overview-20261007/runtime/$SLURM_JOB_ID"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B "$root/ops/first_hit_summary.py" \
  --root "$root/results" --output "$root/results/overview-20261007/first_hit_thresholds.csv"
