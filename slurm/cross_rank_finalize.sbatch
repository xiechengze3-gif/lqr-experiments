#!/usr/bin/env bash
#SBATCH --job-name=lqr-cross-audit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:20:00
set -euo pipefail
engine=$1
release=$2
result=$3
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/cross-rank-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/audit-$SLURM_JOB_ID"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TMP="$runtime/tmp" TEMP="$runtime/tmp" XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$engine" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c CROSS_RANK_SHA256SUMS
cd "$result/source"
sha256sum -c FINALIZE_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python_bin" -B "$result/source/cross_rank_finalize.py" --release "$release" --output "$result"
sacct -j 20057876,20057877,20057886,20057887,20057888,20057889,20057898,20057926,20057927,20057933 --format=JobID,State,ExitCode,Elapsed,AllocCPUS -n > "$result/slurm_audit.txt"
archive="/scratch/user/changze/lqr_experiments/packages/$(basename "$result")-complete.tar.gz"
tar --exclude='*/runtime' --exclude='*/numba-cache' --exclude='*/logs' -czf "$archive" -C "$(dirname "$result")" "$(basename "$result")"
sha256sum "$archive" > "$archive.sha256"
