# Real RxRx Local Setup

Phase 1 validates parsers, split logic, leakage diagnostics, and retrieval plumbing. Do not use these checks to claim biological retrieval quality yet.

## What To Place Locally

Put metadata and optional embedding files under `data/raw/`. The manifest builder searches these metadata locations first:

```text
data/raw/rxrx1/rxrx1_site_metadata.csv
data/raw/rxrx1/rxrx1_metadata.csv
data/raw/rxrx1/site_metadata.csv
data/raw/rxrx1/metadata.csv
data/raw/rxrx1/metadata.tsv
data/raw/rxrx1/metadata.parquet
data/raw/rxrx19a/rxrx19a_site_metadata.csv
data/raw/rxrx19a/rxrx19a_metadata.csv
data/raw/rxrx19a/site_metadata.csv
data/raw/rxrx19a/metadata.csv
data/raw/rxrx19a/metadata.tsv
data/raw/rxrx19a/metadata.parquet
```

The builder also accepts dataset-prefixed files directly in `data/raw/`, such as:

```text
data/raw/rxrx1_site_metadata.csv
data/raw/rxrx19a_site_metadata.csv
```

Embeddings are not discovered automatically. Place them wherever is convenient under `data/raw/`, for example:

```text
data/raw/rxrx1/embeddings.csv
data/raw/rxrx1/embeddings.parquet
data/raw/rxrx1/embeddings.npy
data/raw/rxrx1/embeddings.npz
data/raw/rxrx19a/embeddings.csv
data/raw/rxrx19a/embeddings.parquet
data/raw/rxrx19a/embeddings.npy
data/raw/rxrx19a/embeddings.npz
```

CSV/parquet embeddings should include a `site_id` column plus numeric embedding columns. NPZ embeddings should include an `embeddings` array and, ideally, an `ids` or `site_id` array.

## What Not To Place In Git

Do not commit:

- `data/`
- `outputs/`
- `results/`
- embeddings, parquet outputs, NumPy arrays, model weights, indexes, or raw images

The repository `.gitignore` already excludes these paths and file types.

## Parser Validation Commands

Build manifests from local metadata without downloading raw image archives:

```bash
python scripts/build_rxrx_manifests.py --dataset rxrx1 --data-root data/raw --out data/processed
python scripts/build_rxrx_manifests.py --dataset rxrx19a --data-root data/raw --out data/processed
```

Each run writes a report like:

```text
data/processed/rxrx1_manifest_build_report.json
data/processed/rxrx19a_manifest_build_report.json
```

The report records the source metadata file, raw columns, canonical column mappings, optional source fields that were missing, and defaults applied.

## Querying With Local Metadata

Generate query templates:

```bash
python scripts/build_queries.py --dataset rxrx1 --manifest data/processed/rxrx1_perturbation_manifest.parquet --out data/processed
python scripts/build_queries.py --dataset rxrx19a --manifest data/processed/rxrx19a_perturbation_manifest.parquet --out data/processed
```

Run parser-level retrieval modes:

```bash
python scripts/run_retrieval.py --dataset rxrx1 --queries data/processed/rxrx1_queries.csv --site-manifest data/processed/rxrx1_site_manifest.parquet --mode lexical --top-k 50 --out outputs/rxrx1_phase1
python scripts/run_retrieval.py --dataset rxrx19a --queries data/processed/rxrx19a_queries.csv --site-manifest data/processed/rxrx19a_site_manifest.parquet --mode lexical --top-k 50 --out outputs/rxrx19a_phase1
```

If local embeddings are available, build an index and run embedding retrieval:

```bash
python scripts/build_index.py --dataset rxrx1 --manifest data/processed/rxrx1_site_manifest.parquet --embeddings data/raw/rxrx1/embeddings.csv --out outputs/rxrx1_index
python scripts/run_retrieval.py --dataset rxrx1 --queries data/processed/rxrx1_queries.csv --site-manifest data/processed/rxrx1_site_manifest.parquet --mode embedding --index outputs/rxrx1_index --top-k 50 --out outputs/rxrx1_embedding_phase1
```

## Leakage Diagnostics

After queries and manifests exist, run:

```bash
python scripts/run_leakage_diagnostics.py --queries data/processed/rxrx1_queries.csv --site-manifest data/processed/rxrx1_site_manifest.parquet --out outputs/rxrx1_leakage
python scripts/run_leakage_diagnostics.py --queries data/processed/rxrx19a_queries.csv --site-manifest data/processed/rxrx19a_site_manifest.parquet --out outputs/rxrx19a_leakage
```

These diagnostics check whether query-positive perturbations appear across batches, plates, or splits. They are intended to catch split leakage and replicate-structure shortcuts, not to validate biological retrieval.

## Readiness Report

After running whichever local artifacts are available, generate a Phase 2 readiness report:

```bash
python scripts/make_rxrx_readiness_report.py \
  --dataset rxrx1 \
  --data-root data/raw \
  --site-manifest data/processed/rxrx1_site_manifest.parquet \
  --manifest-build-report data/processed/rxrx1_manifest_build_report.json \
  --index-metadata outputs/rxrx1_index/index_metadata.json \
  --leakage-summary outputs/rxrx1_leakage/leakage_summary.csv \
  --composite-manifest outputs/rxrx1_composites/composite_manifest.csv \
  --out outputs/rxrx1_readiness_report.md
```

Any optional paths that do not exist are reported as missing. The report is a local generated artifact and should not be committed.
