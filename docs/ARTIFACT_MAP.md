# Artifact Map

This map shows what each major script consumes and produces.

## Synthetic CI

| Script | Inputs | Outputs | Commit? |
| --- | --- | --- | --- |
| `scripts/run_phase1_smoke.py` | synthetic RxRx fixtures | `outputs/ci_phase1_smoke/` | no |
| `scripts/run_phase2_jump_smoke.py` | generated synthetic JUMP files | `outputs/ci_phase2_jump_smoke/` | no |
| `scripts/run_phase2_local_report.py` | synthetic JUMP smoke data in CI | `outputs/ci_phase2_local_report/` | no |
| `scripts/check_phase2_readiness.py` | generated report directory | readiness JSON | no |
| `scripts/build_split_presets.py` | synthetic or local manifests | split manifest plus `split_summary.json`, `split_summary.csv` | no |

CI uploads compact summaries as GitHub Actions artifacts. It does not commit outputs.

## Local JUMP Real-Data Track

| Script | Inputs | Outputs | Commit? |
| --- | --- | --- | --- |
| `scripts/audit_jump_pilot.py` | `data/raw/jump_pilot/` | `inventory.json` | no |
| `scripts/build_jump_profile_index.py` | local profile tables | index files, `index_metadata.json`, `artifact_manifest.json`, `runtime_log.json` | no |
| `scripts/run_jump_profile_diagnostics.py` | local profile tables | diagnostics CSV/JSON plus `leakage_summary.json`, `leakage_summary.csv`, `dashboard_leakage_summary.json` | no |
| `scripts/run_jump_text_profile_retrieval.py` | local profile tables | text-profile CSV/JSON | no |
| `scripts/make_phase2_jump_report.py` | generated summaries | Markdown report | no |
| `scripts/run_phase2_local_report.py` | local profile tables | all of the above plus `baseline_manifest.json` | no |
| `scripts/check_phase2_readiness.py` | generated local report directory | readiness JSON | no |

## RxRx Local-Asset Track

| Script | Inputs | Outputs | Commit? |
| --- | --- | --- | --- |
| `scripts/audit_real_data.py` | `data/raw/` | inventory JSON | no |
| `scripts/build_rxrx_manifests.py` | local metadata | processed manifests and build report | no |
| `scripts/build_queries.py` | perturbation manifest | query CSV | no |
| `scripts/run_retrieval.py` | queries and site manifest | retrieval results | no |
| `scripts/run_eval.py` | retrieval outputs | metrics | no |
| `scripts/run_leakage_diagnostics.py` | queries and manifest | leakage summaries plus `dashboard_leakage_summary.json` | no |
| `scripts/make_rxrx_readiness_report.py` | local inventory and generated summaries | readiness Markdown | no |

## Public GitHub Pages

| Path | Purpose | Data Policy |
| --- | --- | --- |
| `site/index.html` | public dashboard | summary values only |
| `site/styles.css` | page styling | no data |
| `site/404.html` | data-safety fallback page | no data |
| `site/robots.txt` | crawler policy | no data |
| `site/sitemap.xml` | public URL listing | no data |

The public site is deployed by `.github/workflows/pages.yml`.

## Repository Artifacts That Are Safe To Commit

- source code
- tests
- synthetic fixtures
- docs
- static site files
- GitHub Actions workflows

## Repository Artifacts That Are Not Safe To Commit

- downloaded profiles
- downloaded metadata
- raw images
- generated reports
- generated indexes
- generated embeddings
- model weights
- parquet outputs
- NumPy arrays
- local result directories

## Artifact Manifest Policy

JUMP profile index builds now write `artifact_manifest.json` and `runtime_log.json`
inside the index output directory. The manifest records paths, file sizes, row
counts, feature counts, index type, distance metric, command metadata, and
best-effort git metadata. It does not copy raw profile rows, embeddings, image
data, or row-level result tables into the manifest.

Generated manifests and runtime logs describe local artifacts, so they stay in
ignored output directories unless a tiny synthetic fixture explicitly requires
otherwise.

## Split And Leakage Summary Policy

Split preset builds write aggregate `split_summary.json` and `split_summary.csv`
files next to the generated split manifest. These summaries report train/test
row counts, perturbation counts, batch/plate/well counts, treatment overlap,
evaluable query counts when labels allow, and explicit warnings for missing
labels or one-batch limitations.

JUMP diagnostics write aggregate `leakage_summary.json`, `leakage_summary.csv`,
and `dashboard_leakage_summary.json` files under the diagnostics output
directory. RxRx leakage diagnostics also write `dashboard_leakage_summary.json`.
Dashboard-safe leakage summaries contain aggregate counts/rates and warnings
only; they do not expose row-level metadata, local paths, image names, embeddings,
or raw local identifiers.
