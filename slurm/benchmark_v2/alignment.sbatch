#!/usr/bin/env bash
#SBATCH --job-name=plm_v2_alignment
set -euo pipefail
: "${BENCHMARK_REPO:?Set BENCHMARK_REPO to the checkout}"
: "${BENCHMARK_PLAN:?Set BENCHMARK_PLAN to the normalized plan.json}"
: "${BENCHMARK_OUTPUT:?Set BENCHMARK_OUTPUT to a scratch output directory}"
: "${SLURM_ARRAY_TASK_ID:?Submit with --array}"
cd "$BENCHMARK_REPO"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
"${BENCHMARK_PYTHON:-python}" -m perturb_lm.sklearn_api.execution run \
  --plan "$BENCHMARK_PLAN" --row "$SLURM_ARRAY_TASK_ID" --stage alignment \
  --out "$BENCHMARK_OUTPUT" --data-root "${BENCHMARK_DATA_ROOT:-$BENCHMARK_REPO}"
