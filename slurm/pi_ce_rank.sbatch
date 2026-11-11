#!/usr/bin/env bash
#SBATCH --job-name=lqr-cross-rank
#SBATCH --ntasks=1
#SBATCH --time=04:00:00
set -euo pipefail
engine=$1
release=$2
result=$3
profile=$4
mode=$5
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/cross-rank-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-single}"
mkdir -p "$runtime/tmp" "$runtime/cache" "$result/$profile/raw" "$result/report"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$engine" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1} MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1} OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1} NUMBA_NUM_THREADS=1
cd "$engine"
sha256sum -c DENSE_SHA256SUMS
cd "$release"
sha256sum -c CROSS_RANK_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest="$release/configs/cross_rank_$profile.json"
if [[ "$mode" == report ]]; then
  "$python_bin" -B scripts/pi_ce_rank_report.py --release "$release" --output "$result"
elif [[ "$profile" == npg-* ]]; then
  "$python_bin" -B scripts/npg_rank_scaling.py "$mode" --manifest "$manifest" --task-id "${SLURM_ARRAY_TASK_ID:-0}" --output "$result/$profile"
else
  "$python_bin" -B scripts/pi_ce_rank.py "$mode" --manifest "$manifest" --task-id "${SLURM_ARRAY_TASK_ID:-0}" --output "$result/$profile"
fi
