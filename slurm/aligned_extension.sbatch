#!/usr/bin/env bash
#SBATCH --job-name=lqr-align
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=01:00:00
set -euo pipefail
release=$1
result=$2
mode=$3
case "$(realpath -m "$release")" in /scratch/user/changze/lqr_experiments/releases/aligned-* ) ;; *) exit 2 ;; esac
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/aligned-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-single}"
mkdir -p "$runtime/tmp" "$runtime/cache" "$result/logs"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
cd "$release"
sha256sum -c SHA256SUMS
if [[ "$mode" == benchmark ]]; then
  "$python_bin" -B scripts/aligned_extension.py benchmark --output "$result/benchmark"
elif [[ "$mode" == report ]]; then
  "$python_bin" -B scripts/aligned_extension.py report --output "$result"
else
  test "$mode" = run
  "$python_bin" -B scripts/aligned_extension.py run --task-id "$SLURM_ARRAY_TASK_ID" --output "$result"
fi
