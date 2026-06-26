# Local Data Status

JUMP CPJUMP1 is the current real Cell Painting profile track for Phase 2 work.

Local JUMP pilot files should live under:

```text
data/raw/jump_pilot/
```

Current expected settings:

- Batch: `2020_11_04_CPJUMP1`
- Profile kind: `normalized_feature_select_negcon_batch`
- Source: `https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1`

Run the synthetic software smoke workflow first:

```bash
python scripts/run_phase2_jump_smoke.py
```

This writes tiny synthetic JUMP-like files and local outputs under `outputs/phase2_jump_smoke/`. It validates the audit, index, and diagnostics code paths without downloading real JUMP data. It is for software validation only, not biological results.

Run the local inventory audit with:

```bash
python scripts/audit_jump_pilot.py
python scripts/audit_jump_pilot.py --summary-only --max-columns-to-print 20
```

This writes `outputs/jump_pilot_inventory.json`. The `--summary-only` form is easier to read when real profile files have hundreds of feature columns. The output is a local generated artifact and should not be committed.

Build the local profile index with:

```bash
python scripts/build_jump_profile_index.py
```

This writes a sklearn cosine index and `outputs/jump_pilot_index/index_metadata.json`.

Run leakage-aware nearest-neighbor diagnostics with:

```bash
python scripts/run_jump_profile_diagnostics.py
python scripts/run_jump_profile_diagnostics.py --filtered-presets
```

These diagnostics include same-batch@K, same-plate@K, same-well@K, same-perturbation/treatment@K, plus random and shuffled-label controls when the required columns exist.

The default diagnostics include unfiltered rows. `--filtered-presets` keeps those rows and adds filtered same-treatment checks after excluding same-plate, same-well, and same-plate-and-well neighbors. Filtered same-treatment retrieval is stronger evidence than unfiltered retrieval because plate and well-position effects can inflate nearest-neighbor results.

One-plate runs validate the software path, but they are not enough for biological claims. Same-plate diagnostics are only meaningful after multiple plates are downloaded. When only some rows have same-treatment replicates, use `value_evaluable_queries` for replicate-sensitive interpretation and keep `value_all_queries` as the conservative overall view.

## Current Priority

The first real-data baseline is profile-based cosine retrieval over CPJUMP1 morphology profiles. Raw JUMP images are not required yet.

The next recommended real-data step is a 5-plate CPJUMP1 profile run before scaling to all available profile data.

RxRx1 remains a future/generalization track unless real RxRx1 files are added locally. RxRx1 is useful for later batch and generalization checks, but it is not the active local profile baseline unless matching files exist under `data/raw/`.

DINOv3 is a later optional image/composite baseline after local image or composite handling exists. RAG is later query and explanation support, not the first priority for this Phase 2 data path. Strong biological claims should wait until profile retrieval beats controls under leakage-aware evaluation.

Do not commit downloaded data, generated outputs, profiles, embeddings, raw images, model files, parquet files, NumPy arrays, or `.env` files.
