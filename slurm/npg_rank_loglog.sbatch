#!/usr/bin/env bash
#SBATCH --job-name=lqr-npg-rank-loglog
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:10:00
set -euo pipefail
root=/scratch/user/changze/lqr_experiments
review="$root/results/npg-budget-loglog-e93b7ffa7fca793e"
mkdir -p "$review/runtime/tmp" "$review/runtime/cache"
export TMPDIR="$review/runtime/tmp" TEMP="$review/runtime/tmp" TMP="$review/runtime/tmp"
export XDG_CACHE_HOME="$review/runtime/cache" MPLCONFIGDIR="$review/runtime/cache/matplotlib"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$review"
sha256sum -c LOGLOG_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python_bin" -B plot_npg_rank_loglog.py --result "$root/results/npg-budget-e93b7ffa7fca793e" \
    --output "$review"
sha256sum *.png *.pdf loglog_diagnostics.json > OUTPUT_SHA256SUMS
tar --exclude=runtime -czf "$root/packages/npg-budget-loglog-e93b7ffa7fca793e.tar.gz" \
    -C "$root/results" npg-budget-loglog-e93b7ffa7fca793e
sha256sum "$root/packages/npg-budget-loglog-e93b7ffa7fca793e.tar.gz" \
    > "$root/packages/npg-budget-loglog-e93b7ffa7fca793e.tar.gz.sha256"
