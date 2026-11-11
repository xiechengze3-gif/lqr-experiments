#!/usr/bin/env bash
#SBATCH --job-name=lqr-align-report
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=01:00:00
set -euo pipefail
release=$1
result=$2
# The frozen wrapper verifies sources, configures all scratch caches, and runs
# the original independent policy/budget audit before unified postprocessing.
source "$release/slurm/aligned_extension.sbatch" "$release" "$result" report
"$python_bin" -B "$result/control/aligned_unified_report.py" --release "$release" --output "$result" --historical "$result/control/historical_endpoints.csv"
root=/scratch/user/changze/lqr_experiments
name=$(basename "$result")
mkdir -p "$root/archives"
archive="$root/archives/$name.tar.gz"
tar -czf "$archive" -C "$root" --exclude="results/$name/runtime" --exclude="results/$name/numba-cache" --exclude='__pycache__' "results/$name" "releases/$name"
sha256sum "$archive" > "$archive.sha256"
printf '%s\n' "$archive" > "$result/archive_ready.txt"
