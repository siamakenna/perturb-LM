# Index Runtime Notes

The first real Phase 2 baseline is profile-based cosine retrieval over local JUMP CPJUMP1 morphology profiles. This comes before raw image, composite, or DINOv3 experiments.

Before using real local profile files, run the synthetic smoke workflow:

```bash
python scripts/run_phase2_jump_smoke.py
```

This creates tiny JUMP-like metadata/profile tables under `outputs/phase2_jump_smoke/`, then runs audit, index building, and diagnostics. The smoke output is for software validation only and should not be interpreted as biological signal.

Build the local profile index with:

```bash
python scripts/build_jump_profile_index.py
```

By default this reads profile-like CSV/TSV files under `data/raw/jump_pilot/` and writes:

```text
outputs/jump_pilot_index/index_metadata.json
outputs/jump_pilot_index/artifact_manifest.json
outputs/jump_pilot_index/runtime_log.json
outputs/jump_pilot_index/embeddings.npy
outputs/jump_pilot_index/id_mapping.csv
outputs/jump_pilot_index/profile_metadata.csv
outputs/jump_pilot_index/sklearn_nearest_neighbors.pkl
```

`artifact_manifest.json` records the input profile paths, file sizes, generated
output paths, row count, numeric feature count, embedding dimension, index type,
distance metric, command metadata, warnings, and best-effort git metadata. It is
metadata only: it does not copy raw profile rows, embeddings, image data, or
row-level result tables.

`runtime_log.json` records start/end time, elapsed seconds, Python/platform
details, and best-effort memory measurements. On platforms where process memory
is unavailable, the field is left null and a warning is recorded instead of
crashing the build.

Generated outputs are local-only artifacts and should not be committed.

The deterministic save/load tests build a tiny synthetic JUMP profile index,
load the saved sklearn index and metadata back, and verify nearest-neighbor
identities, distances, feature-column order, and row metadata order. This is an
engineering reproducibility check only.

Run leakage-aware profile diagnostics with:

```bash
python scripts/run_jump_profile_diagnostics.py
python scripts/run_jump_profile_diagnostics.py --filtered-presets
python scripts/run_jump_profile_diagnostics.py --exclude-same-plate --exclude-same-well
```

The diagnostics report same-batch@K, same-plate@K, same-well@K, and same-perturbation/treatment@K when the corresponding columns exist. Random and shuffled-label controls are included as guardrails.

The summary CSV includes both `value_all_queries` and `value_evaluable_queries`. Use `value_evaluable_queries` when only some queries have same-treatment or same-well positives, and read `n_evaluable_queries` before interpreting any diagnostic. Same-plate diagnostics are not informative in a one-plate run because every nearest neighbor is necessarily from the same plate.

Unfiltered same-treatment retrieval can be inflated by plate, well-position, or batch structure. Filtered diagnostics are stronger evidence than unfiltered diagnostics because they remove neighbors that share obvious leakage labels with the query before scoring same-treatment hits. The preset run keeps the unfiltered rows and adds `exclude_same_plate`, `exclude_same_well`, and `exclude_same_plate_and_well`; `exclude_same_batch` is included when multiple batch labels are available.

Interpret same-treatment retrieval most carefully after excluding both same-plate and same-well neighbors. If too few candidates remain after a filter, the summary reports candidate counts and warnings instead of treating the filtered score as reliable.

These diagnostics are not proof of biological retrieval. Strong biological claims should wait until retrieval beats controls under leakage-aware evaluation, especially when same-batch, same-plate, or same-well structure could explain nearest-neighbor hits.

Five-profile local runs are useful PR and pipeline sanity checks, but they are still not final biological evidence. Well-filtered results are especially sensitive to how many queries remain evaluable, so report `n_evaluable_queries` beside `value_evaluable_queries`.

After a one-plate software check, the next recommended real-data step is 5 CPJUMP1 plates before attempting all profile data.
