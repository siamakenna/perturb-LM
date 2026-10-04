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
| BiomedCLIP text | Microsoft / `9f341de2...` | lazy OpenCLIP | pinned, mocked only | `needs_model_prefetch` |
| BGE general retrieval | BAAI / `a5beb1e3...` | lazy Transformers | pinned, mocked only | `needs_model_prefetch` |
| DINOv2 | Facebook / `f9e44c81...` | lazy Transformers | pinned, mocked only | `needs_model_prefetch` |
| CellCLIP | suinleelab / `15f66a48...` | pinned local code boundary | explicit boundary only | `needs_scientific_approval` |
| OpenPhenom-S/16 | Recursion / `0f923336...` | pinned remote-code boundary | explicit boundary only | `needs_scientific_approval` |
| CellProfiler/RxRx embeddings | user-supplied | precomputed ingestion | schema boundary only | `needs_data` |

The catalog records dimensions, pooling, normalization, input schema, batching,
and required packages. `LocalModelEmbedder` requires a complete checksummed local
asset manifest and uses offline loading. It never resolves a model name online.
