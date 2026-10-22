# Phase 5.2 evidence register

2026-10-14. Related issues #30, #52 and #31. **PROPOSED_NOT_APPROVED.**
This register distinguishes transferred evidence, direct source inspection, new
synthetic validation and work requiring the original data-holding machine.

## Supplied material and version boundary

The supplied `Perturb-LM-Astra-Ultra.zip` is an actual source snapshot: **374 files**
in 427 ZIP entries, 949,448 compressed bytes and 2,260,431 uncompressed file bytes.
Archive SHA-256:
`eafc08c6f185cef8eb7dfb641442aed746ec06af63c063dbb235cbf4cab2d976`.
Archive integrity passed. The snapshot includes `src/`, `scripts/`, `tests/`,
the seven Phase 5 scientific documents, four Phase 5.1 documents and the existing
plan-only rotation generator. It contains no Git history, original cohort
profiles or private audit mapping. Historical aggregate result tables and
explicit synthetic fixtures are present; their presence is not a new execution.

The user identifies main commit
`c0518710d38adb17a21e150db45b0388a503b030` and reports PR #76 merged on October 14.
Those are **user-supplied provenance**, not a live remote or Git-object verification
performed here. The transfer helper checks the actual checkout commit and all
374 baseline file hashes before applying additions. A discrepancy must be
reconciled, not bypassed by changing the expected commit.

No separately named new research-handoff document is inside this ZIP. The
earlier Phase 5-to-5.1 handoff already supplied in this conversation was also
read. Its historical synchronization instructions predate the completed PRs and
are superseded by the current request; they are not a reason to repeat Phase 5.1.
This work uses the new ZIP for implementation, rather than silently substituting
an older checkout available in the workspace.

## Evidence classification

| Item | What is established here | What is not established |
|---|---|---|
| Existing cohort: 4,524 profiles, 904 features, 12 plates | Reported by the supplied completed Phase 5 audit | No private rows or profile checksums were rerun here |
| Strict non-control support: 13 CRISPR reagents; four-plate U2OS report: 104 rows | Prior audit/scope findings | Per-rotation support, distinct effective genes and independent cultures remain unknown |
| Historical V2: eight strings for 641 treatment identities | Prior renderer audit; current source inspected | No new encoder result or universal mAP ceiling |
| Historical BiomedBERT/MedCPT/BioLORD/CellCLIP evidence | Comparator documents and aggregate result artifacts are present | No new Phase 5.2 inference; older public pending-result language is not silently rewritten |
| Existing Phase 5.1 rotation planner | Actual implementation and synthetic tests are supplied | Merge/publication does not approve a scientific endpoint or execution |
| Public layout/annotation facts below | Primary documentation and selected browser-rendered rows inspected | No complete, immutable, checksum-verified upstream table snapshot was downloaded here |
| New compound layout crosswalk | Additive implementation plus explicitly synthetic validation | No real crosswalk totals, measured replicate counts, biological validity or statistical power |

## Public sources and findings

Accessed October 14, 2026. Mutable browser views may reflect cached versions.
The executable audit requires a separately pinned raw-byte snapshot.

