# Methods Draft

This document records the current manuscript-facing methods for Perturb-LM. It describes the validated benchmark foundation and the planned model experiment. It does not report completed learned-model results.

## 1. Study Objective

Perturb-LM asks whether biological language can retrieve perturbation-induced Cell Painting morphology under leakage-aware evaluation. The current system establishes a perturbation-level text-to-morphology-profile benchmark before training or evaluating a real biomedical text-alignment model.

## 2. Dataset And Profile Inventory

The active dataset track is JUMP CPJUMP1 Cell Painting morphology profiles. The primary local benchmark contains 4,524 profiles from 12 consistent profile files. Raw microscopy image archives are not required for the current benchmark and were not downloaded for this foundation pass.

The benchmark is profile-based. Image-level retrieval is a longer-term direction that requires additional validation.

## 3. Morphology Feature QC

Profile QC audits numeric morphology columns, missing values, infinite values, variance, duplicate feature columns, duplicate profile rows, extreme values, feature schema consistency, and candidate batch/plate/well/treatment metadata availability.

The QC report separately records:

- union of numeric morphology features;
- intersection of numeric morphology features across files;
- features missing from at least one file;
- schema-group counts;
- rows and files per schema group;
- dtype and naming conflicts where detectable;
- harmonization policy.

## 4. Primary Feature Space

The primary modeling feature space is the 904-feature intersection from the original 12-file local benchmark. A 13-file compatibility investigation found 1,377 union features but only 509 shared features across schema groups. That compatibility set is not the primary modeling dataset.

The current default harmonization policy is `strict_intersection`. Silent union-plus-imputation is not used for held-out-batch benchmarking.

## 5. Query Construction

Text queries are built from aggregate perturbation labels and public-safe metadata fields. The full-query lexical baseline contains 641 evaluable queries. Query construction records the selected query count, query-selection mode, and a public-safe checksum.

The current benchmark evaluates retrieval at the perturbation level after profile-level scoring.

## 6. Identifier-Removal Policy

Direct treatment identifiers are allowed only in the intentionally identifier-dominated full-metadata lexical reference. They are prohibited from identifier-stripped query and candidate text.

`Metadata_target_sequence` is treated as a direct or near-direct treatment identifier and is prohibited.

Identifier-stripped fields are limited to:

- gene;
- perturbation type;
- control type;
- negative-control type.

The validation code fails if prohibited identifier values appear in supposedly identifier-stripped query or candidate text.

## 7. Train-Only Preprocessing

The planned modeling pipeline fits normalization and preprocessing parameters using training data only. Synthetic contract tests verify train-only fitting behavior and deterministic feature ordering. Generated fitted objects must remain local and ignored.

## 8. Query-Selection Strategy

Query selection supports three deterministic modes:

- `all`;
- `random`;
- `stratified`.

Scientific runs using bounded query subsets default to stratified selection when strata are available. Stratified selection uses aggregate categories such as perturbation type, control status, replicate-count bin, plate-coverage bin, and treatment-label availability. The full corrected baseline uses all 641 queries.

## 9. Lexical And Stochastic Controls

Current controls include:

- full-metadata TF-IDF, an identifier-dominated lexical reference;
- identifier-stripped TF-IDF, the primary lexical control;
- random retrieval;
- shuffled-label retrieval.

The identifier-stripped TF-IDF baseline has mAP 0.2513 with a query-bootstrap 95% confidence interval of 0.2445 to 0.2582. This is a lexical control, not a learned model result.

## 10. Evaluation Units And Metrics

The formal evaluation unit is perturbation-level retrieval after profile-level scoring and aggregation. Reported metrics include:

- mean average precision;
- Hit@1, Hit@5, Hit@10;
- Recall@1, Recall@5, Recall@10;
- enrichment over random;
- total query count;
- evaluable query count;
- same-plate, same-well, same-batch, and same-treatment rates where available.

Non-evaluable cases are reported explicitly rather than silently dropped.

## 11. Held-Out Split Design

Configured split and filter targets include held-out plate, held-out treatment, held-out well, exclude-same-plate retrieval, exclude-same-well retrieval, and exclude-same-plate-and-well retrieval. Split-specific learned-model results remain pending.

Held-out treatment has no train/test treatment overlap by design. Zero train/test treatment overlap is not itself a failed split; the model evaluation must test whether unseen-treatment text queries retrieve held-out profiles or biologically related labels.

Held-out batch is unavailable in the current primary benchmark because it contains one inferred batch.

## 12. Plate And Well Leakage Filters

Profile-neighbor diagnostics include same-plate, same-well, and same-plate-and-well exclusion filters. These filters evaluate how much treatment retrieval depends on obvious acquisition structure. The current readiness report distinguishes these foundation diagnostics from pending split-specific model results.

## 13. Query-Bootstrap Uncertainty

Uncertainty is estimated with query-level paired bootstrap summaries. Bootstrap samples resample query IDs with replacement and use paired samples across compared modes. Stochastic controls retain seed-level variability, while deterministic TF-IDF modes are reported as point estimates with query-bootstrap confidence intervals.

## 14. Artifact And Provenance Policy

The repository commits code, synthetic tests, configuration, and public-safe aggregate documentation. It does not commit real profiles, embeddings, model weights, indexes, raw image archives, row-level tables, local paths, or generated outputs.

Runtime and environment summaries are written as local artifacts and dashboard-safe aggregate summaries.

## 15. Current Limitations

- The real biomedical text-encoder experiment has not started.
- Learned linear-projection results are pending.
- Split-specific model results are pending.
- Held-out-batch evaluation is unavailable.
- The 13-file compatibility set is not the primary modeling dataset.
- The benchmark is currently text-to-morphology-profile retrieval, not validated text-to-image retrieval.
- No broad biological retrieval or clinical claim is supported.

## 16. Planned Model Experiment

The next experiment freezes a biomedical text encoder and trains a small regularized linear projection into the 904-feature morphology-profile space. Success requires outperforming identifier-stripped TF-IDF under held-out and leakage-aware evaluation. Beating random or shuffled-label controls alone is insufficient.
