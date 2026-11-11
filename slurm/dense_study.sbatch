#!/usr/bin/env bash
#SBATCH --job-name=lqr-dense
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=02:00:00
set -euo pipefail
: "${SLURM_JOB_ID:?Submit via Slurm}"
[[ $# -eq 5 ]] || exit 2
python_bin=$1
release=$2
manifest=$3
result=$4
mode=$5
case "$(realpath -m "$result")" in
  /scratch/user/changze/lqr_experiments/results/dense-* ) ;;
  *) exit 2 ;;
esac
runtime="$result/runtime/${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-single}"
mkdir -p "$runtime/tmp" "$runtime/cache/matplotlib" "$result/raw" "$result/report"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache"
export PIP_CACHE_DIR="$runtime/cache/pip" MPLCONFIGDIR="$runtime/cache/matplotlib" MPLBACKEND=Agg
export NUMBA_CACHE_DIR="$result/numba-cache"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c DENSE_SHA256SUMS
scontrol show job "$SLURM_JOB_ID" > "$runtime/slurm_request.txt"
printf 'SOURCE=%s\nRESULT=%s\nTMPDIR=%s\nNUMBA_CACHE_DIR=%s\n' "$release" "$result" "$TMPDIR" "$NUMBA_CACHE_DIR"
case "$mode" in
  verify) "$python_bin" -B dense_scaling.py verify ;;
  run) "$python_bin" -B dense_scaling.py run --manifest "$manifest" --task-id "${SLURM_ARRAY_TASK_ID:?}" --output "$result/raw" ;;
  report) "$python_bin" -B dense_report.py --manifest "$manifest" --raw "$result/raw" --output "$result/report" ;;
  *) exit 2 ;;
esac
