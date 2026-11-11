#!/usr/bin/env bash
#SBATCH --job-name=lqr-align-report-check
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
base_release=$1
base_result=$2
snapshot="$base_result/report-check"
source "$base_release/slurm/aligned_extension.sbatch" "$base_release" "$snapshot" report
"$python_bin" -B "$base_result/control/aligned_unified_report.py" --release "$base_release" --output "$snapshot" --historical "$base_result/control/historical_endpoints.csv"
