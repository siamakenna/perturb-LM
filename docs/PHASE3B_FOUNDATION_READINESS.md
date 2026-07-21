# Phase 3B Foundation Readiness

Branch: `phase3b-foundation-hardening`

This branch hardens the project before any biomedical text-encoder experiment. It does not train a real encoder, generate production text embeddings, add FAISS, download raw microscopy images, or make biological retrieval claims.

## Scope

The current validation target is a controlled JUMP CPJUMP1 profile benchmark. The goal is to ensure local real metadata and profile embeddings can move through the repository safely, with leakage-aware controls and reproducible aggregate artifacts, before starting text-profile model development.

JUMP-CP profiles are used locally. Raw microscopy image archives are not downloaded by default and were not used for this pass.

## Identifier Guardrail

`Metadata_target_sequence` is treated as a direct or near-direct treatment identifier.

Corrected identifier-stripped query fields:

- `Metadata_gene`
- `Metadata_pert_type`
- `Metadata_control_type`
- `Metadata_negcon_control_type`

Prohibited identifier fields include:

- `Metadata_broad_sample`
- `Metadata_pert_iname`
- `Metadata_InChIKey`
- `Metadata_smiles`
- `Metadata_target_sequence`
- `Metadata_Plate`
- `Metadata_Well`
- `Metadata_Batch`
- `profile_id`
- `source_profile_file`
- `source_profile_row`

Identifier-stripped candidate text and model query text are validated against prohibited values. If a target sequence appears in supposedly identifier-stripped text, validation fails.

## Local Real-Data Checks

Original local CPJUMP1 profile subset:

| Check | Value |
| --- | ---: |
| profile files | 12 |
| profile rows | 4,524 |
| union numeric morphology features | 904 |
| intersection numeric morphology features | 904 |
| usable numeric morphology features | 904 |
| schema groups | 1 |
| features missing from at least one file | 0 |
| definition or naming conflicts | 0 |

Combined compatibility investigation with one additional public profile plate:

| Check | Value |
| --- | ---: |
| profile files | 13 |
| profile rows | 4,716 |
| union numeric morphology features | 1,377 |
| intersection numeric morphology features | 509 |
| usable numeric morphology features under `strict_intersection` | 509 |
| schema groups | 2 |
| features missing from at least one file | 868 |
| definition or naming conflicts | 0 |

Conclusion: the original 12-file benchmark remains the 904-feature modeling space. The 13-file combination is a compatibility investigation only because the shared feature intersection is smaller and the schema grouping changes. Held-out-batch evaluation remains unavailable until multiple confirmed batches pass feature harmonization, row/treatment adequacy checks, and split-specific evaluable-query thresholds.

## Query Selection

The previous ordered `query_limit=100` baseline is superseded and should not be used for scientific reporting.

Corrected full-query run:

- selection method: `all`
- total queries: 641
- evaluable queries: 641
- selection checksum: `d2a414713ca986d4984493d3fe7e8ace9fcf5c89a9a0009e38212f3648d84512`
- seeds: `0, 1, 2, 3, 4`
- top-k: `1, 5, 10`

Bounded scientific runs now default to deterministic stratified sampling rather than first sorted labels. Stratified selection records aggregate stratum counts and fails if the requested limit is smaller than the number of available strata.

## Corrected Baselines

Aggregate means across seeds:

| Mode | mAP | Hit@1 | Hit@5 | Hit@10 | Recall@1 | Recall@5 | Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| random | 0.0034 | 0.0019 | 0.0081 | 0.0144 | 0.0002 | 0.0012 | 0.0021 |
| shuffled label | 0.0018 | 0.0009 | 0.0081 | 0.0175 | 0.0001 | 0.0012 | 0.0026 |
| identifier-stripped TF-IDF | 0.2513 | 0.2512 | 0.8549 | 0.9657 | 0.0393 | 0.2099 | 0.4245 |
| full-metadata TF-IDF | 0.9952 | 0.9906 | 0.9938 | 0.9984 | 0.1660 | 0.8067 | 0.9784 |

