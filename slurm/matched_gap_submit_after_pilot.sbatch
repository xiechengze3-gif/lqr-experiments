#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:02:00
set -euo pipefail
route=$1
[[ "$route" == npg || "$route" == pi ]]
# This short controller starts only after every pilot array element completes.
# The script checks all25 pairs, distinct formal seeds, measured task time,
# resource limits and scratch capacity before creating any formal array.
bash /scratch/user/changze/lqr_experiments/releases/matched-gap-memory-ops-20261019/submit_matched_gap_confirm.sh "$route"
