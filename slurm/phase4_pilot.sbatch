#!/usr/bin/env bash
#SBATCH --job-name=plm_pilot
#SBATCH --cpus-per-task=2
#SBATCH --mem=8g
#SBATCH --time=00:10:00
set -euo pipefail
: "${SLURM_JOB_ID:?Use a reviewed compute allocation}"
: "${PILOT_CODE:?Set the reviewed checkout on this machine}"
: "${PILOT_ENV:?Set the preinstalled environment on this machine}"
: "${PILOT_MANIFEST:?Set an approved pilot manifest}"
: "${PILOT_APPROVAL:?Set the recorded approval document}"
: "${PILOT_DATA:?Set the approved input root}"
: "${PILOT_ASSETS:?Set the approved model directory}"
: "${PILOT_OUT:?Set a new private output directory}"
test -f "$PILOT_MANIFEST"
test -f "$PILOT_APPROVAL"
test -f "$PILOT_ASSETS/asset.json"
test -d "$PILOT_DATA"
test ! -e "$PILOT_OUT"
cd "$PILOT_CODE"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONPATH="$PILOT_CODE/src"
umask 077
exec "$PILOT_ENV/bin/python" -m perturb_lm.sklearn_api.pilot run \
  --manifest "$PILOT_MANIFEST" --approval "$PILOT_APPROVAL" \
  --data-root "$PILOT_DATA" --asset-root "$PILOT_ASSETS" --out "$PILOT_OUT"
