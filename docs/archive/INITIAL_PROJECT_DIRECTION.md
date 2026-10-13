# BioMorph-Search: Actionable Project Direction

Date: 2026-06-23

## Working Thesis

High-content microscopy datasets are already searchable by metadata, engineered morphology features, and perturbation labels, but they are not naturally searchable by biological language. BioMorph-Search should test a narrow, reproducible question:

Can natural-language phenotype queries retrieve microscopy images, perturbations, or treatment classes that are biologically meaningful?

The strongest near-term version is not a full general-purpose microscopy chatbot. It is a retrieval benchmark that compares:

1. existing vision-language models,
2. biomedical/domain vision-language models,
3. microscopy-specific image embeddings,
4. lightweight alignment strategies between morphology embeddings and text.

The core contribution can be a careful benchmark plus a small prototype search index.

## Recommended First Scope

Use public Cell Painting-style data first, not optical pooled screening data first.

Best first dataset: JUMP Cell Painting pilot or a tractable subset of JUMP-CP.

Why:

- It has chemical and genetic perturbation metadata, which can be converted into text queries.
- It has Cell Painting images and precomputed profiles available through Cell Painting Gallery/JUMP Hub.
- It naturally supports evaluation by matching perturbations, mechanisms, genes, targets, compound classes, and morphology profiles.
- It connects directly to the longer-term optical pooled screening vision without making barcode decoding, spatial registration, or pooled screen preprocessing the first bottleneck.

Good secondary dataset: RxRx1 or RxRx19a.

Why:

- RxRx1 is useful for batch-effect stress testing because it was designed around cross-batch biological signal recovery.
- RxRx19a is useful for drug-treatment / rescue-style phrasing, but it is more COVID-specific and may be less clean for a general phenotype retrieval benchmark.

Defer BioImage Archive for the first sprint unless a very specific, well-annotated dataset is selected. It is strategically important for the searchable bioimage database story, but dataset heterogeneity and metadata variation could swamp the first feasibility result.

## Minimum Viable Question Set

Start with query types that can be evaluated without manual expert annotation:

1. Perturbation identity queries
   - "cells treated with [compound]"
   - "cells with [gene] knocked down"

2. Mechanism/target queries
   - "microtubule inhibitor phenotype"
   - "proteasome inhibition"
   - "mitochondrial translation disruption"

3. Metadata-derived phenotype descriptions
   - Use known pathway, target, MoA, gene family, and organelle annotations to generate text.
   - Example: "cells with disrupted mitochondrial translation and altered mitochondrial staining."

4. Example-image queries
   - "phenotypes similar to this treatment/image"
   - This gives a strong non-language baseline and helps determine whether the image representation itself is good.

Avoid making "messed up mitochondria" the first formal benchmark unless you create a small expert-labeled query set. It is exactly the right motivating example, but too ambiguous for first-pass automated scoring.

## Model Ladder

Run models in increasing order of project risk:

1. Image-only morphology baselines
   - CellProfiler / JUMP morphology profiles if available.
   - Cell Painting CNN / DeepProfiler-style embeddings.
   - DINO or DINOv2-style frozen embeddings.
   - Optional: MAE microscopy embeddings if a usable checkpoint is available.

2. Zero-shot VLM baselines
   - OpenCLIP / CLIP with rendered Cell Painting images.
   - BiomedCLIP as the biomedical figure-caption baseline.
   - BioCLIP only as a negative/edge baseline; it is stronger for organismal biology than cellular microscopy.

3. Lightweight aligned retrieval
   - Freeze image embeddings.
   - Encode generated perturbation descriptions with a biomedical text encoder.
   - Train a small projection or contrastive alignment layer using image/metadata-text pairs.
   - Evaluate held-out perturbations, held-out MoA classes, and held-out plates/batches separately.

4. Fine-tuned VLM only if early baselines show signal
   - Fine-tune an OpenCLIP/BiomedCLIP-style model on image-text pairs generated from metadata.
   - Use batch-aware splits and avoid training/test leakage through identical perturbation labels.

## Evaluation Setup

Primary evaluation should be retrieval, not classification.

Recommended metrics:

- Recall@K / Hit@K for same perturbation, same MoA, same target, or same pathway.
- Mean average precision for ranked retrieval.
- Enrichment over random in top K.
- Pairwise similarity correlation with CellProfiler/JUMP morphology similarity.
- Batch leakage checks: can the model retrieve same plate/batch rather than same biology?

Critical splits:

- Held-out wells/images: easiest but least convincing.
- Held-out plates/batches: tests technical robustness.
- Held-out perturbations within known MoA: tests whether the text link generalizes.
- Held-out MoA/pathway classes: hardest; probably aspirational for the first sprint.

Suggested retrieval tasks:

1. Text-to-image: text query retrieves images or wells.
2. Text-to-perturbation: text query retrieves aggregated perturbation profiles.
3. Image-to-image: example image retrieves same or related perturbations.
4. Text-to-profile: text embedding retrieves morphology profile via an aligned embedding space.

The most publishable result is likely at the perturbation/profile level, because single-cell and field-level images are noisy. The prototype can still show image tiles, but formal scoring should aggregate.

## Feasibility Sprint

