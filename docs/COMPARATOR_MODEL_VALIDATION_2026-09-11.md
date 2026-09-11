# Comparator model validation

**Validation date:** 2026-09-11
**Perturb-LM source commit:** `551e98280793a1e1beefae282900b12bb586201a`

Two frozen text-comparator snapshots were resolved and loaded offline before integration into the Perturb-LM evaluator.

| Comparator | Frozen revision | Hidden size | Smoke-test output shape | Status |
| --- | --- | ---: | --- | --- |
| `ncbi/MedCPT-Query-Encoder` | `d83a36cc6b8e3a5c5e9d9d6ba156808c1643dcbc` | 768 | `2x5x768` last hidden state | PASS |
| `FremyCompany/BioLORD-2023` | `167aab527b238a50ca65224e6319215d2ff4fc9f` | 768 | `2x5x768` last hidden state | PASS |

This is a loading and tensor-validity check, not a Perturb-LM performance result.

## Adapter contracts

### MedCPT

The primary adapter will use the query encoder, truncate model input to 64 tokens, and take the final hidden state of the `[CLS]` token as the 768-dimensional representation. No model weights are committed to this repository.

### BioLORD-2023

The frozen snapshot contains a Sentence-Transformers Transformer plus mean-pooling module, with `max_seq_length` set to 128. Its Hugging Face Transformers usage example applies attention-mask-aware mean pooling and then L2 normalization. The Perturb-LM adapter must record this normalization decision explicitly rather than assume it from the pooling module alone.

## Benchmark invariants

MedCPT and BioLORD must receive the same identifier-stripped M0 text and enter the same:

- profile inclusion rule;
- held-out-plate split;
- same-plate/same-well exclusion;
- candidate pool and positive definition;
- train-only morphology preprocessing;
- ridge-alignment implementation;
- metrics and bootstrap implementation.

Only the frozen text encoder and its documented tokenizer/pooling policy may change.

## Status

- Frozen snapshots: complete.
- Offline model loading: complete.
- 768-dimensional hidden-state validation: complete.
- Perturb-LM encoder adapters: pending.
- Strict MedCPT and BioLORD evaluations: pending.

## Licensing note

The MedCPT model card labels the query encoder as public domain. The BioLORD-2023 model card identifies `ihtsdo-and-nlm-licences` and notes that users should ensure appropriate UMLS and SNOMED CT licensing. This repository records model identifiers and immutable revisions but does not redistribute model weights.
