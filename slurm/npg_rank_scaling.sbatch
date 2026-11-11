#!/usr/bin/env bash
#SBATCH --job-name=lqr-npg-rank
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=04:00:00
set -euo pipefail
engine=$1
supplement=$2
manifest=$3
result=$4
mode=$5
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/npg-rank-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-single}"
mkdir -p "$runtime/tmp" "$runtime/cache" "$result/raw" "$result/report"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$engine" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$engine"
sha256sum -c DENSE_SHA256SUMS
cd "$supplement"
sha256sum -c NPG_RANK_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
if [[ "$mode" == report ]]; then
  "$python_bin" -B scripts/npg_rank_report.py --manifest "$manifest" --output "$result"
elif [[ "$mode" == verify ]]; then
  "$python_bin" -B scripts/npg_precision_audit.py verify
  "$python_bin" -B scripts/npg_batched_collector.py
else
  "$python_bin" -B scripts/npg_rank_scaling.py "$mode" --manifest "$manifest" --task-id "${SLURM_ARRAY_TASK_ID:-0}" --output "$result"
fi
