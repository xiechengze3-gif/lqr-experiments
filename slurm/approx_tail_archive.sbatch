#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
set -euo pipefail
release=$1
result=$2
test -s "$result/report/numerical_audit.json"
test -s "$result/report/summary.json"
mkdir -p "$result/source"
cp -a "$release/." "$result/source/"
archive="/scratch/user/changze/lqr_experiments/packages/$(basename "$result")-complete.tar.gz"
tar -czf "$archive" --exclude='runtime' --exclude='numba-cache' -C "$(dirname "$result")" "$(basename "$result")"
sha256sum "$archive" > "$archive.sha256"
