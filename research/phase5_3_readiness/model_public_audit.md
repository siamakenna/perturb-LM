# ChAda-ViT: bounded public-source audit

Prepared 27 October 2026. Status: **PARTIAL_PUBLIC_SOURCE_AUDIT_PINS_NOT_ESTABLISHED**.
This is a source review, not an integrated or evaluated Perturb-LM model.

## What was learned

- The [author configuration](https://huggingface.co/nicoboou/chadavit16-moyen/blob/main/config.json)
  declares up to ten channels, 224-pixel inputs, 16-pixel patches and 192-dimensional
  token embeddings.
- **Output pooling needs an explicit decision.** The retrieved configuration sets
  `return_all_tokens=true`. The [forward implementation](https://huggingface.co/nicoboou/chadavit16-moyen/blob/main/modeling_chada_vit.py)
  then returns non-masked patch tokens. A fixed vector for each image requires
  CLS-token output or a separately specified pooling rule.
- The author wrapper expects `forward(x, index, list_num_channels)` and groups a
  flattened single-channel batch. Its `in_chans=1` setting describes the patchifier,
  not a limit of one channel for the complete model. A tested input-group adapter
  is required before passing five-channel image data.
- The [author development environment](https://raw.githubusercontent.com/nicoboou/chadavit/main/pyproject.toml)
  declares NumPy 1.24.3 and Torch 2.0.0. Assess a separate model runtime; do not
  install the old stack into the repaired Perturb-LM NumPy 2 environment.
- Transformers auto classes point to custom repository code. Inspect and pin
  that source before loading; this review executed none of it.

## Training, identity and independence

The [primary paper](https://arxiv.org/html/2311.15264v2) reports DINO self-supervised
training on IDRCell100k, a collection of 79 experiments with one to ten channels.
It is not specifically a DINOv2 extension. Training-study overlap with the intended
JUMP evaluation cohort remains unresolved. Self-supervised training does not prove
an independent evaluation.

## Pinning is still incomplete

The [retrieved checkpoint tree](https://huggingface.co/nicoboou/chadavit16-moyen/tree/main)
exposed commit candidate `91a41123650ccff12f590364fec95d76af36cc93`. The available
reader could not retrieve the immutable commit/configuration or live API. That
candidate is **not** certified as the current head or as the revision of the
inspected mutable-main files. No author GitHub source SHA or byte-level source
hash was established. The JSON audit preserves these gaps explicitly.

The code repository declares Apache 2.0. The checkpoint-weight license still needs
separate verification. Exact intensity normalization, channel semantics, cropping,
registration, missing-channel behavior and well aggregation remain unbound.

## Smallest next actions

1. Capture immutable source and checkpoint metadata on the receiving Mac.
2. Bind the exact configuration and custom code to those revisions and hash them.
3. Freeze grouping, channel mapping and image-output pooling contracts.
4. Test those contracts using invented inputs in an isolated proposed runtime.
5. Proceed to real images only after cohort availability and preprocessing checks.

No weights were downloaded; no model, inference, scientific scoring, GitHub write
or Biowulf job ran during this audit. Evidence references and retrieval limits are
recorded in `model_public_audit.json`.
