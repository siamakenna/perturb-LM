# Phase 2 Real Baseline Status

> **Status: Historical.** This document records a completed Phase 2 local baseline snapshot. Current entry points are `README.md`, `docs/README.md`, `docs/METHODS_DRAFT.md`, and `docs/PHASE3C_TEXT_PROFILE_ALIGNMENT.md`.

This note records the first real-data Phase 2 retrieval baseline run. The run used local JUMP CPJUMP1 profile files only. It does not use raw microscopy images, VLMs, or aligned text/image models yet.

## Local Data Used

- Dataset track: JUMP CPJUMP1 pilot profiles
- Local root: `data/raw/jump_pilot/`
- Batch: `2020_11_04_CPJUMP1`
- Profile kind: `normalized_feature_select_negcon_batch`
- Metadata files found: 5 of 5 expected files
- Profile files found: 12
- Indexed profile rows: 4,524
- Numeric Cell Painting feature columns: 904
- Detected batch column: `Metadata_Inferred_Batch`
- Detected plate column: `Metadata_Plate`
- Detected well column: `Metadata_Well`
- Same-treatment label column: `Metadata_broad_sample`

Generated outputs were written under `outputs/jump_pilot_real_baseline/` and should not be committed.

## Commands Run

```bash
python scripts/audit_jump_pilot.py \
  --summary-only \
  --max-columns-to-print 20 \
  --out outputs/jump_pilot_real_baseline/inventory.json

python scripts/build_jump_profile_index.py \
  --data-root data/raw/jump_pilot \
  --out outputs/jump_pilot_real_baseline/index

python scripts/run_jump_profile_diagnostics.py \
  --data-root data/raw/jump_pilot \
  --filtered-presets \
  --out outputs/jump_pilot_real_baseline/diagnostics

python scripts/run_jump_text_profile_retrieval.py \
  --data-root data/raw/jump_pilot \
  --out outputs/jump_pilot_real_baseline/text_profile

python scripts/make_phase2_jump_report.py \
  --inventory outputs/jump_pilot_real_baseline/inventory.json \
  --index-metadata outputs/jump_pilot_real_baseline/index/index_metadata.json \
  --diagnostics-summary outputs/jump_pilot_real_baseline/diagnostics/profile_neighbor_diagnostics_summary.csv \
  --diagnostics-json outputs/jump_pilot_real_baseline/diagnostics/profile_neighbor_diagnostics_summary.json \
  --text-profile-summary outputs/jump_pilot_real_baseline/text_profile/jump_text_profile_summary.csv \
  --out outputs/jump_pilot_real_baseline/phase2_jump_report.md
```

## Batch And Leakage Behavior

All local profiles came from one inferred batch, so same-batch diagnostics are not informative yet. The diagnostic summary explicitly warns:

```text
Same-batch diagnostics are not informative because all rows come from one batch in Metadata_Inferred_Batch.
```

Unfiltered nearest-neighbor behavior shows strong plate and well structure:

| Diagnostic | Metric | Observed | Random | Shuffled label |
| --- | ---: | ---: | ---: | ---: |
| Plate | same_plate@1 | 0.6375 | 0.0834 | 0.0802 |
| Well | same_well@1 | 0.1379 | 0.0024 | 0.0022 |

Interpretation: profile nearest neighbors carry strong acquisition-layout signal. Any treatment retrieval score must be read with filtered diagnostics, not only unfiltered results.

## Same-Treatment Retrieval

Same-treatment means matching the `Metadata_broad_sample` label. `value_evaluable_queries` is the preferred number when not all rows have same-treatment positive candidates after filtering.

| Filter | K | Observed, all queries | Observed, evaluable queries | Random, evaluable queries | Shuffled, evaluable queries | Evaluable queries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unfiltered | 1 | 0.1512 | 0.1632 | 0.0014 | 0.0010 | 4,190 |
| Unfiltered | 5 | 0.2564 | 0.2769 | 0.0071 | 0.0060 | 4,190 |
| Unfiltered | 10 | 0.3265 | 0.3525 | 0.0141 | 0.0119 | 4,190 |
| Exclude same plate | 1 | 0.2098 | 0.2265 | 0.0015 | 0.0019 | 4,190 |
| Exclude same plate | 5 | 0.3420 | 0.3692 | 0.0075 | 0.0060 | 4,190 |
| Exclude same plate | 10 | 0.4211 | 0.4547 | 0.0149 | 0.0112 | 4,190 |
| Exclude same well | 1 | 0.0254 | 0.1509 | 0.0015 | 0.0026 | 762 |
| Exclude same well | 5 | 0.0292 | 0.1732 | 0.0073 | 0.0131 | 762 |
| Exclude same well | 10 | 0.0323 | 0.1916 | 0.0146 | 0.0210 | 762 |
| Exclude same plate and well | 1 | 0.0212 | 0.1260 | 0.0014 | 0.0026 | 762 |
| Exclude same plate and well | 5 | 0.0245 | 0.1457 | 0.0068 | 0.0079 | 762 |
| Exclude same plate and well | 10 | 0.0272 | 0.1614 | 0.0135 | 0.0184 | 762 |

## Current Interpretation

This is a validated real-data morphology-profile retrieval baseline. It shows same-treatment retrieval above random and shuffled-label controls, including after excluding same-plate and same-well neighbors.

The strongest leakage-aware read is the `exclude_same_plate_and_well` result. It remains above controls, but only 762 of 4,524 rows are evaluable after that filter. Report both the score and the evaluable-query count.

This does not prove biological natural-language retrieval. It validates that real JUMP profile data can flow through the repo, be indexed, and be evaluated with batch/plate/well/treatment diagnostics.

## Text-To-Profile Metadata Baseline

The added text-to-profile baseline generates metadata-derived text queries and retrieves profile rows with a TF-IDF lexical baseline over profile metadata text. This moves the input side closer to the project goal, but it is still a metadata control rather than biological image understanding.

In the current local run, it produced 641 evaluable queries. The full metadata TF-IDF baseline had mean hit@1 of 0.9906 and mean average precision of 0.9952, while random and shuffled-label controls were near zero at hit@1.

Because full metadata TF-IDF includes direct perturbation identifiers, the run now also reports an identifier-stripped TF-IDF control. That tougher control removes direct perturbation IDs/names from candidate text and uses mechanism-style query text when possible. It had mean hit@1 of 0.2496 and mean average precision of 0.3991, still above random/shuffled controls but far below direct metadata lookup. This is a more honest rung toward biological retrieval.

Positive profiles crossed plates for all 641 queries, but crossed batches for none because the local data still contains one inferred batch.

## Next Phase 2 Tasks

1. Repeat the run with additional CPJUMP1 batches or more diverse JUMP profile data so same-batch diagnostics become meaningful.
2. Regenerate the automatic Phase 2 JUMP report after each real-data baseline run.
3. Stress-test text-to-profile retrieval across additional batches and with stronger non-metadata baselines.
4. Add selected raw/composite image support only after profile diagnostics are stable.
5. Keep OpenCLIP, BiomedCLIP, DINO, and alignment models behind optional dependencies until the profile baseline and leakage checks are reproducible.
