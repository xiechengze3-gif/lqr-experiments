#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
release=$1
result=$2
mode=$3
case "$(realpath -m "$release")" in /scratch/user/changze/lqr_experiments/releases/ce-precision-zoom-* ) ;; *) exit 2 ;; esac
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/ce-precision-zoom-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-single}"
mkdir -p "$runtime/tmp" "$runtime/cache" "$result/raw" "$result/logs"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib" NUMBA_CACHE_DIR="$result/numba-cache"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
if [[ "$mode" == run ]]; then
  "$python_bin" -B scripts/ce_precision_zoom.py run --output "$result" --task-id "$SLURM_ARRAY_TASK_ID"
else
  "$python_bin" -B scripts/ce_precision_zoom.py report --output "$result"
  root=/scratch/user/changze/lqr_experiments
  name=$(basename "$result")
  mkdir -p "$root/archives"
  tar -czf "$root/archives/$name.tar.gz" -C "$root" --exclude="results/$name/runtime" --exclude="results/$name/numba-cache" "results/$name" "releases/$name"
  sha256sum "$root/archives/$name.tar.gz" > "$root/archives/$name.tar.gz.sha256"
fi
