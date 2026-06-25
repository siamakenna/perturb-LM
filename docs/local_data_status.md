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

Run the local inventory audit with:

```bash
python scripts/audit_jump_pilot.py
```

This writes `outputs/jump_pilot_inventory.json`. The output is a local generated artifact and should not be committed.

Build the local profile index with:

```bash
python scripts/build_jump_profile_index.py
```

This writes a sklearn cosine index and `outputs/jump_pilot_index/index_metadata.json`.

Run leakage-aware nearest-neighbor diagnostics with:

```bash
python scripts/run_jump_profile_diagnostics.py
```

These diagnostics include same-batch@K, same-plate@K, same-well@K, same-perturbation/treatment@K, plus random and shuffled-label controls when the required columns exist.

## Current Priority

The first real-data baseline is profile-based cosine retrieval over CPJUMP1 morphology profiles. Raw JUMP images are not required yet.

RxRx1 remains a future/generalization track unless real RxRx1 files are added locally. RxRx1 is useful for later batch and generalization checks, but it is not the active local profile baseline unless matching files exist under `data/raw/`.

DINOv3 is a later optional image/composite baseline after local image or composite handling exists. RAG is later query and explanation support, not the first priority for this Phase 2 data path. Strong biological claims should wait until profile retrieval beats controls under leakage-aware evaluation.

Do not commit downloaded data, generated outputs, profiles, embeddings, raw images, model files, parquet files, NumPy arrays, or `.env` files.
