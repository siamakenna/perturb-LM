# Phase 2 Real Data And Model Design

Phase 2 turns the Phase 1 parser/retrieval scaffold into a real-image benchmark path. The goal is still careful retrieval validation, not a claim that the system has solved biological search.

This PR covers Adam's Phase 2 JUMP profile-infrastructure and diagnostics slice. It does not try to finish the full VLM, raw-image, or text-query/RAG project.

## Scope

Use real local metadata and local embeddings/profiles first, then selected local microscopy channel images later. Do not download full raw image archives by default. Full archive downloads remain opt-in only.

The immediate benchmark ladder is:

1. JUMP CPJUMP1 profile inventory and profile-based retrieval.
2. Metadata lexical retrieval from Phase 1 where matching local metadata exists.
3. Image/profile nearest-neighbor retrieval using local morphology embeddings or profiles.
4. Zero-shot VLM baselines on rendered RGB microscopy composites.
5. Lightweight alignment from biomedical text embeddings to microscopy/profile embeddings.

Formal scoring remains perturbation-level after image/site aggregation.

## Local Asset Flow

The active real Cell Painting profile track is JUMP CPJUMP1 under `data/raw/jump_pilot/`.

```bash
python scripts/run_phase2_jump_smoke.py
python scripts/audit_jump_pilot.py
python scripts/build_jump_profile_index.py
python scripts/run_jump_profile_diagnostics.py
python scripts/run_jump_profile_diagnostics.py --filtered-presets
python scripts/make_phase2_jump_report.py --out outputs/jump_pilot_phase2_report.md
python scripts/run_jump_text_profile_retrieval.py --out outputs/jump_text_profile
```

The smoke command writes tiny synthetic JUMP-like files and outputs under `outputs/phase2_jump_smoke/`. It is software validation only, not a biological result. The audit writes `outputs/jump_pilot_inventory.json` and reports expected metadata files, profile files, row and column counts, Metadata columns, numeric feature columns, likely batch/plate/well columns, likely perturbation columns, and warnings. The profile index writes `outputs/jump_pilot_index/index_metadata.json`. Generated smoke, inventory, index, and diagnostic outputs are local only and should not be committed.

The report command rebuilds a Markdown Phase 2 summary from the inventory, index metadata, and diagnostics summary. It is the preferred way to record baseline behavior because the tables are generated from local artifacts rather than copied by hand.

The text-to-profile retrieval command creates metadata-derived text queries, retrieves profile rows using TF-IDF lexical baselines over profile metadata text, and compares the result to random and shuffled-label controls. It reports both a full metadata lookup baseline and an identifier-stripped baseline that removes direct perturbation IDs/names from candidate text. This is closer to the project goal because the input is text, but it is still a metadata baseline rather than evidence of biological image understanding.

For concise real-data inventory output, use:

```bash
python scripts/audit_jump_pilot.py --summary-only --max-columns-to-print 20
```

Small CPJUMP1 profile runs validate the software path but are not enough for biological claims. Same-batch diagnostics become meaningful only after more than one batch is available. When only some queries have same-treatment replicates, prefer `value_evaluable_queries` for replicate-sensitive interpretation and keep `value_all_queries` as the conservative all-query metric.

Unfiltered same-treatment retrieval can be inflated by plate, well-position, or batch structure. Filtered diagnostics remove neighbors that share obvious leakage labels with the query before scoring same-treatment hits. Interpret same-treatment retrieval most carefully after excluding both same-plate and same-well neighbors. Text-to-profile baselines should also report whether positive profiles span multiple plates or batches. Future model baselines should beat the identifier-stripped metadata control, not merely random. These are still local profile diagnostics and metadata baselines, not final biological claims.

The next recommended real-data step is to add more CPJUMP1 batches or otherwise broaden the local profile data so batch-level diagnostics become meaningful before scaling to heavier model baselines.

For RxRx local assets, place real files under `data/raw/` as described in `docs/REAL_RXRX_SETUP.md`.

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

Create a readiness report before Phase 3:

```bash
python scripts/make_rxrx_readiness_report.py \
  --dataset rxrx19a \
  --data-root data/raw \
  --site-manifest data/processed/rxrx19a_site_manifest.parquet \
  --manifest-build-report data/processed/rxrx19a_manifest_build_report.json \
  --leakage-summary outputs/rxrx19a_leakage/leakage_summary.csv \
  --out outputs/rxrx19a_readiness_report.md
```

This report records which real RxRx assets and baseline artifacts are present. Missing optional artifacts are expected until local embeddings or images are available.

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

- Load local CPJUMP1 profile features before raw images.
- Detect Metadata columns separately from numeric Cell Painting feature columns.
- Track profile IDs plus likely batch, plate, well, and perturbation/treatment columns.
- Build the sklearn cosine index with `scripts/build_jump_profile_index.py`.
- Evaluate nearest-neighbor behavior with same-batch, same-plate, same-well, and same-perturbation/treatment diagnostics.
- Compare unfiltered diagnostics with `--filtered-presets` to test whether same-treatment retrieval survives same-plate and same-well exclusions.
- Treat one-plate same-plate scores as software validation only.

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
- Same-batch, same-plate, same-well, and same-perturbation diagnostics.
- Filtered same-treatment diagnostics that exclude same-plate and same-well neighbors.
- Leakage diagnostics for query positives across batches, plates, and splits.
- Held-out perturbation evaluation when labels allow.

## Scientific Guardrail

Phase 2 can say that real images, metadata, and embeddings are being used in a retrieval benchmark. It should not claim biological retrieval unless aligned or VLM retrieval beats appropriate baselines under batch-aware and perturbation-aware splits.
