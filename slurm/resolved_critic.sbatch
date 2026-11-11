#!/usr/bin/env bash
#SBATCH --job-name=lqr-resolved-critic
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=02:00:00
set -euo pipefail
release=$1
instrument=$2
manifest=$3
result=$4
mode=$5
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/dense-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-single}"
mkdir -p "$runtime/tmp" "$runtime/cache/matplotlib" "$result/raw" "$result/report"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache"
export MPLCONFIGDIR="$runtime/cache/matplotlib" MPLBACKEND=Agg NUMBA_CACHE_DIR="$result/numba-cache"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c DENSE_SHA256SUMS
cd "$instrument"
sha256sum -c RESOLVED_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
if [[ "$mode" == run ]]; then
  "$python_bin" -B scripts/resolved_critic.py --manifest "$manifest" --task-id "${SLURM_ARRAY_TASK_ID:?}" --output "$result/raw"
elif [[ "$mode" == report ]]; then
  "$python_bin" -B "$release/dense_report.py" --manifest "$manifest" --raw "$result/raw" --output "$result/report"
else
  exit 2
fi
