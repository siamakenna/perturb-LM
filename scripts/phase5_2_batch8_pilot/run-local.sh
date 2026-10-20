#!/bin/bash
set -euo pipefail
umask 077
export PATH="$HOME/.local/bin:$PATH"
export UV_SYSTEM_CERTS=true PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
unset PYTHONHOME PYTHONPATH

MODE="${1:?Usage: bash run-local.sh prepare WORK_ROOT | score WORK_ROOT PLAN_SHA256}"
WORK="${2:?Supply the existing Phase 5.2 work folder}"
WORK="$(cd -P "$WORK" && pwd)"
HERE="$(cd -P "$(dirname "$0")" && pwd)"
test -f "$WORK/python-path.txt"
test ! -L "$WORK/python-path.txt"
BASE_PYTHON="$(cat "$WORK/python-path.txt")"
test -x "$BASE_PYTHON"

if [ "$MODE" = prepare ]; then
  UV="${P52_UV:-$HOME/Downloads/perturb-lm-jump-images.ktX3NO/preparation.5owSaA/runtime/uv-aarch64-apple-darwin/uv}"
  test -x "$BASE_PYTHON"
  test -x "$UV"
  RUN="$("$BASE_PYTHON" - "$HERE" "$WORK" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from path_contract import PathContract
print(PathContract(sys.argv[2]).create_run_directory('phase52-pilot.'))
PY
)"
  mkdir "$RUN/kit"
  cp "$HERE"/*.py "$HERE/run-local.sh" "$HERE/requirements.txt" "$HERE/README.txt" "$HERE/VALIDATION.txt" "$RUN/kit/"
  exec > >(tee "$RUN/preparation.log") 2>&1
  trap 'printf "\nWorking folder: %s\n" "$RUN"' EXIT
  printf 'Preparing one local pilot in: %s\n' "$RUN"
  "$UV" --no-config venv --python "$BASE_PYTHON" "$RUN/venv"
  PYTHON="$RUN/venv/bin/python"
  "$UV" --no-config pip install --python "$PYTHON" --only-binary=:all: -r "$RUN/kit/requirements.txt"
  "$UV" --no-config pip check --python "$PYTHON"
  "$UV" --no-config pip freeze --python "$PYTHON" > "$RUN/environment-freeze.txt"
  (cd "$RUN/kit" && "$PYTHON" -m unittest discover -s . -p 'test_*.py' -v)
  "$PYTHON" "$RUN/kit/pilot.py" prepare --work-root "$WORK" --out "$RUN/plan"
  (cd "$RUN/plan" && shasum -a 256 -c SHA256SUMS)
  test ! -L "$WORK/latest-batch8-pilot.txt" || { echo 'STOP: latest pilot pointer is a symlink.'; exit 1; }
  if [ -e "$WORK/latest-batch8-pilot.txt" ] && [ ! -f "$WORK/latest-batch8-pilot.txt" ]; then
    echo 'STOP: latest pilot pointer must be absent or a regular file.'
    exit 1
  fi
  POINTER_TMP="$(mktemp "$WORK/.latest-batch8-pilot.XXXXXX")"
  printf '%s\n' "$RUN" > "$POINTER_TMP"
  mv -f "$POINTER_TMP" "$WORK/latest-batch8-pilot.txt"
  printf '\nREADY FOR REVIEW: %s/plan/REPORT.html\n' "$RUN"
  printf 'No retrieval scoring has run. Approval SHA: '
  awk '{print $1}' "$RUN/plan/plan.sha256"
  open "$RUN/plan/REPORT.html" || true
elif [ "$MODE" = score ]; then
  APPROVAL="${3:?Supply the SHA256 shown in the reviewed plan report}"
  RUN="$("$BASE_PYTHON" - "$HERE" "$WORK" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from path_contract import PathContract
paths = PathContract(sys.argv[2])
paths.validate_output_root()
print(paths.input_directory(paths.read_pointer('latest-batch8-pilot'), within=paths.outputs))
PY
)"
  ACTUAL="$("$BASE_PYTHON" - "$HERE" "$WORK" "$RUN" <<'PY'
import hashlib
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from path_contract import PathContract
paths, run = PathContract(sys.argv[2]), Path(sys.argv[3])
plan = paths.read_bytes(run / 'plan' / 'plan.json', within=paths.outputs)
paths.fresh_output(run / 'results', forbidden=(run / 'plan',))
if (run / 'scoring.log').exists() or (run / 'scoring.log').is_symlink():
    raise ValueError('A scoring log already exists; preserve and inspect the previous attempt.')
current = Path(sys.argv[1])
archived = paths.input_directory(run / 'kit', within=paths.outputs)
names = {path.name for path in current.glob('*.py')}
if names != {path.name for path in archived.glob('*.py')}:
    raise ValueError('The recorded pilot has a different Python implementation; its approval cannot be reused here.')
for name in sorted(names):
    if paths.read_bytes(archived / name, within=paths.outputs) != (current / name).read_bytes():
        raise ValueError('The recorded pilot has different implementation bytes; its approval cannot be reused here.')
print(hashlib.sha256(plan).hexdigest())
PY
)"
  test "$APPROVAL" = "$ACTUAL" || { echo 'STOP: supplied approval does not match this plan.'; exit 1; }
  test ! -e "$RUN/results" || { echo 'STOP: results already exist; open them rather than rerunning.'; exit 1; }
  exec > >(tee "$RUN/scoring.log") 2>&1
  trap 'printf "\nWorking folder: %s\n" "$RUN"' EXIT
  "$RUN/venv/bin/python" "$RUN/kit/pilot.py" score --work-root "$WORK" \
    --plan-dir "$RUN/plan" --approve-plan-sha256 "$APPROVAL" --out "$RUN/results"
  (cd "$RUN/results" && shasum -a 256 -c SHA256SUMS)
  printf '\nCOMPLETE. Attach only: %s/results/pilot-summary.json\n' "$RUN"
  open "$RUN/results/REPORT.html" || true
  open -R "$RUN/results/pilot-summary.json" || true
else
  echo 'STOP: mode must be prepare or score.'
  exit 1
fi
