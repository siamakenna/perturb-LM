# Phase 5 blinded manual image/ROI review protocol

Draft, 2026-10-14; related [#30](https://github.com/siamakenna/perturb-LM/issues/30) and [#55](https://github.com/siamakenna/perturb-LM/issues/55). No images, example ROIs, review labels or biological conclusions were generated. This protocol needs human approval and exact image-level mappings before sampling.

## Sampling and blinding

Freeze the reviewed cohort, query/gallery outputs, model versions, filters, QC policy and sampling seed before opening images. Use the intersection of evaluable queries for model comparisons and retain a separate exclusion ledger. Select, for example, 20 pairs per prespecified stratum: exact-treatment different-position positives, unrelated-treatment null pairs matched for cell/modality/conditions, curated target-related pairs, and model-disagreement pairs. This 80-pair target is a proposal; with fewer independent eligible pairs, use all eligible pairs and report the shortfall instead of importing unrelated images. Limit reuse of each treatment and report shared images. Avoid selecting only visually convincing or high-scoring examples.

An independent custodian creates opaque pair/image IDs, randomizes left/right order and presentation order, and keeps treatment, gene, model, rank, score, stratum and plate/well lookup in a separate private key. Reviewers see only blinded images, a neutral scale bar and display-setting ID. Model disagreement strata should not be recognizable from file names or UI labels. The custodian must not annotate morphology on behalf of reviewers.

## Image and ROI eligibility

Require a verified link from profile row to physical plate, well, site, channel, acquisition and original image checksum. Profile metadata alone cannot identify an exact image or ROI. Record pixel size, channel identity, segmentation version if used, and crop coordinates relative to the original field. Use a deterministic site/crop sampling rule, not handpicked cells. If the mapping is absent, set `mapping_status=missing` and do not create the review cohort. Historical CellCLIP documentation is not a substitute for a current image manifest.

Use identical channel order, channel colors, pixel scale, crop size and per-channel intensity transformation for both members of a pair. Freeze scaling from an independent calibration/reference set; no per-image contrast adjustment to favor apparent similarity. Display individual grayscale channels as well as a fixed composite. Preserve raw bit depth and clipping specifications in the private display manifest. Never use an RGB display image as an undeclared model feature input.

## Human labels

Review QC before similarity. Per image, label `pass`, `borderline`, `fail` or `unassessable`, with prespecified reasons: focus, saturation, illumination, registration, debris, cell scarcity, segmentation failure or other. Record cell-density differences without automatically excluding biologically meaningful toxicity; the exclusion rule is approved in advance.

For each assessable pair, rate morphological similarity on a four-point ordinal scale: 0 clearly dissimilar; 1 weak/local resemblance; 2 moderate similarity across multiple observable attributes; 3 strong similarity. `uncertain` is a separate state, not forced into the middle. Record attribute checkboxes (cell/nuclear shape, texture, intensity/localization, organelle organization, cell number) and confidence (low/medium/high). These are human visual judgments, not inferred mechanisms.

A separate biological curator, initially blind to visual ratings and model scores, records annotation source/version, target relationships, perturbation modality, expected direction and ambiguity. Shared targets are not automatically visual positives. Keep multiple targets and knockdown/overexpression differences explicit. Neither an AI-generated label nor a model score is independent validation.

## Uncertainty, agreement and unblinding

Treat failed/unassessable QC as missing similarity data; report counts by prespecified stratum after unblinding. Do not replace uncertain pairs selectively. If a second reviewer participates, have both independently review the same blinded set and keep original ratings. Report QC percent agreement and Cohen's kappa; weighted kappa for ordinal similarity, alongside the confusion table and uncertain/missing counts. Confidence ratings do not become accuracy weights post hoc. Cluster uncertainty by treatment or shared image rather than treating repeated pairs as independent.

Lock and timestamp original ratings before releasing the key. Compare model strata only after the lock; any adjudication follows independent ratings and is recorded separately, without overwriting them. Unblinding can reveal confounders but cannot justify retroactive relabeling to match a model. Publish only approved aggregate results; private images, logs and location keys stay outside Git.

## Empty private review-sheet schema

The following header is a schema, not a fabricated review row. Create it only in ignored `outputs/phase5/private_roi/` or approved private storage. Blank ratings remain blank.

```csv
review_version,pair_id,reviewer_id,display_settings_id,left_image_id,right_image_id,left_qc,right_qc,left_qc_reason,right_qc_reason,similarity_status,similarity_ordinal,shape_similarity,nuclear_similarity,texture_similarity,localization_similarity,organelle_similarity,cell_number_similarity,confidence,blinded_notes,rating_timestamp,locked_timestamp
```

Private custodian key (separate access):

```csv
pair_id,left_record_id,right_record_id,left_image_checksum,right_image_checksum,left_site,right_site,left_roi_xywh,right_roi_xywh,channel_manifest_id,mapping_status,sampling_seed,sampling_stratum,model_id,query_rank,query_score,left_treatment,right_treatment,left_plate,right_plate,left_well,right_well,condition_stratum,unblinding_timestamp
```

Independent biology sheet (separate from visual ratings):

```csv
pair_id,curator_id,annotation_source,annotation_version,relationship_type,left_targets,right_targets,direction_expectation,multitarget_flag,annotation_ambiguity,biological_confidence,curator_notes,annotation_locked_timestamp
```

No local absolute image paths belong in a committed schema or public report. Resolve opaque image IDs through an access-controlled manifest. Named people, study-specific access decisions and biological labels are supplied by the team, not invented here.