Interpretation:

- full-metadata TF-IDF is identifier-dominated and is included only as a reference control;
- identifier-stripped TF-IDF excludes target sequences and is the baseline the first learned projection must beat;
- random and shuffled-label controls stay near zero;
- these results validate parser, feature, split, leakage, and baseline behavior, not biological natural-language retrieval.

## Query Bootstrap

Query-level 95% bootstrap intervals for deterministic point estimates:

| Mode | Metric | Estimate | 95% CI |
| --- | --- | ---: | --- |
| identifier-stripped TF-IDF | mAP | 0.2513 | 0.2445 to 0.2582 |
| identifier-stripped TF-IDF | Hit@1 | 0.2512 | 0.2200 to 0.2839 |
| identifier-stripped TF-IDF | Hit@5 | 0.8549 | 0.8268 to 0.8830 |
| identifier-stripped TF-IDF | Hit@10 | 0.9657 | 0.9516 to 0.9797 |
| identifier-stripped TF-IDF | Recall@1 | 0.0393 | 0.0338 to 0.0446 |
| identifier-stripped TF-IDF | Recall@5 | 0.2099 | 0.1991 to 0.2204 |
| identifier-stripped TF-IDF | Recall@10 | 0.4245 | 0.4113 to 0.4370 |
| full-metadata TF-IDF | mAP | 0.9952 | 0.9907 to 0.9986 |
| full-metadata TF-IDF | Hit@1 | 0.9906 | 0.9828 to 0.9969 |
| full-metadata TF-IDF | Hit@5 | 0.9938 | 0.9860 to 0.9984 |
| full-metadata TF-IDF | Hit@10 | 0.9984 | 0.9953 to 1.0000 |
| full-metadata TF-IDF | Recall@1 | 0.1660 | 0.1621 to 0.1696 |
| full-metadata TF-IDF | Recall@5 | 0.8067 | 0.7903 to 0.8228 |
| full-metadata TF-IDF | Recall@10 | 0.9784 | 0.9719 to 0.9844 |

Paired query-bootstrap differences versus identifier-stripped TF-IDF, seed 0 reference:

| Mode | Metric | Difference | 95% CI |
| --- | --- | ---: | --- |
| full-metadata TF-IDF | mAP | 0.7438 | 0.7348 to 0.7515 |
| full-metadata TF-IDF | Hit@1 | 0.7395 | 0.7051 to 0.7754 |
| full-metadata TF-IDF | Hit@5 | 0.1388 | 0.1092 to 0.1669 |
| full-metadata TF-IDF | Hit@10 | 0.0328 | 0.0202 to 0.0468 |
| full-metadata TF-IDF | Recall@1 | 0.1266 | 0.1198 to 0.1329 |
| full-metadata TF-IDF | Recall@5 | 0.5968 | 0.5818 to 0.6140 |
| full-metadata TF-IDF | Recall@10 | 0.5539 | 0.5414 to 0.5657 |
| random | mAP | -0.2481 | -0.2547 to -0.2411 |
| shuffled label | mAP | -0.2496 | -0.2563 to -0.2428 |

Paired query-bootstrap differences versus random, seed 0 reference:

| Mode | Metric | Difference | 95% CI |
| --- | --- | ---: | --- |
| identifier-stripped TF-IDF | mAP | 0.2481 | 0.2416 to 0.2548 |
| identifier-stripped TF-IDF | Hit@1 | 0.2512 | 0.2168 to 0.2824 |
| identifier-stripped TF-IDF | Hit@5 | 0.8471 | 0.8206 to 0.8736 |
| identifier-stripped TF-IDF | Hit@10 | 0.9501 | 0.9329 to 0.9657 |
| identifier-stripped TF-IDF | Recall@1 | 0.0393 | 0.0338 to 0.0448 |
| identifier-stripped TF-IDF | Recall@5 | 0.2085 | 0.1979 to 0.2187 |
| identifier-stripped TF-IDF | Recall@10 | 0.4219 | 0.4078 to 0.4340 |