| ID | Primary source | Supported finding and limitation |
|---|---|---|
| S1 | [JUMP-Target README](https://github.com/jump-cellpainting/JUMP-Target/blob/master/README.md) | Two compound layouts; one CRISPR and one ORF layout. Compound sample IDs may differ; source recommends InChIKey joins. Source CRISPR design includes multiple guides per gene; this is not a count of eligible local measurements. |
| S2 | [Pinned JUMP structure standardizer](https://github.com/broadinstitute/monorepo/blob/912315df698cc0f3e9daadcd6ef994a7af94fbdd/libs/smiles/src/smiles/standardize_smiles.py) | Parent transformations include charge, isotope, stereo and tautomer handling before key generation. Full-key matches in the standardized metadata do not certify original stereochemical identity or a common stock/lot. The exact recipe producing each downloaded table still needs its own lineage record. |
| S3 | [Chandrasekaran et al., Nature Methods 2025](https://doi.org/10.1038/s41592-025-02753-9), [author manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC12439680/) | Describes four Target-1 compound plates in one source_4 production batch, Target-2 measurements across batches and separate polybrene conditions. This motivates a bridge search; exact condition-matched plate IDs and layout-by-batch crossing were not verified here. |
| S4 | [Target-1 compound metadata](https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/refs/heads/master/JUMP-Target-1_compound_metadata.tsv) and [map](https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/master/JUMP-Target-1_compound_platemap.tsv) | One manually inspected example is recorded below. No complete match count is inferred from file length. |
| S5 | [Target-2 compound metadata](https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/refs/heads/master/JUMP-Target-2_compound_metadata.tsv) and [map](https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/refs/heads/master/JUMP-Target-2_compound_platemap.tsv) | Selected matching rows and coordinates inspected. Duplicate annotation rows must not multiply wells; DMSO solvent alone is not a control annotation. |
| S6 | [Production metadata schema](https://github.com/jump-cellpainting/datasets/blob/main/metadata/README.md) | Source/batch/plate/well/JCP identifiers and separate compound/control tables support an observed-measurement join. The schema is not an observed eligible cohort. |
| S7 | [CPJUMP1 primary paper](https://doi.org/10.1038/s41592-024-02241-6) and [source README](https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/blob/main/README.md) | Public assay/layout and processing descriptions support confounder assessment. They do not bind the user's existing `normalized_feature_select_negcon_batch` files to a proven fit population. |
| S8 | [Public feature-selection configuration](https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/blob/main/config_files/config_compounds_crispr_orf_feature_select.yml), [pinned processing implementation](https://github.com/jump-cellpainting/profiling-recipe/blob/342789895ec349a16ed38ccee1d6385e89063029/profiles/profile.py), [wrapper](https://github.com/jump-cellpainting/profiling-recipe/blob/342789895ec349a16ed38ccee1d6385e89063029/profiles/profiling_pipeline.py) | Configuration requests batch-level feature selection; implementation concatenates configured plate frames before selecting features. Negative-control normalization is a separate per-plate step. The mutable configuration, audit revision and actual local bytes have not been linked, so this establishes a concrete provenance risk, not verified local processing history. |

Concrete design-level example inspected in S4/S5: the LOXO-101 annotation is
`BRD-K36574127-001-01-3` at A06 in Target-1 and
`BRD-K36574127-001-04-9` at O21 in Target-2. Both records give full standardized
key `NYNZQNWKBKUAII-UHFFFAOYSA-N`. This establishes a plausible coordinate-changing
metadata bridge despite different sample IDs. It does not establish matched
assay conditions, biological replication, profile availability or a phenotype.
These mutable rows are an inspected example, not an executable frozen fixture.

For annotation resource semantics, see the source links in
[the query/preprocessing specification](PHASE5_2_QUERY_AND_PREPROCESSING.md).
No private-cohort gene annotation corpus was collected or adjudicated.

## Unresolved evidence that changes the experiment choice

1. Original profile/mapping provenance and actual Phase 5.1 rotation coverage.
2. Same-gene/different-guide eligibility, guide quality and culture independence.
3. Complete standardized-key/layout crosswalk and chemistry ambiguity review.
4. Observed Target-1/Target-2 plate/well records and layout × batch × condition support.
5. Raw-to-profile processing lineage, fitting populations and ordered feature compatibility.
6. Evidence-disjoint query assertions and relevance annotations, with source-publication overlap.
7. A source-bound scientific decision on primary endpoint, uncertainty, eligibility and claims.

Missing items remain unknown. Neither a new checksum nor a successful parser can
replace the underlying biological/provenance evidence. No GitHub write, private
data upload, pretrained inference or scored experiment was performed in this phase.
