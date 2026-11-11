#!/usr/bin/env bash
#SBATCH --ntasks=1
set -euo pipefail
release=$1
result=$2
algorithm=${3:-all}
if [[ "$algorithm" == all ]]; then
  report="$result/report"
  test -s "$report/numerical_audit.json"
  mkdir -p "$result/source"
  cp -a "$release/." "$result/source/"
  archive="/scratch/user/changze/lqr_experiments/packages/$(basename "$result")-complete.tar.gz"
  tar -czf "$archive" --exclude='runtime' --exclude='numba-cache' --exclude='REPORT_SCHEMA_FIXTURE_NOT_EXPERIMENT' -C "$(dirname "$result")" "$(basename "$result")"
else
  report="$result/report-${algorithm,,}"
  test -s "$report/numerical_audit.json"
  archive="/scratch/user/changze/lqr_experiments/packages/$(basename "$result")-${algorithm,,}-report.tar.gz"
  tar -czf "$archive" -C "$result" "report-${algorithm,,}"
fi
sha256sum "$archive" > "$archive.sha256"