Sprint duration: 2 to 3 weeks.

Week 1: Data and baselines

- Select one small, reproducible dataset subset.
- Build a manifest with image paths, perturbation IDs, plate/batch, compound/gene metadata, and labels.
- Create 50 to 200 template-generated text queries from metadata.
- Build embeddings for:
  - morphology profiles,
  - OpenCLIP,
  - BiomedCLIP,
  - one microscopy/self-supervised image model.
- Run retrieval and produce first Recall@K / mAP tables.

Week 2: Alignment and robustness

- Train a frozen-encoder projection model from text to image/profile embedding space.
- Add held-out batch and held-out perturbation splits.
- Add negative controls:
  - shuffled text labels,
  - batch-only retrieval analysis,
  - random embedding baseline.
- Inspect qualitative hits for 10 to 20 representative queries.

Week 3: Prototype and write-up

- Package a small searchable index with thumbnails and query text.
- Generate figures:
  - retrieval diagram,
  - benchmark table,
  - UMAP/embedding map by MoA,
  - qualitative retrieval panels,
  - failure cases.
- Decide publication route based on signal strength.

Go/no-go criteria:

- Go for PSB full paper or preprint if aligned text retrieval beats zero-shot VLM and image-only baselines on held-out perturbation or MoA retrieval without batch leakage.
- Go for symposium/abstract if the prototype is compelling but generalization is weak.
- Reframe as a negative/benchmark paper if zero-shot VLMs fail but morphology embeddings plus metadata alignment reveal clear limitations and evaluation lessons.

## Likely Claim

Conservative claim:

Natural-language search over biological microscopy becomes feasible when phenotype language is grounded through perturbation metadata and morphology-aware image embeddings; off-the-shelf VLMs alone are unlikely to be sufficient.

Stronger claim, if results support it:

Lightweight alignment of biomedical text descriptions to microscopy-specific morphology embeddings enables retrieval of mechanistically related perturbations in public Cell Painting datasets.

## Main Risks

1. Text supervision is synthetic
   - Mitigation: explicitly call it metadata-derived phenotype language, and add a small manually curated query set if time permits.

2. VLMs may fail on false-color microscopy
   - Mitigation: treat this as a benchmark finding and emphasize the need for microscopy-specific alignment.

3. Retrieval may reflect batch/site artifacts
   - Mitigation: batch-aware splits, TVN/sphering or other batch correction, and explicit batch retrieval diagnostics.

4. MoA labels may be sparse or noisy
   - Mitigation: evaluate multiple label granularities: perturbation, target, pathway, MoA, morphology-neighbor agreement.

5. Whole-image query results may look visually unconvincing
   - Mitigation: aggregate to wells/profiles for metrics; use representative thumbnails only for interpretation.

## Conference and Dissemination Route

As of 2026-06-23:

- PSB 2027 paper submission deadline: 2026-08-03. This is plausible only if the first sprint starts immediately and the paper is framed as a benchmark/prototype.
- PSB 2027 poster/abstract deadline: 2026-12-01. This is much more comfortable.
- Crick BioImage Analysis Symposium 2026: abstract deadline listed as end of August 2026.
- Global BioImaging Exchange of Experience 2026: event is 2026-10-26 to 2026-10-29; poster abstract submission is through registration, with in-person registration deadline listed as 2026-09-05.
- NeurIPS 2026 main paper deadline has passed. NeurIPS workshop contributions are the realistic path; suggested workshop contribution date is 2026-08-29, with final workshop accept/reject by 2026-09-29.
- bioRxiv/arXiv can be used whenever the benchmark/prototype is coherent.
- Zenodo should be used for reproducible artifacts: manifest, query set, embeddings if license permits, analysis code, and archived prototype release.

Recommended route:

1. Sprint now for PSB paper go/no-go by mid-July.
2. If strong: PSB paper by 2026-08-03 plus arXiv/bioRxiv shortly after submission.
3. If moderate: NeurIPS workshop and Crick/GBI abstracts in late August/early September.
4. If still exploratory: Crick/GBI poster + Zenodo prototype + preprint later.

## Source Notes From Shared Folder

- Moshkov et al. supports the need for diverse Cell Painting training data, batch correction, and retrieval-style evaluation using perturbation matching.
- Sivanandan et al. supports the long-term bridge to Cell Painting plus optical pooled screening and shows DINO-style embeddings recovering gene networks.
- Bigverdi et al. supports perturbation-level representation learning and evaluation against protein complexes / functional gene groupings.
- Kudo et al. supports the long-term optical pooled screening motivation, but its data/code availability makes it a poor first sprint dependency.
- Doron et al. supports DINO/ViT self-supervised microscopy embeddings as a serious baseline.
- Kraus et al. supports masked autoencoders and scaling laws for cellular morphology embeddings.
- Chen et al. suggests that contrastive alignment can be framed more flexibly than vanilla CLIP-style pair matching, relevant if metadata/text labels are noisy.
- Bajcsy et al. supports the bigger searchable bioimage database framing: FAIR image repositories, standardized metadata, and cloud-friendly formats.
- Haase et al. supports using established bioimage tooling and reproducible workflows rather than bespoke preprocessing.

