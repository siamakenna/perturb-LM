# Phase 3C Text-Profile Alignment Plan

Phase 3C asks whether frozen biomedical language representations can retrieve perturbation-induced Cell Painting morphology better than identifier-stripped TF-IDF under held-out and leakage-aware evaluation.

This phase does not fine-tune a biomedical encoder, download raw microscopy image archives, add FAISS, or connect the public prototype to real model outputs.

## Primary Question

Can a frozen biomedical language representation retrieve perturbation-induced cellular morphology better than an identifier-stripped TF-IDF control under held-out and leakage-aware evaluation?

## Working Hypothesis

Frozen biomedical language representations contain enough mechanistic information to support retrieval of perturbation-induced morphology after lightweight alignment, but success must be demonstrated against identifier-stripped lexical controls under held-out and leakage-aware evaluation.

## Baseline To Beat

The reference baseline remains the Phase 3B identifier-stripped TF-IDF control:

- mAP: `0.2513`
- 95% query-bootstrap CI: `0.2445` to `0.2582`

Beating random or shuffled-label controls alone is not enough.

## Selected Encoder

- Model: `microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext`
- Official source: Hugging Face model card from Microsoft
- License: MIT
- Pinned revision: `e1354b7a3a09615f6aba48dfad4b7a613eef7062`
- Embedding dimension: 768
- Maximum sequence length: 512 tokens
- Pooling: attention-mask mean pooling over last hidden states
- Normalization: L2-normalize pooled embeddings by default
- Device: CPU supported; CUDA or Apple MPS may be used when available

Rationale: BiomedBERT was pretrained from scratch on PubMed abstracts and PubMedCentral full text, has a permissive license, can be pinned by revision, and is small enough for frozen local inference.

Limitation: BiomedBERT is a masked-language model rather than a retrieval-trained sentence encoder. Mean-pooled embeddings are a controlled feature-extraction baseline and must not be described as biological retrieval success without beating identifier-stripped TF-IDF under the predefined evaluation.

## Query Text Policy

Allowed fields:

- `Metadata_gene`
- `Metadata_pert_type`
- `Metadata_control_type`
- `Metadata_negcon_control_type`

Prohibited fields and values:

- `Metadata_target_sequence`
- treatment names
- sample IDs
- compound identifiers
- SMILES
- InChIKey
- plate
- well
- batch
- profile IDs
- source filenames
- source row numbers

The run must fail before encoding if prohibited values appear in model input text.

## Methods Compared

Exactly these methods are compared:

1. `random`
2. `shuffled_label`
3. `identifier_stripped_tfidf`
4. `frozen_text_embeddings_unaligned`
5. `frozen_text_embeddings_linear_projection`

The unaligned frozen-embedding method uses a fixed deterministic random projection only as a dimension-matching control. It is not a primary success claim.

The projected method uses ridge regression fit only on training profiles after train-only morphology preprocessing.

## Splits And Filters

Primary split:

- held-out plate

Secondary split:

- held-out treatment

Retrieval filters:

- exclude same plate
- exclude same well
- exclude same plate and well

Held-out batch is recorded as unavailable when the local dataset contains one inferred batch. Batch generalization must not be claimed.

## Metrics

Every split/filter must report its own aggregate counts and metrics:

- train profiles
- test profiles
- train treatments
- test treatments
- total queries
- evaluable queries
- excluded queries
- mAP
- Hit@1, Hit@5, Hit@10
- Recall@1, Recall@5, Recall@10
- same-plate, same-well, same-batch, and same-treatment rates where available
- paired difference from identifier-stripped TF-IDF
- paired query-bootstrap 95% CI

Do not reuse the global 641-query count as a split-specific result.

## Optional Install

Core tests use fake embeddings and do not download models. Real local encoder inference requires:

```bash
python -m pip install -e ".[phase3c,dev]"
```

Phase 3C model caches, text embeddings, fitted projections, indexes, and generated result tables must stay under ignored local output directories.
