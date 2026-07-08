# Phase 3 Engineering Plan

This document defines the engineering work needed before Phase 3 model development. The goal is to make the real-data retrieval benchmark more reliable, inspectable, and scalable before any stronger biological claim is made.

## Current Project State

The repository already has:

- configuration and path handling
- dataset documentation
- RxRx metadata downloader scaffold
- RxRx manifest builders
- query generation
- site/image retrieval result aggregation
- perturbation-level scoring
- random and shuffled controls
- JUMP CPJUMP1 profile audit/index/diagnostics
- text-to-profile metadata baselines
- leakage-aware diagnostics
- JUMP profile index artifact manifests and runtime logs
- deterministic JUMP profile index save/load validation on tiny fixtures
- reproducibility/readiness checks
- synthetic tests and CI smoke runs
- a public GitHub Pages dashboard

The strongest current claim is that the repository can run parser, baseline, split, leakage, and reproducibility checks on tiny fixtures and local real-data files when available.

The current scope is reproducibility, baseline, leakage, and readiness validation. Biological retrieval requires future leakage-aware model comparisons.

## Engineering Mission

Build and validate the Phase 3 retrieval benchmark infrastructure:

- scalable embedding indexing
- reproducible artifact manifests
- held-out batch, plate, well, and perturbation evaluation
- leakage diagnostics
- optional local image visualization
- safe handling of real local RxRx/JUMP files without committing data

The engineering work should make the benchmark trustworthy before model-alignment work begins.

## Data Safety Rules

Never commit:

- raw microscopy images
- downloaded metadata
- downloaded JUMP profiles
- embeddings
- generated indexes
- model weights
- parquet outputs
- NumPy arrays
- local reports under `outputs/`
- any file under `data/`, `outputs/`, `models/`, or local asset folders unless it is a tiny committed fixture already tracked by git

Safe to commit:

- source code
- docs
- tests
- tiny synthetic fixtures
- static site files
- GitHub Actions workflows

Before every commit, run:

```bash
git status --short
```

If any large data or generated result appears as tracked or staged, stop and fix `.gitignore` before committing.

## Golden Local Commands

Run the synthetic checks first:

```bash
pytest
python scripts/run_phase1_smoke.py --out outputs/phase1_smoke
python scripts/run_phase2_jump_smoke.py --out outputs/phase2_jump_smoke
```

Run the one-command JUMP real-data report when local CPJUMP1 profiles are present:

```bash
python scripts/run_phase2_local_report.py \
  --data-root data/raw/jump_pilot \
  --out outputs/jump_pilot_real_baseline

python scripts/check_phase2_readiness.py \
  --root outputs/jump_pilot_real_baseline \
  --out outputs/jump_pilot_real_baseline/readiness_check.json
```

Run the RxRx path when local RxRx metadata and embeddings are present:

```bash
python scripts/audit_real_data.py --data-root data/raw --out outputs/real_data_inventory.json

python scripts/build_rxrx_manifests.py \
  --dataset rxrx19a \
  --data-root data/raw \
  --out data/processed

python scripts/build_queries.py \
  --dataset rxrx19a \
  --manifest data/processed/rxrx19a_perturbation_manifest.parquet \
  --out data/processed

python scripts/run_leakage_diagnostics.py \
  --dataset rxrx19a \
  --queries data/processed/rxrx19a_queries.csv \
  --site-manifest data/processed/rxrx19a_site_manifest.parquet \
  --out outputs/rxrx19a_leakage
```

Raw image use must stay opt-in and local. Do not download full image archives by default.

## Phase 3 Engineering Work Packages

### 1. Index Reliability

Owner focus:

- deterministic index builds
- save/load validation
- row count and embedding dimension checks
- query-time top-k correctness
- memory and runtime logging
- clear index metadata files

Acceptance criteria:

- index build records input file, row counts, dimensions, generated files, and timestamp
- reload test confirms the same nearest neighbors for a small deterministic fixture
- missing or mismatched embeddings fail with an actionable error
- generated `artifact_manifest.json` and `runtime_log.json` stay local and ignored

### 2. Split And Leakage Stress Tests

Owner focus:

- held-out plate evaluation
- held-out well evaluation
- held-out batch evaluation when more than one batch exists
- held-out perturbation evaluation when labels allow
- same-batch, same-plate, same-well, same-treatment summaries

Acceptance criteria:

- every split reports train/test row counts and perturbation counts
- every filtered result reports `n_evaluable_queries`
- one-batch or missing-label limitations are explicitly reported
- no result table is interpreted without leakage diagnostics

### 3. Artifact Manifests

Owner focus:

- machine-readable run manifests
- checksums or file sizes for major inputs
- generated artifact inventory
- reproducible command logging

Acceptance criteria:

- each run writes a compact manifest JSON
- manifest names all input files without copying data into git
- manifest lists every generated output path
- readiness checker can validate the manifest
- manifests record paths, file sizes, counts, and metadata only, not raw data

### 4. Optional Image Visualization

Owner focus:

- verify local image path resolution
- render small channel composites or thumbnails
- log missing channels
- keep image handling opt-in

Acceptance criteria:

- no raw image archive download occurs unless explicitly confirmed
- rendering works on a tiny synthetic image fixture
- real image visualization writes only ignored local outputs
- public docs describe visuals as sanity checks, not biological evidence

### 5. Baseline Dashboard Inputs

Owner focus:

- export compact JSON summaries for the public dashboard
- avoid publishing raw row-level data
- surface readiness status, leakage warnings, and key baseline metrics

Acceptance criteria:

- dashboard inputs are small summaries only
- no local data paths, row-level metadata, or image names are published
- CI verifies the static site still links to the protocol and provenance docs

## Project Roles

Scientific lead:

- query wording
- biological interpretation
- dataset prioritization
- claim discipline
- final decision on whether a result is biologically meaningful

Engineering collaborator:

- data pipeline reliability
- scalable indexing
- runtime/memory measurement
- leakage/split automation
- reproducible artifacts
- optional local visualization tools

Shared responsibility:

- no accidental data commits
- no biological claim without leakage-aware controls
- every result must be reproducible from commands

## Definition Of Ready For Model Work

Phase 3 modeling can start only when:

1. A real-data baseline has a reproducible command sequence and generated report.
2. Random and shuffled controls are present.
3. Identifier-stripped metadata controls are present.
4. Leakage diagnostics are present or explicitly unavailable with counts.
5. Held-out split behavior is reported where labels allow.
6. The scoring unit is perturbation-level retrieval after site/image aggregation.
7. All generated data and artifacts remain ignored by git.

Recommended first model target:

```text
JUMP morphology/profile embedding space first, then RxRx image/site embeddings when real local RxRx embeddings are available.
```
