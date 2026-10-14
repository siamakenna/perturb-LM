# Phase 5 CPJUMP1 cohort audit

Audit date: 2026-10-14. Related issues: [#30](https://github.com/siamakenna/perturb-LM/issues/30), [#52](https://github.com/siamakenna/perturb-LM/issues/52).
Status: completed metadata audit and descriptive diagnostics; no new benchmark performance or pretrained inference. Historical results and contracts remain unchanged.

## Repository preflight

A fresh `git fetch origin main` resolved to `bbd5aab2c2803623d7e21f6eee7193042ab157dd`, also the historical SHA supplied in the request. This equality was checked, not assumed. Recent main integrations include #74 (Python 3.11 NumPy constraints), #73 (dependency updates), #72 (launch integrity), #71 (operator tools), #70 (Next), #69 (SciBERT), and #68 (external bounded manifests). GitHub disposition on the audit date: **#67 open; #68–#73 merged**. None was merged or modified by this task.

The original checkout was on `feature/benchmark-v2-scikit`, HEAD `3884195d233daebf7f7ab82def690a6c8fc66572`, with untracked `.firecrawl/`, `output/`, and `tmp/`. It and the nine pre-existing linked worktrees were preserved. A clean worktree was created from refreshed main on `science/phase5-cpjump1-audit`. The audit adds new modules, scripts, tests and these documents; it does not rebuild Phase 4.

## Evidence and reproducibility

Source revision: `56845c7d4dc322652952783d91dae0ffef47829f` of the [original repository](https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/tree/56845c7d4dc322652952783d91dae0ffef47829f). The small allowlisted download includes the experiment TSV, its creation notebook, barcode map, three plate maps, three annotation tables, expanded compound targets and README. It excludes images, weights and profile downloads. SHA-256 checksums are recorded in `outputs/phase5/source/provenance.json` and verified before local auditing.

Run from this branch using an environment with the project's core dependencies. Set `CPJUMP1_DATA_ROOT` to the existing local `jump_pilot` directory; do not put its machine-specific value in Git.

```bash
PYTHONPATH=src python scripts/audit_phase5_cpjump1.py \
  --fetch-source --data-root "$CPJUMP1_DATA_ROOT" \
  --source-root outputs/phase5/source --out outputs/phase5/cohort \
  --profile-diagnostics
PYTHONPATH=src python scripts/audit_phase5_queries.py \
  --data-root "$CPJUMP1_DATA_ROOT" --out outputs/phase5/queries
```

Omit `--data-root` for source-only reconstruction. Omit `--fetch-source` to use the checksummed local source snapshot. The CLIs require ignored output locations. `--profile-diagnostics` computes only descriptive within-condition cosine moments of existing features; it fits no model and calculates no retrieval performance.

Selection is explicitly `profiles/2020_11_04_CPJUMP1/**/*normalized_feature_select_negcon_batch.csv.gz`. The separate 192-row timepoint file is present locally but excluded. Each file's checksum, feature schema hash, row count and **row-observed plate IDs** are recorded. Twelve files happen to contain twelve plates; the loader and tests support multiple plates within a file and do not infer one plate per filename.

Joins use `(Batch, Assay_Plate_Barcode)`, then `(Plate_Map_Name, well_position)`, then `(Perturbation, broad_sample)`. Duplicate keys are marked ambiguous without multiplying rows. Missing/contradictory keys, duplicate local plate/well records, annotation differences and batch/path disagreements are explicit. No treatment is filled from a plate map when its local label is missing.

## Confirmed source inventory versus local cohort

The [source experiment table](https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/blob/56845c7d4dc322652952783d91dae0ffef47829f/benchmark/output/experiment-metadata.tsv) contains 117 records across acquisition collections. For the specified batch, **51 assay plates: 24 compound, 18 CRISPR, 9 ORF; 31 A549 and 20 U2OS**. The barcode table agrees; there are zero inventory discrepancies or duplicate batch/plate keys. Each of the three plate maps has 384 well positions. Annotation table sizes are 307 compound, 335 CRISPR, 176 ORF records, with no duplicate modality/sample keys. These counts describe source metadata, not local data availability.

| Local assay plate | Modality | Cells | Exposure (h) | Antibiotics | Anomaly | Rows | Labeled |
| --- | --- | --- | ---: | --- | --- | ---: | ---: |
| BR00116991 | compound | A549 parental | 24 | absent | WGA | 384 | 320 |
| BR00116992 | compound | A549 parental | 24 | absent | WGA | 384 | 320 |
| BR00116993 | compound | A549 parental | 24 | absent | WGA | 383 | 319 |
| BR00116994 | compound | A549 parental | 24 | absent | WGA | 384 | 320 |
| BR00116995 | compound | U2OS parental | 24 | absent | WGA | 301 | 251 |
| BR00116996 | CRISPR | U2OS Cas9 | 144 | absent | WGA | 384 | 380 |
| BR00116997 | CRISPR | U2OS Cas9 | 144 | absent | WGA | 384 | 380 |
| BR00116998 | CRISPR | U2OS Cas9 | 144 | absent | WGA | 384 | 380 |
| BR00116999 | CRISPR | U2OS Cas9 | 144 | absent | WGA | 384 | 380 |
| BR00117000 | CRISPR | A549 Cas9 | 144 | absent | none documented | 384 | 380 |
| BR00117001 | CRISPR | A549 Cas9 | 144 | Puromycin | none documented | 384 | 380 |
| BR00117002 | CRISPR | A549 Cas9 | 144 | Puromycin | none documented | 384 | 380 |

**Local:** 4,524 rows, 4,190 nonmissing treatment labels, 334 missing labels, 641 labeled treatment IDs; 904 numeric features in each of 12 matching feature schemas. Compound rows: 1,836; CRISPR: 2,688; ORF: zero. A549: 2,687; U2OS: 1,837. WGA-flagged rows: 3,372 on nine plates; other three plates: 1,152 rows. All source records say `Density=100`, `Time_delay=Day0`, `Times_imaged=1`.

`Density=100` is **100% of modality-specific baseline seeding density**, not 100 cells/well and not a common absolute density. Source methods specify 1,000 cells/well for compounds, 350 for CRISPR, and 1,625 for ORF; treatment compounds were assayed at 5 μM. These are source-protocol facts, not measured row-level dose or density fields. Source plate format is 384 wells (A–P, 01–24). The original study describes replicate plates and multiple imaging sites per well; sites are technical subsamples, not independent biological replicates. [Original methods](https://www.nature.com/articles/s41592-024-02241-6).

## Mapping completeness, missingness and discrepancies

- All 4,524 local rows match one experiment record, one barcode/plate-map record and one well assignment. All sample assignments agree, including blanks. No ambiguous plate/well join or duplicate local plate/well exists.
- All 4,190 labeled rows match original modality-specific annotations. Gene and perturbation/control fields agree.
- The 334 missing treatment labels comprise 306 compound negative-control wells with blank broad sample IDs, plus 28 CRISPR wells without treatment annotations. Do not discard the first category from culture/QC inspection just because historical exact-treatment scoring excludes it; do not invent identities for the second.
- There are **84 absent well rows** relative to the included plate maps: one on BR00116993 and 83 on BR00116995. The exact coordinates are in the ignored missing-well report. Their absence does not establish why they are missing; no imputation is applied.
- **1,009 rows disagree on PubChem CID**, after canonicalizing equivalent numeric spellings without rounding. Their local numeric values are consistent with lost precision. This interpretation is inferred, not proven provenance. Treatment IDs, genes and plate-map assignments agree; CID discrepancies are separately flagged and do not disqualify exact sample-ID joins. Use the original source CID for future approved chemistry annotation; do not silently rewrite historical data.
- Batch is absent from profile columns and initially inferred from the selected directory. The exact plate IDs independently match the source inventory in that batch. Thus source membership is corroborated; independence between cultures, dates or laboratories is not established by a folder name.

Ignored outputs include `source_plates.csv` (all 51), `source_conditions.csv`, `source_plate_wells.csv`, `source_inventory_discrepancies.csv`, `local_plates.csv`, `controls.csv`, `cohort_summary.json`, and the profile manifest. `local_mapping_PRIVATE.csv` retains the complete row mapping; `unresolved_PRIVATE.csv` lists unresolved mappings **or annotation conflicts** (1,009 CID-conflict rows here); `missing_treatment_PRIVATE.csv` lists all 334 missing labels; `missing_wells_PRIVATE.csv` lists absent coordinates. Private suffixes are precautionary local handling, not a claim that the public source tables are restricted. No row-level file is committed.

## Replication and target overlap

All 641 labeled treatment IDs occur on multiple plates. All 4,190 labeled rows have another-plate same-treatment candidate without condition restrictions. Requiring a different plate **and a different well coordinate** leaves 762 rows from 59 IDs. Matching all recorded culture/acquisition conditions as well leaves 652 rows from 59 IDs; 496 are control rows. Only **156 rows from 13 non-control CRISPR reagent IDs** survive. No non-control compound has a different-coordinate exact-treatment replicate. These are eligibility counts, not performance or independent sample counts.

There are 507 IDs labeled `trt` (260 compound, 247 CRISPR) and 134 labeled control IDs. Four A549 compound plates, four U2OS CRISPR plates and two puromycin A549 CRISPR plates provide within-condition plate replication. The single U2OS compound plate and single untreated A549 CRISPR plate do not. Physical plate replication is resolved; independent cell preparations/culture lineage and exact biological-versus-technical replicate identifiers remain unknown.

Among 306 locally represented annotated compound IDs, 208 have multiple entries in `target_list`; 267 intersect the 130 non-control CRISPR genes. The principal `target` field intersects 130 genes, while `target_list` intersects 128: **the expanded list is not a guaranteed superset of the principal annotation**. Both mappings must be retained separately and reviewed. These annotation overlaps are candidates for Endpoint B, not a declaration of positive morphology pairs. No local compound–CRISPR pair is time-matched (24 versus 144 h), and parental versus Cas9 state also differs. No local ORF endpoint is available.

## Evidence boundaries

Confirmed local counts derive from actual profile rows, not synthetic fixtures. Exposure, cell identity, density percentage, antibiotics, delay, imaging count and anomalies come from the original experiment table. Filename/path evidence selects the cohort and initially supplies batch. Absolute dose/density are source-protocol annotations. Per-well achieved dose, infection/knockout efficacy, raw-image quality, cell passage, independent culture preparations and exact image/ROI mappings are not resolved by this audit. The original M0 results remain the scientific reference; these findings define what future comparisons can mean.


## Validation and preserved references

The final targeted run passed **150 tests, zero failures and zero skips**, including 33 new audit tests and existing query, retrieval, index, diagnostic, benchmark and public-copy tests. New coverage includes duplicate/ambiguous joins without fan-out, missing labels and fields, conflicting plate/batch/sample metadata, multiple plates within a source file, source-only fallback, numeric identifier precision, target/time overlap, controlled cosine moments, query collisions and production identifier-guard equivalence. Ruff lint and formatting checks passed for all six new Python files; the standalone public-copy consistency check and Git whitespace check passed.

The attempted full suite stopped during collection with **seven errors** because the local environment lacks `torch`, `scikit-image` and `tifffile`. No full-suite pass is claimed; collection stopped before test execution and no skipped-test result was reported. No heavyweight environment installation was undertaken for this metadata audit.

An independent local check, without importing the new audit modules, reproduced source plate/well joins, rendered-query counts and strict replication eligibility using CSV records and a separate self-join. All 12 profile-file checksums were unchanged. Six tracked historical implementation/reference files and two existing frozen baseline result CSVs matched their pre-audit reference checksums (8/8). Validation logs, the independent check and private outputs remain in ignored `outputs/phase5/`; no raw profiles, images, embeddings, credentials or local absolute paths are included in the changes.

Reproduce the targeted checks from an environment with the existing core project dependencies:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_phase5_audits.py tests/test_query_generation.py \
  tests/test_jump_pilot_audit.py tests/test_benchmark_v2.py \
  tests/test_benchmark_v2_review.py tests/test_public_copy_consistency.py \
  tests/test_jump_text_profile_retrieval.py tests/test_jump_profile_index_and_diagnostics.py
ruff check src/perturb_lm/audits scripts/audit_phase5_*.py tests/test_phase5_audits.py
ruff format --check src/perturb_lm/audits scripts/audit_phase5_*.py tests/test_phase5_audits.py
python scripts/check_public_copy_consistency.py
git diff --check
```
