# Phase 2 Real Data And Model Design

Phase 2 turns the Phase 1 parser/retrieval scaffold into a real-image benchmark path. The goal is still careful retrieval validation, not a claim that the system has solved biological search.

## Scope

Use real local metadata, optional local embeddings/profiles, and selected local microscopy channel images. Do not download full raw image archives by default. Full archive downloads remain opt-in only.

The immediate benchmark ladder is:

1. Metadata lexical retrieval from Phase 1.
2. Image/profile nearest-neighbor retrieval using local morphology embeddings or profiles.
3. Zero-shot VLM baselines on rendered RGB microscopy composites.
4. Lightweight alignment from biomedical text embeddings to microscopy/profile embeddings.

Formal scoring remains perturbation-level after image/site aggregation.

## Local Asset Flow

Place real assets under `data/raw/` as described in `docs/REAL_RXRX_SETUP.md`.

Then run:

```bash
python scripts/audit_real_data.py --dataset rxrx1 --data-root data/raw --out outputs/rxrx1_inventory.json
python scripts/audit_real_data.py --dataset rxrx19a --data-root data/raw --out outputs/rxrx19a_inventory.json
```

After manifests exist, include path checks:

```bash
python scripts/audit_real_data.py --dataset rxrx1 --data-root data/raw --site-manifest data/processed/rxrx1_site_manifest.parquet --out outputs/rxrx1_inventory.json
```

The audit reports local metadata files, likely embedding/profile files, image file counts, and whether manifest channel paths resolve locally.

## Rendering Real Images

Build manifests first:

```bash
python scripts/build_rxrx_manifests.py --dataset rxrx1 --data-root data/raw --out data/processed
```

Render a small composite set:

```bash
python scripts/render_composites.py --site-manifest data/processed/rxrx1_site_manifest.parquet --raw-root data/raw --out outputs/rxrx1_composites --limit 200 --size 224x224
```

The renderer creates false-color PNG composites from existing `image_path_ch1` through `image_path_ch6` paths and writes `composite_manifest.csv`. Missing image rows are reported instead of silently passing.

## Model Inputs

Each model stage should consume one of these stable artifacts:

- Site manifest: `data/processed/{dataset}_site_manifest.parquet`
- Perturbation manifest: `data/processed/{dataset}_perturbation_manifest.parquet`
- Query table: `data/processed/{dataset}_queries.csv`
- Composite manifest: `outputs/{dataset}_composites/composite_manifest.csv`
- Embedding index: `outputs/{dataset}_index/`

Do not commit these generated artifacts.

## Baseline Ladder

Image/profile baseline:

- Load local embeddings or profile features.
- Align rows to `site_id` or another declared ID column.
- Build the sklearn cosine index with `scripts/build_index.py`.
- Evaluate nearest-neighbor behavior with batch and perturbation diagnostics.

Zero-shot VLM baseline:

- Render composites from a small local image subset.
- Encode composites with OpenCLIP and BiomedCLIP in optional scripts later.
- Encode query text with the matching text encoder.
- Treat this as a baseline, not an expected win.

Lightweight alignment:

- Freeze image/profile embeddings.
- Encode metadata-derived biological text.
- Train a small projection from text embeddings into image/profile embedding space.
- Evaluate held-out wells/images, held-out batches/plates, and held-out perturbations separately.

## Required Negative Controls

- Random retrieval.
- Shuffled-label retrieval.
- Same-batch and same-plate diagnostics.
- Leakage diagnostics for query positives across batches, plates, and splits.
- Held-out perturbation evaluation when labels allow.

## Scientific Guardrail

Phase 2 can say that real images, metadata, and embeddings are being used in a retrieval benchmark. It should not claim biological retrieval unless aligned or VLM retrieval beats appropriate baselines under batch-aware and perturbation-aware splits.
