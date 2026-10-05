# Benchmark V2 scientific contracts

This document separates relevance from query rendering. The machine-readable source
is [`configs/benchmark_v2/relevance_contracts.yaml`](../configs/benchmark_v2/relevance_contracts.yaml)
and the implementation is `perturb_lm.sklearn_api.RelevanceContract`.

`M0_GENE_AWARE_V1` preserves the frozen historical query rendering: gene,
perturbation type, control type, and negative-control type may be visible. Its
recommended relevance is exact treatment identity at treatment retrieval, with
profile/well scores filtered first and averaged by treatment. Non-evaluable queries
are excluded and counted.

`M0_IDENTITY_FREE_V2` uses the same exact-treatment relevance and split/filter
behavior, but excludes gene and direct identity fields from rendered text. It is a
separate condition and must not silently replace historical M0. Treatment labels
remain in the separate identity channel for scoring only.

`M1_BIOLOGICAL_CONTEXT` currently proposes exact `(gene, perturbation_type, species)`
identity. Annotation source, orthology, multi-gene perturbations, and the meaning
of context require scientific approval. `M5_LEAKAGE_CONTROL` currently retains
exact-treatment scoring while rendering constant neutral text. Its interpretation
as a null control also requires approval. Both are `proposed` and blocked for real
execution.

An exact-gene contract must define gene namespace, species, and perturbation type.
An exact-compound contract must define compound namespace, dose, and timepoint.
Cross-dataset transfer requires reviewed mapping provenance and a common namespace;
the implementation rejects missing provenance rather than guessing.

Before real execution, approve historical M0 against the now-available `ccec3b9`
lineage, decide whether V2 is primary or sensitivity analysis, approve normalization
tables and replicate/site aggregation, and choose the M1/M5 null interpretation.
