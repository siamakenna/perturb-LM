# Phase 5.3 A549 exploratory context extension (#30, #52)

This is a separate four-plate A549 analysis selected after the completed U2OS
exploratory study. The user authorized independent exploratory development on
26 October 2026. No coauthor or biological-identity approval is asserted.

## The scientific question

Does the same source-annotated, different-recorded-guide morphology contrast
remain observable in a second recorded cell context? A549 is analyzed on its
own matched-condition plates. U2OS profiles are not rescored or pooled with it.
All native eligible A549 groups are included; none are selected using favorable
U2OS gene names or A549 feature values. The primary endpoint, spatial masks,
reference weighting, complete-pair weighting, ambiguity holds, feature values
and QC rules remain the same as the completed U2OS implementation.

This is a same-batch context extension, not an untouched independent-batch
validation. Recorded cell context and anomaly/staining fields differ between
arms, so their differences do not isolate a cell-type or WGA intervention.
Guide efficacy, stable target identity and independent culture lineage remain
unreviewed. Source-batch feature selection/preprocessing remains explicit.
Any later direct cross-context comparison must check ordered feature-schema
hashes and use shared recorded-gene/guide groups; this arm reports native A549
results and does not generate a causal cross-context comparison.

## Fixed inputs and conditions

The only selected plates are BR00117000, BR00117003, BR00117004 and BR00117005.
The pinned public experiment table records CRISPR, A549/Cas9, 144 hours,
density 100, antibiotics absent, Day0, first imaging and anomaly none. Plates
BR00117001 and BR00117002 are excluded because their antibiotic condition is
puromycin. The runner verifies source bytes and actual joined rows before
numeric conversion. Image counts are not used as profile-row or well counts.

[Source experiment table](https://raw.githubusercontent.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/56845c7d4dc322652952783d91dae0ffef47829f/benchmark/output/experiment-metadata.tsv)

The expected capture is 1,536 rows and 904 unchanged ordered features from the
four `normalized_feature_select_negcon_batch` profiles at source revision
`56845c7d4dc322652952783d91dae0ffef47829f`. Those are expected checks, not a
claim that the A549 objects or measurements have been verified here. Missing
objects, contradictory conditions or a different schema stop the run; no
substitute, imputation, revised eligibility or favorable cohort is selected.

Bounds remain 16 MiB compressed per profile and 64 MiB total, 32 MiB decompressed
per profile and 1 MiB per source metadata file. No images, private profiles,
models, bulk production datasets or Biowulf resources enter this study.
The independent U2OS validator is not modified or monkeypatched.

## Publication and local execution

`run-on-mac.py --publish --execute` discovers the current pull request containing
the completed U2OS source commit `589ad24f14eec0ac8b726f37ba89abef1a5316b2`.
It requires the expected open source head, or a merged main that preserves that
commit. Advanced or ambiguous bases stop for source review. A fresh checkout
preserves all earlier Mac work. A suitable existing numerical Python environment
is reused, including an explicitly selected `P5_PYTHON`.

The helper runs invented-data tests and public-copy checks, creates a new
`science/phase5-3-a549-*` branch, and commits only this study's 16 source/doc/test
files and its focused CI workflow. It verifies the push and draft PR before
fetching the new public profiles. Nothing is merged and no research results
are automatically published. Existing U2OS outputs stay unchanged.

The analysis freezes the contract before feature loading. Cross-guide/position
comparisons and the query-field information audit run as two concurrent local
CPU tasks. The engine, query audit and renderer are byte-identical to the
completed U2OS versions. They are complementary analyses of one A549 cohort,
not separate biological replications.

Outputs are ignored local `outputs/phase53-a549.*` directories containing
`summary.json`, `report.html`, five figures, `report.pdf`, provenance and hash
receipts. Detailed source-identity tables stay in `PRIVATE/`. Completion means
computation/report completion, not reviewed biology. Empty eligibility remains
unavailable with explicit coverage. Return only the aggregate `summary.json`
for interpretation; current GitHub CI should be assessed on the new source head.

## Reproduce from the published checkout

Use a clean committed checkout and Python 3.10–3.12 with NumPy, pandas and
Matplotlib. From the repository root:

```bash
export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
python -m unittest discover -s research/phase5_3_a549 -p 'test_*.py' -v
python research/phase5_3_a549/run_analysis.py \
  --repo "$PWD" --out "$PWD/outputs/phase53-a549-NEW" \
  --fetch-public --authorize-exploratory
```

Use a fresh ignored output directory. No model training or pretrained inference
is part of this command. Read `PROTOCOL.json` for the frozen experimental rules.
`REPLICATION_PLAN.md` specifies the parallel metadata-first external compound
holdout task and its present selected-well-data acquisition blocker.
