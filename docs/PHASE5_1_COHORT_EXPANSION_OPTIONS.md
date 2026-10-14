# Phase 5.1 cohort expansion assessment

2026-10-14. Related issues: [#30](https://github.com/siamakenna/perturb-LM/issues/30) and [#52](https://github.com/siamakenna/perturb-LM/issues/52). Public-metadata assessment and experimental proposal only; no additional profiles, images, embeddings or checkpoints were downloaded. No expanded cohort or benchmark is approved by this document.

## Recommendation

Complete the four-plate U2OS CRISPR rotation-feasibility assessment before scoring. If a bounded expansion is selected, the most concrete CPJUMP1 option is to add **BR00117003, BR00117004 and BR00117005** to existing **BR00117000**, creating a separate four-plate A549 CRISPR condition. This can test whether an exploratory finding also appears in a second recorded cell context without the U2OS WGA flag. It does **not** supply new reagent placements, resolve the narrow set of exact-treatment positives, establish independent batches, or identify a causal WGA effect.

If the scientific requirement is many more non-control treatments with different-coordinate positives, this expansion does not meet it. The better next metadata investigation is the JUMP-Target-1/Target-2 layout bridge in the larger JUMP release, with explicit compound-identity and coordinate joins. Its plate-level eligibility remains unresolved here. Broadening model coverage cannot repair either missing positive pairs or indistinguishable query text.

## Evidence status

The supplied Git bundle contains the Phase 5 audit at `0ee3a11d6e27975df79798ff6f67bfba08258074`. The [cohort audit](PHASE5_CPJUMP1_COHORT_AUDIT.md) supplies prior real-profile evidence: 12 files, 4,524 rows, 904 matching features, and no ORF rows in the frozen cohort. Those profile files and private audit CSVs are absent from this workspace. Their counts are inherited audit findings, **not rerun measurements**.

For this assessment, the pinned original [experiment table][experiment] and [README][source-readme] were read directly through the browser. The table verifies the candidate conditions below. Attempts to read the pinned barcode map, ORF well map and ORF annotation table returned cache misses. Their presence and the three fixed modality layouts are documented by Phase 5; no fresh well-level overlap count or raw-byte checksum is claimed here. A browser rendering is not a substitute for the checksum-verified source snapshot required by the executable audit.

All CPJUMP1 source paths below use repository `jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1` at immutable revision **`56845c7d4dc322652952783d91dae0ffef47829f`**.

## Specific source candidates

The following rows were rechecked in the pinned experiment table. All belong to `2020_11_04_CPJUMP1`; all have `Density=100`, `Antibiotics=absent`, `Time_delay=Day0`, and `Times_imaged=1`.

| Role | Plate IDs | Cells/state | Modality, exposure | Anomaly |
| --- | --- | --- | --- | --- |
| Existing narrow cohort | BR00116996, BR00116997, BR00116998, BR00116999 | U2OS/Cas9 | CRISPR, 144 h | WGA |
| Concrete expansion | BR00117000, BR00117003, BR00117004, BR00117005 | A549/Cas9 | CRISPR, 144 h | none |
| ORF candidate pair | BR00117020, BR00117021 | A549/parental | ORF, 48 h | none |
| ORF candidate pair | BR00117022, BR00117023 | U2OS/parental | ORF, 48 h | none |
| Optional compound partner | BR00117011, BR00117012 | U2OS/parental | compound, 48 h | none |

The anomaly value `none` means no anomaly documented in this field, not image-QC certification. Other U2OS 48 h compound plates BR00117010 and BR00117013 carry a Mitotracker flag and are not silently pooled with this pair. [Source][experiment]

`Density=100` is a percentage of the modality-specific baseline, not a shared absolute cell count. Equal exposure or relative density therefore does not make ORF and compound conditions biologically interchangeable. Imaging-site counts are technical sampling, not independent replicates. The original README identifies well-level aggregate profiles and a profile-processing workflow, but exact candidate object availability, row counts, source-normalization scope and feature schemas still require verification. [Source][source-readme]

## Existing cohort versus bounded expansion

| Design question | Four U2OS CRISPR plates | A549 CRISPR expansion |
| --- | --- | --- |
| Local evidence | Phase 5 reports actual rows and complete plate/well joins | BR00117000 is in the frozen cohort; availability of the three additions on the user's machine is unknown |
| Strict non-control population | Prior audit: 13 reagent IDs and 104 rows before rotation-specific eligibility checks | Same CRISPR map; no new eligible-ID count can be claimed before inspecting actual added profiles |
| Plate roles | Four plates permit ordered query/gallery choices with the other two reserved for fitting | Same nominal four-plate design is possible if actual rows, conditions and positive coverage pass |
| Advantage | No new profile acquisition is needed where the audited local data already exist | Adds a separately analyzed cell context and plate replication without a documented WGA anomaly |
| Position diversity | Limited by the shared reagent layout | Fixed layout remains; adding copies cannot create new reagent coordinates |
| Biological independence | Culture lineage and exact replicate unit unresolved | New plate barcodes alone do not resolve those same uncertainties |
| New claim supported now | Feasibility and information-content diagnostics | Metadata-grounded expansion proposal only |

Do not pool the A549 puromycin plates BR00117001/BR00117002 into the no-antibiotic condition to increase its size. Do not present an A549-versus-U2OS difference as a WGA intervention: cell type and anomaly differ together. A successful matched-condition replication would remain a second exploratory stratum, not held-out-batch validation. Separate query collision tables are needed for each candidate population.

Twelve ordered query/gallery plate choices are combinatorially possible with four plates. This arithmetic is not evidence that all twelve have eligible queries, independent measurements or sufficient effective sample size. Candidate masks, treatment support in training, distinct coordinates and annotation completeness must be checked from real row mappings for each rotation.

## ORF: useful endpoint expansion, different design

The ORF pairs above are concrete metadata candidates for a later Endpoint B assessment. They add a perturbation direction absent from the frozen 12-file cohort. Each displayed matched condition has only two plates, so it cannot directly support the proposed two-training/one-query/one-gallery plate scheme. No ORF profile rows have been inspected or acquired in Phase 5.1.

Before selecting either pair, join the exact `(Batch, Assay_Plate_Barcode)` to the barcode map, `(Plate_Map_Name, well_position)` to the ORF well map, and `(Perturbation, broad_sample)` to the source annotation. Retain ORF construct identity, target gene, controls, duplicates and unresolved annotations. Multiple constructs for a gene are not the same reagent; opposite perturbation direction is not automatically a morphology match. Any compound–ORF proposal also needs a reviewed target/alias mapping and an explicit handling of multi-target compounds. Counts of shared genes would describe annotations, not experimentally established phenocopies.

The optional U2OS compound pair permits a same-recorded-duration cross-modality proposal. It does not repair culture/perturbation differences, prove dose equivalence or establish independent validation. The existing CRISPR condition has a different exposure duration. Expanding ORF simply to increase model counts is not justified.

## What could actually address layout or batch confounding?

The consortium's [principal-dataset manuscript][principal-paper] describes JUMP-Target-1 and JUMP-Target-2 compound plates with matching contents but different layouts, and a source_4 Target-1 bridge in the production dataset. This is a promising **published design-level lead**, not a plate manifest or a verified count of eligible pairs. Repeated production plates using only one layout would still not solve exact-treatment/position confounding.

The current [official metadata schema][metadata-schema] provides source, batch, plate, well and perturbation identifiers, separate compound/genetic annotation, control designations and imaging/pipeline metadata. The broader metadata repository is different from the pinned CPJUMP1 repository. Its reviewed commit and checksums have not been fixed in this assessment; no production plate IDs or independent-batch count are invented.

A bounded next metadata-only investigation should:

1. Pin a reviewed `jump-cellpainting/datasets` revision. Acquire only the needed plate/well/compound/control metadata and the two target layouts, with file-size limits and checksums; do not issue recursive profile or image downloads.
2. Identify the documented Target-1 bridge and candidate Target-2 plate groups from the plate metadata. Join by source plus plate, preserving batch and duplicate/ambiguous keys.
3. Establish an explicit compound identity crosswalk between CPJUMP1 sample IDs and production JCP IDs using source annotations. Preserve salts/aliases, stereochemical ambiguity, mixtures and unmatched IDs; do not join on unreviewed display names or rounded numeric identifiers.
4. Count distinct coordinates for each same-reagent or approved compound identity across layouts, then apply cell/dose/duration/control restrictions and count surviving query/gallery pairs. Report losses at every join and filter. Treatment overlap alone does not establish exposure matching.
5. Resolve experimental generation lineage, dates and culture preparation. Distinct acquisition-directory strings do not certify independent experimental batches. Source IDs also must not be assumed to identify independent laboratories without provenance.
6. Inspect exact profile manifests and upstream fitting before proposing a held-out-source/batch comparison. Record duplicate physical wells, repeat acquisitions, technical subsamples and source-protocol shifts explicitly.

The CPJUMP1 delayed-imaging and bleaching collections cannot be counted as independent cultures merely because their folder names differ. The pinned table repeats physical plate identities with changed storage/imaging fields; the original README explains those fields. They may support acquisition-stability questions under a separately approved protocol, not an automatic increase in biological replication. [Sources][experiment] [and field definitions][source-readme]

## Profile acquisition and normalization contract

For the bounded A549 proposal, the existing historical selector expects:

```text
profiles/2020_11_04_CPJUMP1/<plate>/<plate>_normalized_feature_select_negcon_batch.csv.gz
```

This is a **candidate path template from the audited selector**, not a fresh assertion that every object exists. Inspect repository tree/LFS pointer metadata or a bounded object inventory before downloading a single approved file. Resolve exact object URLs, sizes and checksums; compare plate IDs observed in the rows with the selection, rather than inferring one plate per filename. Preserve the frozen 12-file dataset unchanged and put any approved additions under a separate ignored data root and manifest.

Required before expanded analysis:

- Reproduce the experiment/barcode/well/annotation joins; report missing labels, absent wells, control classifications and conflicts without imputing them. Keep the complete non-control gallery, not just recoverable IDs.
- Compare ordered feature names, units, CellProfiler pipeline/version and channel measurements. Identical column count is insufficient. Do not fill absent features with zero or silently concatenate differently processed schemas.
- Trace upstream negative-control normalization and feature-selection fit populations from the pinned workflow/configuration. Filename wording does not prove train-only preprocessing. The README documents source preprocessing but does not establish the fit boundaries needed for this proposed split.
- If only source-preprocessed features are usable, label the analysis as conditional on that preprocessing and obtain review of its transductive scope. Applying a new train-only scaler cannot undo earlier batch-wide selection. An inductive claim requires appropriate less-processed inputs and transformations fitted without held-out query/gallery data; any use of held-out controls for calibration must be separately declared.
- Keep plate-level nulls, controls, non-control estimands and uncertainty units distinct. More rows do not create more independent reagents or culture replicates. Freeze feature and metadata hashes before future scoring.

## Existing image preparation: optional technical sidecar

The user-supplied `jump-preparation-summary.json` reports successful full-size and center-crop pixel processing for BR00117011 wells A01/A02, site 1: two accepted images and zero exclusions in each variant, with raw inputs unchanged. Source code revision was `bbd5aab2c2803623d7e21f6eee7193042ab157dd`. This establishes reported technical preparation only; visual review of the corresponding masks/previews has not occurred here.

BR00117011 is outside the audited 12-plate profile cohort and outside the proposed CRISPR strata. Two sites from two wells on one compound plate are not additional independent replicate plates. Full and cropped versions are derivatives of the same fields. They cannot substitute for profile-to-image mappings, a blinded evaluation set or biological validation. No raw images, local paths or derived measurements are committed. The sidecar can remain parked while Phase 5.1 proceeds; DINOv2 is optional and off the critical path.

## Decision record to complete after evidence review

Makenna can choose the existing-data diagnostic or the separately staged A549 extension after seeing actual rotation coverage. Claire's review should resolve reagent/replicate identity, minimum effective units, controls and anomaly interpretation. Adam's technical review should resolve joins, duplicate acquisition handling, feature harmonization and upstream fit scope. These are proposed review responsibilities from Phase 5, not approvals inferred from this assessment. None requires a pretrained run to make the decision concrete.

If the intended primary claim requires broad position-diverse or batch-generalized biology, retain that goal but mark this CPJUMP1 expansion insufficient. Finish the production Target-1/Target-2 metadata crosswalk before choosing a larger profile download or changing the approved benchmark definition.

[experiment]: https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/blob/56845c7d4dc322652952783d91dae0ffef47829f/benchmark/output/experiment-metadata.tsv
[source-readme]: https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/blob/56845c7d4dc322652952783d91dae0ffef47829f/README.md
[principal-paper]: https://www.biorxiv.org/content/10.1101/2023.03.23.534023v2.full
[metadata-schema]: https://github.com/jump-cellpainting/datasets/blob/main/metadata/README.md
