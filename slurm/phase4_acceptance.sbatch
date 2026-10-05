#!/usr/bin/env bash
#SBATCH --job-name=plm_acceptance
#SBATCH --cpus-per-task=4
#SBATCH --mem=16g
#SBATCH --time=01:30:00
set -euo pipefail
: "${SLURM_JOB_ID:?Run with sbatch}"
: "${ACCEPT_REPO:?Set the target checkout}"
: "${ACCEPT_ENV:?Set its installed virtual environment}"
: "${ACCEPT_OUT:?Set a new output directory outside the checkout}"
: "${ACCEPT_DRIVER:?Set the acceptance runner path}"
module load "${ACCEPT_MODULE:-python/3.11}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MPLBACKEND=Agg
export PATH="$ACCEPT_ENV/bin:$PATH"
exec "$ACCEPT_ENV/bin/python" "$ACCEPT_DRIVER" \
  --repo "$ACCEPT_REPO" --out "$ACCEPT_OUT"
