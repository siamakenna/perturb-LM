# Known-Good Local Run Checklist

Use this checklist before handing the repository to a collaborator or before starting Phase 3 model work.

## 1. Clean Repository State

```bash
git status --short
```

Expected:

- source/docs/test changes are intentional
- generated outputs are ignored
- `data/`, `outputs/`, `models/`, raw images, embeddings, indexes, and parquet outputs are not staged

## 2. Install And Test

```bash
python -m pip install -e ".[dev]"
pytest
```

Expected:

- all synthetic tests pass
- no internet or real data is required

## 3. Phase 1 Synthetic Smoke

```bash
python scripts/run_phase1_smoke.py --out outputs/phase1_smoke
```

Expected:

- manifests are generated from fixtures
- queries are generated
- retrieval runs
- perturbation-level evaluation runs

This validates software behavior only.

## 4. Phase 2 Synthetic JUMP Smoke

```bash
python scripts/run_phase2_jump_smoke.py --out outputs/phase2_jump_smoke
```

Expected:

- synthetic CPJUMP1-like profiles are created locally
- inventory, index, diagnostics, text-profile retrieval, and report files are generated
- outputs remain ignored by git

This validates the report path only.

## 5. Phase 2 Real JUMP Baseline

Run only when local JUMP CPJUMP1 profiles are present under `data/raw/jump_pilot/`.

```bash
python scripts/run_phase2_local_report.py \
  --data-root data/raw/jump_pilot \
  --out outputs/jump_pilot_real_baseline

python scripts/check_phase2_readiness.py \
  --root outputs/jump_pilot_real_baseline \
  --out outputs/jump_pilot_real_baseline/readiness_check.json
```

Expected:

- `baseline_manifest.json` is written
- `phase2_jump_report.md` is written
- readiness check passes or reports explicit warnings
- any one-batch limitation is acknowledged

This is still a reproducibility and baseline validation step, not a biological retrieval claim.

## 6. RxRx Real-Data Path

Run only when local RxRx files are present as described in `docs/REAL_RXRX_SETUP.md`.

```bash
python scripts/audit_real_data.py \
  --data-root data/raw \
  --out outputs/real_data_inventory.json
```

For RxRx19a first:

```bash
python scripts/build_rxrx_manifests.py \
  --dataset rxrx19a \
  --data-root data/raw \
  --out data/processed

python scripts/build_queries.py \
  --dataset rxrx19a \
  --manifest data/processed/rxrx19a_perturbation_manifest.parquet \
  --out data/processed

python scripts/run_retrieval.py \
  --dataset rxrx19a \
  --queries data/processed/rxrx19a_queries.csv \
  --site-manifest data/processed/rxrx19a_site_manifest.parquet \
  --mode lexical \
  --top-k 50 \
  --out outputs/rxrx19a_phase1

python scripts/run_eval.py \
  --dataset rxrx19a \
  --queries data/processed/rxrx19a_queries.csv \
  --site-results outputs/rxrx19a_phase1/rxrx19a_site_retrieval_results.parquet \
  --perturbation-results outputs/rxrx19a_phase1/rxrx19a_perturbation_retrieval_results.parquet \
  --site-manifest data/processed/rxrx19a_site_manifest.parquet \
  --out outputs/rxrx19a_phase1_eval

python scripts/run_leakage_diagnostics.py \
  --dataset rxrx19a \
  --queries data/processed/rxrx19a_queries.csv \
  --site-manifest data/processed/rxrx19a_site_manifest.parquet \
  --out outputs/rxrx19a_leakage
```

Expected:

- manifest build report names the source metadata file and mapped columns
- retrieval results aggregate to perturbation-level scoring
- leakage diagnostics report positives across batches, plates, wells, and splits when labels are available

## 7. Optional Embedding Index

Run only when local embeddings are available.

```bash
python scripts/build_index.py \
  --dataset rxrx19a \
  --manifest data/processed/rxrx19a_site_manifest.parquet \
  --embeddings data/raw/rxrx19a_embeddings.csv \
  --out outputs/rxrx19a_index
```

Expected:

- index metadata reports matched and unmatched rows
- generated index files remain ignored

## 8. Optional Local Image Sanity Check

Run only with a tiny local image sample. Do not download full raw image archives by default.

```bash
python scripts/render_composites.py \
  --manifest data/processed/rxrx19a_site_manifest.parquet \
  --image-root data/raw/rxrx19a/images \
  --out outputs/rxrx19a_composites \
  --limit 20
```

Expected:

- rendered composites are local ignored outputs
- missing image channels are reported
- visual inspection is treated as pipeline validation only

## 9. Final Handoff Check

```bash
git status --short
```

Expected:

- only intentional source/docs/test files are tracked
- no local data or generated outputs are staged

Record for the collaborator:

- command sequence used
- generated report directory
- readiness status
- warnings or limitations
- dataset paths used locally
- known missing assets

