# Perturb LM

Perturb LM is a reproducible benchmark and prototype for natural-language retrieval over high-content microscopy perturbation datasets. The user-facing task is text-to-image retrieval, while formal benchmark evaluation aggregates image/site hits to the perturbation level so results are biologically meaningful and robust to replicate structure.

## Current Status

Bootstrap implementation. The repository includes safe downloader scaffolds, RxRx manifest builders, query generation, perturbation-level aggregation, deterministic baselines, metrics, documentation, and tiny synthetic tests that run without internet access or real datasets.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Python 3.10 or 3.11 is recommended. Heavy ML dependencies such as FAISS, torch, transformers, OpenCLIP, and BiomedCLIP are intentionally not required yet.

## Environment Variables

Copy `.env.example` if you want local path overrides:

```bash
cp .env.example .env
```

Supported variables:

- `PERTURB_LM_DATA_ROOT`
- `PERTURB_LM_RAW_DIR`
- `PERTURB_LM_PROCESSED_DIR`
- `PERTURB_LM_OUTPUT_DIR`
- `PERTURB_LM_MODEL_DIR`

Defaults are `data/raw`, `data/processed`, `outputs`, and `models`.

## Safe Data Policy

Full image archives are never downloaded by default. Metadata and embeddings are the first supported downloads. Raw images must be explicitly requested and require `--confirm-large-download`. Data, embeddings, images, model files, parquet files, numpy arrays, and generated outputs should not be committed.

## Phase 1 Commands

For real local RxRx metadata and embedding placement, see `docs/REAL_RXRX_SETUP.md`.
For the real-image and model baseline workflow, see `docs/PHASE2_REAL_DATA_AND_MODELS.md`.

## Phase 2 JUMP Pilot Commands

The active Phase 2 real-data track is JUMP CPJUMP1 profile-based retrieval under `data/raw/jump_pilot/`. Local real data is optional and ignored by git; raw microscopy images are not part of this PR path yet. This PR covers Adam's Phase 2 profile-infrastructure and diagnostics slice, not the full VLM/text-query project.

Run the one-command synthetic smoke workflow first:

```bash
python scripts/run_phase2_jump_smoke.py
```

Then, when local CPJUMP1 profile files are available:

```bash
python scripts/audit_jump_pilot.py --summary-only --max-columns-to-print 20
python scripts/build_jump_profile_index.py
python scripts/run_jump_profile_diagnostics.py --filtered-presets
```

The smoke workflow validates software only. One-plate and five-profile local sanity runs are useful for checking the audit/index/diagnostics path, but they are not final biological claims. Unfiltered retrieval can be inflated by plate and well-position effects; filtered diagnostics are stronger evidence, especially when interpreted alongside `n_evaluable_queries`.

Dry-run safe metadata downloads:

```bash
python scripts/download_rxrx.py --dataset rxrx1 --download metadata --dry-run
python scripts/download_rxrx.py --dataset rxrx19a --download metadata --dry-run
```

Build manifests:

```bash
python scripts/build_rxrx_manifests.py --dataset rxrx1 --data-root data/raw --out data/processed
python scripts/build_rxrx_manifests.py --dataset rxrx19a --data-root data/raw --out data/processed
```

Build queries:

```bash
python scripts/build_queries.py --dataset rxrx1 --manifest data/processed/rxrx1_perturbation_manifest.parquet --out data/processed
python scripts/build_queries.py --dataset rxrx19a --manifest data/processed/rxrx19a_perturbation_manifest.parquet --out data/processed
```

Run retrieval:

```bash
python scripts/run_retrieval.py --dataset rxrx1 --queries data/processed/rxrx1_queries.csv --site-manifest data/processed/rxrx1_site_manifest.parquet --mode lexical --top-k 50 --out outputs/rxrx1_phase1
python scripts/run_retrieval.py --dataset rxrx19a --queries data/processed/rxrx19a_queries.csv --site-manifest data/processed/rxrx19a_site_manifest.parquet --mode lexical --top-k 50 --out outputs/rxrx19a_phase1
```

Run evaluation:

```bash
python scripts/run_eval.py --dataset rxrx1 --queries data/processed/rxrx1_queries.csv --site-results outputs/rxrx1_phase1/rxrx1_site_retrieval_results.parquet --perturbation-results outputs/rxrx1_phase1/rxrx1_perturbation_retrieval_results.parquet --site-manifest data/processed/rxrx1_site_manifest.parquet --out outputs/rxrx1_phase1_eval
```

Run the fixture smoke test:

```bash
python scripts/run_phase1_smoke.py --out outputs/phase1_smoke
```

Run tests:

```bash
pytest
```

Build an optional sklearn embedding index when local embeddings are available:

```bash
python scripts/build_index.py --dataset rxrx1 --manifest data/processed/rxrx1_site_manifest.parquet --embeddings data/raw/rxrx1_embeddings.csv --out outputs/rxrx1_index
```

Create a Phase 1 Markdown report:

```bash
python scripts/make_phase1_report.py --dataset rxrx1 --queries data/processed/rxrx1_queries.csv --site-manifest data/processed/rxrx1_site_manifest.parquet --perturbation-results outputs/rxrx1_phase1/rxrx1_perturbation_retrieval_results.parquet --metrics outputs/rxrx1_phase1_eval/metrics_summary.csv --mode lexical --out outputs/rxrx1_phase1_report
```

## Prototype

The Streamlit prototype is optional and not required for tests:

```bash
python -m pip install -e ".[prototype]"
streamlit run prototype/app.py
```

## Scientific Caution

Phase 1 establishes the working pipeline, perturbation-level aggregation, metrics, and baselines. It does not prove biological retrieval. Biological claims require real RxRx data, real embeddings, batch-aware splits, and later VLM/alignment baselines.

## Exact Next Steps

1. Replace downloader placeholder URLs with verified public RxRx1/RxRx19a metadata and embedding URLs.
2. Validate the real RxRx metadata parser against representative local metadata tables.
3. Add batch-aware split generation and leakage diagnostics.
4. Add rendered microscopy composite generation for selective image samples or thumbnails.
5. Add OpenCLIP and BiomedCLIP zero-shot baselines as optional extras, not core dependencies.