Stochastic controls retain seed-level variability in the local aggregate tables. Deterministic TF-IDF modes are summarized as single point estimates plus query-bootstrap confidence intervals.

## Split Thresholds

The 641 total/evaluable query count applies to the corrected full-query lexical baseline before split-specific model evaluation. It should not be read as independently measured evidence for every held-out split or leakage filter.

Configured scientific evaluable-query thresholds and currently available local aggregate artifacts:

| Split or filter | Configured threshold | Foundation-validation status | Local aggregate artifact | Actual model-run status |
| --- | ---: | --- | --- | --- |
| held-out plate | 500 | Split summary generated; split-integrity accounting reports 699 evaluable treatment-overlap rows. | `outputs/jump_pilot_real_baseline/splits/held_out_plate/split_summary.json` | pending |
| held-out treatment | 100 | Split summary generated; treatment overlap count is 0 by design and is not a failed held-out-treatment split. | `outputs/jump_pilot_real_baseline/splits/held_out_treatment/split_summary.json` | pending |
| held-out well | 100 | Split summary generated; split-integrity accounting reports 131 evaluable treatment-overlap rows. | `outputs/jump_pilot_real_baseline/splits/held_out_well/split_summary.json` | pending |
| exclude same plate | 100 | Profile-neighbor diagnostic generated; 4,524 total and 4,190 treatment-evaluable queries after filtering. | `outputs/jump_pilot_real_baseline/diagnostics/profile_neighbor_diagnostics_summary.csv` | pending |
| exclude same well | 100 | Profile-neighbor diagnostic generated; 4,524 total and 762 treatment-evaluable queries after filtering. | `outputs/jump_pilot_real_baseline/diagnostics/profile_neighbor_diagnostics_summary.csv` | pending |
| exclude same plate and well | 100 | Profile-neighbor diagnostic generated; 4,524 total and 762 treatment-evaluable queries after filtering. | `outputs/jump_pilot_real_baseline/diagnostics/profile_neighbor_diagnostics_summary.csv` | pending |
| held-out batch | unavailable | Split summary generated; unavailable because the current local subset has one inferred batch and the multi-file compatibility investigation changes the feature schema. | `outputs/jump_pilot_real_baseline/splits/held_out_batch/split_summary.json` | unavailable |

The held-out split summaries and profile-neighbor diagnostics are foundation-validation artifacts, not completed Phase 3B model-evaluation results. Held-out treatment is expected to have no train/test treatment overlap by design. Zero train/test treatment overlap is not itself a split failure; the later model evaluation must test whether unseen-treatment text queries retrieve their held-out profiles or biologically related labels.

## Added Guardrails

- Query-text identifier leakage checks for target sequences, treatment identifiers, plate/well/batch fields, profile IDs, and local source-row/source-file fields.
- Deterministic query selection modes: `all`, `random`, and `stratified`.
- Query-level paired bootstrap summaries in addition to seed-level control variability.
- Split-specific evaluable-query thresholds with unavailable-vs-failed distinction.
- Morphology QC feature accounting for union, intersection, schema groups, missing features, and harmonization policy.
- Train-only morphology preprocessing with deterministic feature ordering, dropped-feature reasons, and save-path guards.
- Executable Phase 3B config validation.
- Stage-level runtime logging and dashboard-safe runtime summaries.

## Required Next Step

The next experiment can start only as a controlled benchmark:

Freeze a biomedical text encoder and train a small linear projection into the existing 904-feature JUMP morphology/profile embedding space. The learned projection should outperform identifier-stripped TF-IDF under held-out and leakage-aware evaluation. Beating random or shuffled-label controls alone is not enough.

Generated embeddings, model weights, indexes, row-level result tables, and local data must remain local and ignored.

Sources:

- https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods
- https://broadinstitute.github.io/jump_hub/explanations/data_description.html
