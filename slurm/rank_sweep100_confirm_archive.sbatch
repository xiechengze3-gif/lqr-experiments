#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
set -euo pipefail
root=/scratch/user/changze/lqr_experiments
name=rank-sweep100-confirm-20261016
result="$root/results/$name"
mkdir -p "$root/archives"
myproject > "$result/account_balance_at_archive.txt"
sacct -X -j "$1" -n -P --format=JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU > "$result/slurm_accounting_before_archive.tsv"
sacct -j "$1" -n -P --format=JobID,State,MaxRSS > "$result/slurm_peak_memory.tsv"
tar -czf "$root/archives/$name.tar.gz" -C "$root" \
  --transform='s,^results/,,' --transform='s,^releases/,source/,' \
  "results/$name" "releases/$name" \
  results/rank-sweep100-final-20261016 releases/rank-sweep100-final-20261016 \
  results/rank-sweep100-20261016 releases/rank-sweep100-20261016
sha256sum "$root/archives/$name.tar.gz" > "$root/archives/$name.tar.gz.sha256"
cat "$root/archives/$name.tar.gz.sha256"
