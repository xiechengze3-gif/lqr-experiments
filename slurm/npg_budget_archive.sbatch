#!/usr/bin/env bash
#SBATCH --job-name=lqr-npg-budget-archive
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
set -euo pipefail
result=$1
jobs=$2
root=/scratch/user/changze/lqr_experiments
case "$(realpath -m "$result")" in "$root/results/npg-budget-"*) ;; *) exit 2 ;; esac
cd "$result/source"
sha256sum -c NPG_BUDGET_SHA256SUMS
cd "$result/engine"
sha256sum -c DENSE_SHA256SUMS
sacct -j "$jobs" --format=JobID,State,Elapsed,ExitCode -P > "$result/report/slurm_audit.txt"
name=$(basename "$result")
archive="$root/packages/npg-budget-complete-${name#npg-budget-}.tar.gz"
tar --exclude=runtime --exclude=numba-cache --exclude=__pycache__ --exclude=.runtime \
  -czf "$archive" -C "$root/results" "$name"
sha256sum "$archive" > "$archive.sha256"
stat -c %s "$archive" > "$archive.bytes"
cat "$archive.sha256" "$archive.bytes"
