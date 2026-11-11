#!/usr/bin/env bash
#SBATCH --job-name=lqr-rank-limits
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
: "${SLURM_JOB_ID:?Submit via Slurm}"
root=/scratch/user/changze/lqr_experiments
runtime="$root/results/diagnostics-197699f5/runtime/$SLURM_JOB_ID"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B "$root/ops/diagnose_limits.py" \
  --release "$root/releases/5d78e80516eb6812" \
  --manifest "$root/releases/5d78e80516eb6812/configs/pilot.json" \
  --output "$root/results/diagnostics-197699f5/ideal_limits.json"
