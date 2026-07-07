# Phase 2 Reproducibility Checklist

Use this checklist before starting Phase 3 model work.

## Required Commands

Synthetic validation:

```bash
python -m pytest
python scripts/run_phase1_smoke.py --out outputs/phase1_smoke
python scripts/run_phase2_jump_smoke.py --out outputs/phase2_jump_smoke
```

Local real-data baseline:

```bash
python scripts/run_phase2_local_report.py \
  --data-root data/raw/jump_pilot \
  --out outputs/jump_pilot_real_baseline
```

Readiness check:

```bash
python scripts/check_phase2_readiness.py \
  --root outputs/jump_pilot_real_baseline \
  --out outputs/jump_pilot_real_baseline/readiness_check.json
```

Optional split presets for RxRx-style site manifests:

```bash
python scripts/build_split_presets.py \
  --manifest data/processed/rxrx1_site_manifest.parquet \
  --preset held_out_plate \
  --out outputs/rxrx1_splits/held_out_plate.parquet
```

## Expected Local Artifacts

Under `outputs/jump_pilot_real_baseline/`:

- `inventory.json`
- `baseline_manifest.json`
- `index/index_metadata.json`
- `diagnostics/profile_neighbor_diagnostics_summary.csv`
- `diagnostics/profile_neighbor_diagnostics_summary.json`
- `text_profile/jump_text_profile_summary.csv`
- `text_profile/jump_text_profile_metadata.json`
- `phase2_jump_report.md`
- optional `readiness_check.json`

These are generated local artifacts and should not be committed.

## Expected Real-Data Baseline Fields

The baseline manifest should report:

- dataset track
- data root
- number of metadata files
- number of profile files
- indexed profile rows
- numeric feature count
- batch, plate, well, and treatment columns
- diagnostic filters
- text-profile modes
- known limitations

## Minimum Phase 2 Pass Criteria

- Full test suite passes.
- Phase 1 smoke passes.
- Phase 2 JUMP smoke passes.
- Real local JUMP audit, index, diagnostics, text-profile baseline, and report run.
- Random and shuffled-label controls are present.
- Identifier-stripped metadata TF-IDF is present.
- Filtered same-treatment diagnostics include exclude-same-plate and exclude-same-well settings.
- The report explicitly says this is not a biological retrieval claim.

## Known No-Go Conditions

Do not start Phase 3 when:

- only synthetic fixtures have run
- local artifacts are missing
- the readiness checker fails
- there are no random or shuffled-label controls
- identifier-stripped metadata controls are absent
- generated outputs or data files are staged for git
- the only successful retrieval result is direct metadata lookup

## Git Safety

Never commit:

- `data/`
- `outputs/`
- `results/`
- profile tables
- embeddings
- generated indexes
- model weights
- parquet outputs
- raw microscopy images
