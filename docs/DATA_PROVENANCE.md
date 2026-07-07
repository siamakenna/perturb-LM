# Data Provenance

This repository is designed so code and documentation are public while real datasets and generated artifacts stay local.

## Active Local Data Track

Current active Phase 2 track:

```text
JUMP CPJUMP1 profile data
local root: data/raw/jump_pilot/
profile kind: normalized_feature_select_negcon_batch
```

The current local baseline uses profile tables and metadata, not full raw microscopy image archives.

## Source

The JUMP CPJUMP1 pilot profile scaffold targets:

```text
https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1
```

The downloader can fetch small profile subsets for smoke testing. Full raw image downloads are not part of the default workflow.

## Local-Only Paths

Do not commit:

- `data/`
- `outputs/`
- `results/`
- `models/`
- profile tables
- embeddings
- sklearn indexes
- NumPy arrays
- parquet outputs
- model weights
- raw microscopy images

## Provenance Artifacts

The local Phase 2 runner writes:

```text
outputs/jump_pilot_real_baseline/inventory.json
outputs/jump_pilot_real_baseline/baseline_manifest.json
outputs/jump_pilot_real_baseline/index/index_metadata.json
outputs/jump_pilot_real_baseline/diagnostics/profile_neighbor_diagnostics_summary.json
outputs/jump_pilot_real_baseline/text_profile/jump_text_profile_metadata.json
```

These files record:

- local data root
- number of metadata files
- number of profile files
- loaded profile paths
- indexed rows
- feature counts
- detected batch, plate, well, and treatment columns
- baseline modes
- diagnostic filters
- known limitations

They are generated local artifacts and should remain ignored by git.

## Public Site Policy

The GitHub Pages dashboard publishes only static HTML/CSS and summary values. It does not publish real metadata, profile files, embeddings, indexes, raw images, local reports, or generated outputs.

CI includes static-site tests to prevent accidental publication of local artifact names or generated output paths.

## RxRx Provenance

RxRx1 and RxRx19a local assets should be placed under `data/raw/` following `docs/REAL_RXRX_SETUP.md`. The readiness report records local files and missing optional artifacts. Real RxRx data should not be committed.

## Checksum Policy

When the project starts relying on fixed remote files for Phase 3, add checksums or file-size expectations to the relevant provenance report. Until then, local inventory files and baseline manifests are the primary provenance artifacts.
