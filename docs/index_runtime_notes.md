# Index Runtime Notes

The first real Phase 2 baseline is profile-based cosine retrieval over local JUMP CPJUMP1 morphology profiles. This comes before raw image, composite, or DINOv3 experiments.

Build the local profile index with:

```bash
python scripts/build_jump_profile_index.py
```

By default this reads profile-like CSV/TSV files under `data/raw/jump_pilot/` and writes:

```text
outputs/jump_pilot_index/index_metadata.json
outputs/jump_pilot_index/embeddings.npy
outputs/jump_pilot_index/id_mapping.csv
outputs/jump_pilot_index/profile_metadata.csv
outputs/jump_pilot_index/sklearn_nearest_neighbors.pkl
```

Generated outputs are local-only artifacts and should not be committed.

Run leakage-aware profile diagnostics with:

```bash
python scripts/run_jump_profile_diagnostics.py
```

The diagnostics report same-batch@K, same-plate@K, same-well@K, and same-perturbation/treatment@K when the corresponding columns exist. Random and shuffled-label controls are included as guardrails.

These diagnostics are not proof of biological retrieval. Strong biological claims should wait until retrieval beats controls under leakage-aware evaluation, especially when same-batch, same-plate, or same-well structure could explain nearest-neighbor hits.
