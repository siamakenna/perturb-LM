# Phase 5.3: proposed multichannel retrieval experiment

Status: **PROPOSED_NOT_APPROVED**. Prepared 27 October 2026. Related: #30, #52.

This document specifies development work. It does not approve biological
relationships, change historical results, establish an available image cohort,
or report a new experiment. Publishing source and this proposal is the immediate
deliverable; completing a scientifically interpretable study is a separate task.

## Purpose and testable question

Perturb-LM asks whether biological descriptions can retrieve relevant cellular
morphology when identity and experimental shortcuts cannot explain the result.
The next image experiment should first establish whether its representations
recover reproducible perturbation-associated morphology.

**Hypothesis:** preserving separate fluorescence channels improves retrieval of
profiles from different CRISPR guides associated with the same independently
verified gene, across plates and different well positions.

Multichannel compatibility is an engineering capability. Reproducible biological
retrieval is its proposed scientific test. Text-to-morphology retrieval is a
later, separate evaluation. None follows automatically from the preceding step.

## Evidence and data prerequisites

The completed cross-guide analyses used 904-feature numerical profiles. These
profiles do not reconstruct the raw fluorescence images needed by an image
transformer. Previously inspected development results must remain preserved.
Repeated inspection makes the existing groups development data; favorable
groups must not be selected as the confirmatory cohort.

Before any image-model execution, record a bounded inventory of selected wells:
image availability and checksums; plate, well and field identifiers; channel
identities; guide sequence and independently reconciled gene identity; cell
context; treatment and imaging conditions; and available culture/plate lineage.
Distinguish physical positions, observed profiles and available image fields.
Retain missingness and exclusions without inventing images or imputing outcomes.

If matching images or essential identities are unavailable, report the specific
blocker and continue public-metadata assessment. Do not substitute another
cohort silently or download a complete production dataset by default.

## Compatibility contract

- Preserve documented fluorescence identities, including the assay's DNA, ER,
  RNA, AGP and mitochondrial channels where verified. Brightfield is optional
  and separate; never infer its presence from a model's input dimensions.
- Record axes, channel order, units, bit depth, image resolution, channel
  registration and missing-channel behavior. Reject ambiguous channel mappings.
- Apply the same spatial crops to corresponding channels. Freeze resizing,
  intensity processing and illumination-correction provenance. Display lookup
  tables must not silently determine numerical analysis inputs.
- Fit learned preprocessing on the declared training/reference population.
  Evaluation-control calibration, if used, is a separately labeled transductive
  condition. Existing source normalization is not assumed train-only.
- Freeze field-to-well aggregation. All fields and crops from one well remain
  together during splitting; they are not independent biological replicates.
- Give each representation an explicit model/checkpoint identity and output
  contract. Equal embedding dimensions do not create image-text alignment.

## One controlled image comparison

Choose one channel-aware model after checking input compatibility, software
requirements, checkpoint training populations and licenses. Candidate designs
include ChannelViT and ChAda-ViT; the proposal does not select a checkpoint.
Supervised JUMP pretraining requires particular scrutiny for evaluation overlap.
Unknown pretraining overlap limits any claimed unseen-data generalization.

Compare full fluorescence input with a prespecified reduced-channel condition
using supported channel handling. Keep the model family, training data, image
area, preprocessing, aggregation and optimization budget as consistent as
practical. Document unavoidable differences. An unsupported inference-time
channel deletion tests distribution shift, not an organelle's causal role.
Include existing CellProfiler profiles as a reference on matched eligible wells.

Freeze query/gallery eligibility before new scoring: different guide, same
verified gene for positives; cross-plate and different row and column for the
primary spatial restriction. Report the gallery, excluded candidates, total and
evaluable query groups, and reasons for missing positives. Unknown biological
relationships are not validated negatives for a broader pathway task.

Use a separately versioned execution contract; preserve all completed cosine-
contrast diagnostics. Specify one primary ranking endpoint before execution,
proposed as gene-macro average precision. Include candidate-conditioned uniform and position-only
references. Compare methods on the same eligible population and report coverage
for every method. Plan uncertainty around gene groups and the actual
experimental blocking; overlapping plate pairs and repeated wells are not
independent experiments. Do not invent power or culture independence.

## Confirmation and eventual language evaluation

Confirm any development finding using a separately selected acquisition, layout
or source cohort with adequate identity and replication metadata. Explain which
generalization axis it actually tests. More profiles from one batch do not alone
establish independent replication.

Only then specify text retrieval: independently sourced annotations, explicit
relevance rules, query-collision accounting, held-out perturbation identities,
and lexical controls. Gene-aware, category-only and biological-description text
are distinct information conditions. CellCLIP is an existing paired image-text
baseline; replacing its image encoder requires a compatible alignment procedure.

## Immediate work and decision record

1. Preserve tested method source, synthetic tests and this proposal on GitHub.
2. In parallel, assess bounded image availability, gene/guide identity, and
   preprocessing/experimental provenance. Keep detailed local ledgers private.
3. Select one feasible cohort and model comparison; freeze the execution
   contract and endpoint before reading new results.
4. Execute a bounded image compatibility smoke only under its stated resource
   authorization, then the selected experiment. New model execution and Biowulf
   use are not authorized by publication of this proposal.

Record whether full-channel input helps, fails to help, or remains inconclusive,
with coverage and uncertainty. A completed software test does not establish the
hypothesis, biological mechanism, or improved language retrieval.

## Primary implementation references

- ChannelViT: <https://github.com/insitro/ChannelViT>
- ChAda-ViT: <https://arxiv.org/abs/2311.15264>
- CellCLIP: <https://github.com/suinleelab/CellCLIP>
- CellCLIP paper: <https://papers.nips.cc/paper_files/paper/2025/hash/b4689a8e6ac04c0919f7162365f1248d-Abstract-Conference.html>
- DINOv2 and channel-adaptive extensions: <https://github.com/facebookresearch/dinov2>

DINO-style learning and multichannel input are compatible design choices.
Published model capabilities are not evidence of performance in this proposed
experiment. Source references were inspected during design; no weights were
downloaded or image inference run to prepare this document.
