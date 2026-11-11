#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --time=06:00:00
set -euo pipefail
engine=$1
release=$2
result=$3
mode=$4
profile=${5:-none}
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/approx-tail-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-single}"
mkdir -p "$runtime/tmp" "$runtime/cache" "$result/reference" "$result/report" "$result/$profile/raw"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export LQR_TAIL_SYSTEM_CACHE="$result/systems"
if [[ "$mode" == verify ]]; then export LQR_TAIL_BUILD_CACHE=1; else export LQR_TAIL_BUILD_CACHE=0; fi
export PYTHONPATH="$release/scripts:$engine" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1} MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1} OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1} NUMBA_NUM_THREADS=1
cd "$engine"
sha256sum -c DENSE_SHA256SUMS
cd "$release"
sha256sum -c APPROX_TAIL_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
if [[ "$mode" == report || "$mode" == gate ]]; then
  "$python_bin" -B scripts/approx_tail_report.py "$mode" --manifest configs/approx_tail_suite.json --output "$result"
else
  "$python_bin" -B scripts/approx_tail_run.py "$mode" --manifest configs/approx_tail_suite.json --output "$result" --profile "$profile" --task-id "${SLURM_ARRAY_TASK_ID:-0}"
fi
