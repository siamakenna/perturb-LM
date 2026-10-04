# Biowulf Benchmark V2 handoff

This is an operator handoff, not evidence that these commands have run on Biowulf.
The repository does not download data or model weights automatically. Paths,
modules, partitions, GPU types, and allocations marked `REQUIRES BIOWULF REVIEW`
must be confirmed on the cluster.

```bash
git clone https://github.com/siamakenna/perturb-LM.git
cd perturb-LM
git fetch --all --tags --prune
git switch feature/benchmark-v2-scikit
export PLM_CODE="$PWD"
export PLM_RESULTS="/lscratch/$USER/perturb-lm-v2/results"
export PLM_ENV="/lscratch/$USER/perturb-lm-v2/venv"
export PLM_CACHE="/lscratch/$USER/perturb-lm-v2/cache"
export PLM_DATA="/data/$USER/perturb-lm-v2/data"
mkdir -p "$PLM_RESULTS" "$PLM_CACHE" "$PLM_DATA"
```

```bash
sinteractive --cpus-per-task=4 --mem=16g --time=01:00:00
# REQUIRES BIOWULF REVIEW: load the site-approved Python/module toolchain.
python3 -m venv "$PLM_ENV"
source "$PLM_ENV/bin/activate"
python -m pip install --upgrade pip
python -m pip install -e "$PLM_CODE[dev]"
python -m perturb_lm.sklearn_api.execution --help
python -m perturb_lm.sklearn_api.manifest_cli --help
python -m pytest tests/test_benchmark_v2.py -q
python -m pytest -q
```

Generate and run the synthetic smoke chain:

```bash
python -m perturb_lm.sklearn_api.execution plan \
  "$PLM_CODE/configs/benchmark_v2/synthetic_smoke.yaml" \
  --out "$PLM_RESULTS/smoke-plan" --log-root "$PLM_RESULTS/logs"
for row in 0 1 2 3; do
  python -m perturb_lm.sklearn_api.execution run \
    --plan "$PLM_RESULTS/smoke-plan/plan.json" --row "$row" \
    --out "$PLM_RESULTS/smoke-runs" --data-root "$PLM_CODE"
done
```

Validate a staged manifest without copying its data:

```bash
python -m perturb_lm.sklearn_api.manifest_cli \
  --manifest "$PLM_DATA/cpjump1_manifest.yaml" --root "$PLM_DATA" \
  --include-representations
```

Submit exactly one smoke-array index after reviewing the plan:

```bash
sbatch --array=0 --output="$PLM_RESULTS/logs/smoke-%A_%a.out" \
  --error="$PLM_RESULTS/logs/smoke-%A_%a.err" --cpus-per-task=2 --mem=4g \
  --time=00:10:00 \
  --export=ALL,BENCHMARK_REPO="$PLM_CODE",BENCHMARK_PLAN="$PLM_RESULTS/smoke-plan/plan.json",BENCHMARK_OUTPUT="$PLM_RESULTS/smoke-runs",BENCHMARK_DATA_ROOT="$PLM_CODE" \
  "$PLM_CODE/slurm/benchmark_v2/embedding.sbatch"
squeue -u "$USER"
jobhist JOB_ID
```

Stage only approved immutable assets under `$PLM_CACHE` with `asset.json`, exact
catalog revision, completion flag, and checksums. The local model adapter loads
offline and rejects incomplete caches. CellCLIP and OpenPhenom require review of
pinned model code and licenses.

After approved data, models, and relevance contracts are staged, create the explicit
matrix:

```bash
python -m perturb_lm.sklearn_api.execution plan \
  "$PLM_CODE/configs/benchmark_v2/expanded_staged.yaml" \
  --out "$PLM_RESULTS/staged-plan" --log-root "$PLM_RESULTS/logs"
bash -n "$PLM_RESULTS/staged-plan/submit.sh"
```

The checked-in expanded example is intentionally `plan_only` and emits no real-data
submissions. A reviewed production configuration must explicitly enable its workers.
Once runnable rows exist, inspect and run the generated script, then use `squeue`,
`jobhist JOB_ID`, and `sacct -j JOB_ID --format=JobID,State,ExitCode,Elapsed,MaxRSS`.
Resubmit only indices without valid completion markers or with failed checksums.
