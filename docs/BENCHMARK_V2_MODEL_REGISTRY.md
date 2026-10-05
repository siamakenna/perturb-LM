# Benchmark V2 model registry status

The machine-readable catalog is `configs/benchmark_v2/model_assets.yaml` and can
be inspected with `perturb_lm.sklearn_api.asset_catalog()`. Revisions below were
recorded from public model metadata; no weights are in this repository.

| Family | Identifier/revision | Backend | Local status | Blocker |
| --- | --- | --- | --- | --- |
| BiomedBERT | Microsoft / `e1354b7a...` | lazy Transformers | pinned, mocked only | `needs_model_prefetch` |
| MedCPT | NCBI / `d83a36cc...` | lazy Transformers | pinned, mocked only | `needs_model_prefetch` |
| BioLORD-2023 | FremyCompany / `167aab52...` | lazy Transformers | pinned, mocked only | `needs_model_prefetch` |
| SapBERT | Cambridge / `090663c3...` | lazy Transformers | pinned, mocked only | `needs_model_prefetch` |
| BiomedCLIP text | Microsoft / `9f341de2...` | adapter boundary | pinned, execution disabled | `needs_backend_review` |
| BGE general retrieval | BAAI / `a5beb1e3...` | lazy Transformers | pinned, mocked only | `needs_model_prefetch` |
| DINOv2 | Facebook / `f9e44c81...` | lazy Transformers | pinned, mocked only | `needs_model_prefetch` |
| CellCLIP | suinleelab / `15f66a48...` | pinned local code boundary | execution disabled | `needs_backend_review`, `needs_scientific_approval` |
| OpenPhenom-S/16 | Recursion / `0f923336...` | pinned remote-code boundary | execution disabled | `needs_backend_review`, `needs_scientific_approval` |
| CellProfiler/RxRx embeddings | user-supplied | precomputed ingestion | schema boundary only | `needs_data` |

The catalog records dimensions, pooling, normalization, input schema, batching,
and required packages. `LocalModelEmbedder` requires a complete checksummed local
asset manifest and uses offline loading. It never resolves a model name online.

BM25 and the NumPy MLP/contrastive heads are implemented and synthetic-tested;
they do not require Torch. The registry's learned families remain reservations
for CLI planning; optional HF adapters are invoked explicitly through
`LocalModelEmbedder` and have no real inference validation in this branch.

BGE uses normalized CLS pooling as specified by its
[official model card](https://huggingface.co/BAAI/bge-base-en-v1.5#using-huggingface-transformers).
No instruction prefix is silently added. Any prefix experiment must be explicit
in the approved query contract. BiomedCLIP, CellCLIP, and OpenPhenom need verified
offline architecture/preprocessing adapters before enabling inference. An approval
boolean alone cannot enable these unimplemented backends.
