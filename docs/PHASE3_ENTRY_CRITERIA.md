# Phase 3 Entry Criteria

Phase 3 should not start just because the code can train or project embeddings. It should start only after Phase 2 has a reproducible real-data baseline and clear leakage behavior.

## Required Before Phase 3

For at least one primary RxRx dataset, preferably RxRx19a first and RxRx1 second:

- Real local metadata is discovered by `scripts/audit_real_data.py`.
- Manifests build successfully with `scripts/build_rxrx_manifests.py`.
- The manifest build report identifies the source metadata file and column mappings.
- Queries build from the perturbation manifest.
- At least one non-random baseline runs end to end.
- Perturbation-level evaluation runs after site/image aggregation.
- Leakage diagnostics run and are reviewed.
- If image files are present, `scripts/render_composites.py` reports rendered and missing-channel rows.
- If embeddings are present, `scripts/build_index.py` reports matched and unmatched rows.
- No data, embeddings, indexes, model weights, parquet outputs, raw images, or generated outputs are tracked by git.

For the current JUMP CPJUMP1 profile track:

- Profile audit, index build, and filtered diagnostics run on real local data.
- Same-plate, same-well, and same-treatment diagnostics are compared to random and shuffled-label controls.
- One-batch limitations are documented if only one batch is available.

## Minimum Go Criteria

Move into Phase 3 only when all of the following are true:

1. A real-data baseline has a reproducible command sequence and generated report.
2. Random and shuffled-label controls are available.
3. Batch, plate, well, or split leakage is measured or explicitly marked unavailable.
4. The formal scoring unit remains perturbation-level retrieval after site/image aggregation.
5. The first Phase 3 target embedding space is chosen before model work starts.

Recommended first Phase 3 target:

```text
JUMP morphology/profile embedding space first, RxRx image/site embedding space second when real RxRx embeddings are available.
```

## No-Go Criteria

Do not start Phase 3 if:

- Real data only exists as unverified local files with no inventory report.
- The only successful runs are synthetic fixtures.
- Same-treatment or same-perturbation retrieval has not been compared to random/shuffled controls.
- Leakage diagnostics are missing.
- The proposed model would train on labels that also appear unchanged in the held-out evaluation split.

## Scientific Guardrail

Phase 3 may test whether biomedical text embeddings can be aligned to morphology/profile/image embeddings. It should not claim biological retrieval unless the aligned method beats simple baselines under leakage-aware evaluation.
