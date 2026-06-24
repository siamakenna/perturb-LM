# Evaluation

The main user-facing task is text-to-image retrieval: a user writes a natural-language query and the system retrieves microscopy image sites.

The formal evaluation unit is perturbation-level retrieval after image/site aggregation. Site-level retrieval results are aggregated to perturbation-level scores before metrics are computed, so replicate images and acquisition structure do not dominate the benchmark.

## Required Metrics

- Recall@1
- Recall@5
- Recall@10
- Hit@K
- mAP
- Enrichment over random
- same-batch@K
- same-plate@K
- same-cell-type@K

## Required Baselines

- Random retrieval
- Shuffled-query or shuffled-label retrieval
- Image/site embedding nearest neighbors
- Later: OpenCLIP
- Later: BiomedCLIP
- Later: text-to-image/profile alignment model

## Required Splits

- Held-out wells/images
- Held-out plates/batches
- Held-out perturbations when labels allow
