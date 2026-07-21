# Phase 3B Foundation Readiness

Branch: `phase3b-foundation-hardening`

This branch hardens the project before any biomedical text-encoder experiment. It does not train a real encoder, generate production text embeddings, add FAISS, download raw microscopy images, or make biological retrieval claims.

## Local Real-Data Checks

Original local JUMP profile subset:

- profile files: 12
- profile rows: 4,524
- candidate morphology columns: 904
- usable numeric morphology columns: 904
- missing values: 0
- infinite values: 0
- all-missing features: 0
- zero-variance features: 0
- near-zero-variance features: 0
- duplicate feature columns: 0
- duplicate profile rows: 0
- extreme values: 0
- schema consistent across files: yes

Second-batch investigation:

- one additional public CPJUMP1 pilot profile plate was downloaded locally only;
- no raw microscopy image archive was downloaded;
- combined local profile files: 13
- combined local profile rows: 4,716
- combined candidate morphology columns: 1,377
- combined usable numeric morphology columns: 1,377
- combined schema consistent across files: no
- features present in some files but missing from others: 868
- warning: profile feature schemas differ across input files.

Conclusion: a second batch is reachable through precomputed public profiles, but the current one-plate addition changes the feature schema. Held-out-batch evaluation should not be treated as ready until feature harmonization is explicit and the second-batch subset is large enough for fair evaluation.

Public source notes:

- The CPJUMP1 public materials describe six pilot batches and separate image downloads from well-level profile CSV downloads.
- The JUMP Hub describes `cpg0000-jump-pilot` as a pilot dataset for perturbation-condition testing.

Sources:

- https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods
- https://broadinstitute.github.io/jump_hub/explanations/data_description.html

## Baseline Stability

Command shape:

```bash
python scripts/run_jump_text_profile_retrieval.py \
  --data-root data/raw/jump_pilot \
  --out outputs/phase3b_foundation_baseline_stability_query100 \
  --top-k 1 5 10 \
  --seeds 0 1 2 3 4 \
  --query-limit 100
```

The full unbounded five-seed run was interrupted because it was too slow for this validation pass. The bounded run completed with 100 total and 100 evaluable queries for every mode and seed.

Aggregate means from the bounded run:

| Mode | mAP | Hit@1 | Hit@5 | Hit@10 | Recall@1 | Recall@5 | Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| random | 0.0033 | 0.0020 | 0.0060 | 0.0200 | 0.0005 | 0.0011 | 0.0042 |
| shuffled label | 0.0014 | 0.0020 | 0.0060 | 0.0080 | 0.0004 | 0.0012 | 0.0017 |
| identifier-stripped TF-IDF | 0.4589 | 0.2800 | 0.9800 | 1.0000 | 0.0600 | 0.4310 | 0.9185 |
| full-metadata TF-IDF | 0.9856 | 0.9700 | 0.9800 | 1.0000 | 0.2050 | 0.9620 | 1.0000 |

Interpretation:

- full-metadata TF-IDF remains identifier-dominated and is not a primary success threshold;
- identifier-stripped TF-IDF is still strong and should be treated as the serious baseline to beat;
- random and shuffled-label controls remain near zero;
- these are parser, leakage, split, and baseline-readiness checks, not biological retrieval evidence.

## Added Guardrails

- Aggregate morphology QC with dashboard-safe JSON output.
- Train-only morphology preprocessing with deterministic feature ordering, dropped-feature reasons, and save-path guards.
- Executable Phase 3B config validation.
- Split-integrity checks for held-out plate, held-out treatment, held-out batch limitations, overlap detection, query-text identifier leakage, and evaluable-query thresholds.
- Five-seed baseline aggregation with mean, standard deviation, min, max, median, and bootstrap confidence intervals.
- Synthetic linear-projection contract using deterministic fake embeddings and fake profiles only.
- Stage-level runtime logging and dashboard-safe runtime summaries.
- Public-safe environment reporting and pinned core/dev constraints.

## Required Next Step

Before making biological claims, run the real model experiment only after:

- feature harmonization policy is locked for any multi-batch JUMP run;
- held-out plate and held-out treatment splits pass integrity checks;
- same-plate and same-well retrieval filters are reported;
- the learned projection beats identifier-stripped TF-IDF under leakage-aware evaluation;
- all generated embeddings, weights, indexes, and result tables stay local and ignored.
