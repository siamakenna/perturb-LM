#!/usr/bin/env bash
#SBATCH --job-name=plm_exam
#SBATCH --cpus-per-task=2
#SBATCH --mem=8g
#SBATCH --time=00:35:00
set -euo pipefail
: "${SLURM_JOB_ID:?Run only inside a reviewed Slurm allocation}"
: "${EXAM_REPO:?Set a clean reviewed source checkout}"
: "${EXAM_ENV:?Set its preinstalled synthetic test environment}"
: "${EXAM_OUT:?Set a fresh private directory outside the checkout}"
: "${EXAM_NAME:?Select one implemented synthetic examination}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
exec "$EXAM_ENV/bin/python" "$EXAM_REPO/scripts/run_phase4_examinations.py" \
  --repo "$EXAM_REPO" --out "$EXAM_OUT" --examination "$EXAM_NAME" --timeout 1800
