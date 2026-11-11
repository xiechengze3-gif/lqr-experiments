#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:02:00
set -euo pipefail
bash /scratch/user/changze/lqr_experiments/releases/matched-gap-pi-bundle-ops-v2-20261019/submit_matched_gap_pi_bundles.sh
