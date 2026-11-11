#!/usr/bin/env bash
#SBATCH --account=132685389143
#SBATCH --partition=short
#SBATCH --job-name=lqr-cost-benchmark
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=/scratch/user/changze/lqr_experiments/results/resource-audit-20261009/benchmark-%j.log
set -euo pipefail
audit=/scratch/user/changze/lqr_experiments/results/resource-audit-20261009
export TMPDIR="$audit/tmp" TEMP="$audit/tmp" TMP="$audit/tmp"
export XDG_CACHE_HOME="$audit/cache" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export PYTHONPATH=/scratch/user/changze/lqr_experiments/releases/rank-multiseed-2a95058c9c562fd9/scripts
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B "$audit/grace_lstd_cost_benchmark.py" --output "$audit/benchmark.json"
