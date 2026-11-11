#!/usr/bin/env bash
#SBATCH --job-name=lqr-rank-audit-archive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$1
result=$2
jobs=$3
case "$(realpath -m "$result")" in "$base"/results/npg-rank-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/audit-$SLURM_JOB_ID"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$base/releases/7f5c6de07fb244ab" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python_bin" -B "$result/source/npg_rank_quality.py" --release "$release" --output "$result"
sacct -j "$jobs" -X --format=JobID,State,Elapsed -P > "$result/report/slurm_audit.txt"
name=$(basename "$result")
archive="$base/packages/${name/npg-rank-/npg-rank-complete-}.tar.gz"
tar --exclude='*/runtime' --exclude='*/numba-cache' --exclude='*/logs/audit-*' -C "$base/results" -czf "$archive" "$name"
sha256sum "$archive" > "$archive.sha256"
cat "$archive.sha256"
