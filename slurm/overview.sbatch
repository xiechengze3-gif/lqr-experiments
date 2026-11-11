#!/usr/bin/env bash
#SBATCH --job-name=lqr-rank-figure
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
: "${SLURM_JOB_ID:?Submit via Slurm}"
root=/scratch/user/changze/lqr_experiments
output="$root/results/overview-20261007"
runtime="$output/runtime/$SLURM_JOB_ID"
mkdir -p "$runtime/tmp" "$runtime/cache" "$root/cache/matplotlib"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache"
export MPLCONFIGDIR="$root/cache/matplotlib" MPLBACKEND=Agg
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cache_source="$root/results/pilot-5d78e80516eb6812/runtime/20042274-single/cache/matplotlib"
if [[ -d "$cache_source" ]]; then
  cp -n "$cache_source"/fontlist-*.json "$root/cache/matplotlib/" || true
fi
scontrol show job "$SLURM_JOB_ID" > "$runtime/slurm_request.txt"
sha256sum "$root/ops/plot_overview.py" > "$output/plot_source.sha256"
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B "$root/ops/plot_overview.py" \
  --root "$root/results" --output "$output/rank_overview"
