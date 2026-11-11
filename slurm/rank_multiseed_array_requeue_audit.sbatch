#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --requeue
set -euo pipefail
result=$1
mkdir -p "$result/runtime"
if ((${SLURM_RESTART_COUNT:-0} == 0)); then
  printf '{"first_pass":true,"array_job_id":"%s","array_task_id":"%s"}\n' "$SLURM_ARRAY_JOB_ID" "$SLURM_ARRAY_TASK_ID" > "$result/array_requeue_first_pass.json"
  scontrol requeue "${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
else
  test -s "$result/array_requeue_first_pass.json"
  printf '{"status":"PASS","restart_count":%s,"array_job_id":"%s","array_task_id":"%s"}\n' "$SLURM_RESTART_COUNT" "$SLURM_ARRAY_JOB_ID" "$SLURM_ARRAY_TASK_ID" > "$result/array_requeue_audit.json"
fi
