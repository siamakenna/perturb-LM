# Phase 5.2 scientific development

2026-10-14. **PROPOSED_NOT_APPROVED.** Related issues: #30, #52 and #31.
This proposal does not change frozen benchmarks, approve experiments, or report new private-data results.

## Evidence and decision

The transfer contains actual repository source: 374 files, including the seven Phase 5 scientific documents, four Phase 5.1 documents, the rotation planner and tests. It contains no Git history or private profile/mapping outputs. `c0518710d38adb17a21e150db45b0388a503b030` is the user's supplied main revision; this conversation has not independently established that every archived file matches that Git tree. See the [evidence register](PHASE5_2_EVIDENCE_REGISTER.md). The original Mac's audit is evidence reported in supplied documents, not an analysis rerun here.

**Keep the 13-reagent CRISPR experiment as feasibility, and develop a position-diverse, biologically defined experiment before making biological-retrieval claims.** It could be a principal worked example in a narrowly framed methodological audit; it is not sufficient as the sole primary evidence for meaningful biological relationship recovery.

This judgment is not a universal sample-size cutoff. The joint limitations are a layout-selected subset of at most 13 reagents, possibly fewer independent gene groups, one source batch, unresolved culture lineage, four WGA-flagged plates, unknown upstream preprocessing scope, intentional reagent exposure during training, and a category-only comparison whose information deficit is already known. The reported 104 U2OS rows precede rotation-specific training support and filtering. More rotations, sites or crops do not repair these limitations.

**Two immediate priorities are complementary:** assess same-gene/different-guide support in existing metadata before expanding CPJUMP1 downloads, and investigate the public Target-1/Target-2 compound layouts as a possible route to position-diverse measurements. Keep the existing Phase 5.1 planner; do not rebuild completed engineering.

## Four distinct questions

| Question | Proposed relevance | Interpretation and limit |
| --- | --- | --- |
| Exact-reagent recovery | Same reagent on a different physical plate and coordinate | Measurement repeatability within the tested context; not unseen-target generalization |
| Query-information sensitivity | Same relevance and paired eligible population, V1 versus V2 | Dependence on supplied gene identity; not a balanced test of encoder biology |
| Same-gene/different-guide concordance | Distinct CRISPR reagents with independently verified same-gene mapping; exclude exact-reagent matches | Agreement across different interventions annotated to a target; still subject to guide efficacy and off-target effects |
| Functional/target-relationship retrieval | Independently sourced, reviewed relationship labels with explicit direction and context | Recovery of the defined relation; shared annotation alone does not establish phenocopy or mechanism |

A guide is not a gene; a compound is not its principal target. Knockout, inhibition and overexpression are different interventions. The local compound/CRISPR comparison also changes exposure (24 versus 144 hours) and parental/Cas9 state. None of these endpoints may be silently substituted for another after observing scores.

## Cohort expansion priorities

| Priority and design | What it may add | What it does not solve | Metadata decision before acquisition |
| --- | --- | --- | --- |
| 1. Existing CPJUMP1 same-gene/different-guide assessment | A biologically stronger concordance question using existing measurements | Gene-aware lookup, shared culture/layout structure, efficacy and off-target uncertainty | Verify distinct reagent and guide identities, same-gene mapping, cross-position support, matched conditions and disjointness appropriate to the claim |
| 1. Target-1/Target-2 compound layout bridge | Measurements associated with different compound layouts; potential broader position-diverse recovery | Layout may be confounded with batch/source; standardized chemical groups are not exact lots | Verify identity semantics, actual well shifts, same-condition availability, culture lineage and layout-by-batch/source crossing |
| 2. Three additional A549 no-antibiotic CRISPR plates | Separate four-plate stratum with existing BR00117000, without documented WGA anomaly | Fixed-layout identity/position confounding or independent batches | Confirm BR00117003–BR00117005 availability, lineage, profiles and actual eligibility; keep separate from U2OS and puromycin strata |
| 3. Additional ORF or cross-modality profiles | Different intervention direction and potential target relationships | Exposure/dose equivalence, automatic phenocopy or four-role split feasibility | Approve intervention-specific relevance and matched conditions before acquiring profiles |
| Deferred. More encoders or DINOv2 | Possible robustness/comparator evidence later | Missing biological labels, ambiguous identity or absent independent replication | Reconsider only for a specific scientific question or reviewer request |

### Near-term alternative: different guides for the same gene

The CPJUMP1 source design reports **117 non-control genes with two guides and 13 with one guide**. These are source-design counts, not counts of locally eligible pairs or independent biological units. They motivate a bounded metadata assessment; they do not establish that local guide pairs survive the required filters. [Official JUMP-Target design README][cpjump-readme]

For each proposed pair, preserve the exact reagent identity and guide identity in the private audit channel, independently map a stable gene identifier, exclude identical reagents, require different plates and coordinates, and match the recorded conditions. Count distinct guides, coordinates, plates and culture preparations separately. A distinct coordinate can still share row, column or edge structure. Report unavailable or ambiguous mappings rather than inferring guide distinctions from sample-name similarity.

A guide-held-out design can assess transfer to another intervention at a **seen gene**. That is stronger than same-reagent repetition for guide robustness, but supplied gene identity still offers a direct lookup route. A held-out-gene claim instead requires grouping all guides and gene aliases across fitting roles; whether enough groups and positives remain is unknown. The existing rotation planner does not implement either new endpoint. Specify and review them separately before writing a scored runner.

### Target-1/Target-2: promising but not automatically independent

The public alternate-layout bridge concerns **compound** Target-1/Target-2 plates; the official design has one CRISPR and one ORF layout. It is not evidence of randomized alternate CRISPR layouts. [Target design][cpjump-readme] The production-dataset paper describes four Target-1 plates in one Broad/source_4 batch. Consequently, an apparent Target-1 versus Target-2 difference could also be a batch/source difference unless the selected data contain adequate crossing. Replicate Target-1 plates within one batch do not identify a population-level layout effect. [Production-dataset manuscript][production-paper]

Start with a metadata matrix of source, experimentally defined batch, layout, cell context, dose/duration, microscope/pipeline and available culture lineage. For every matched compound group, count coordinates, rows/columns/edges and query/gallery condition-compatible pairs. Test whether both layouts occur within comparable batch/source conditions, and whether each treatment occupies multiple positions. Where crossing is absent, characterize the proposed comparison as joint layout-and-batch transfer; do not statistically adjust away an unidentifiable distinction and claim a pure layout effect.

The JUMP-Target bridge keys denote standardized parent chemical groupings. The README-linked standardizer applies charge, isotope, stereochemical and tautomer parent transformations; matching even the full resulting key cannot recover those distinctions or prove exact supplier material, lot, mixture or dose identity. Keep source sample IDs, supplied chemical structures, standardization version and ambiguous/many-to-one matches. Relevance can be proposed at standardized-parent level, but it must be named and approved as such rather than mislabeled exact-reagent recovery. [Pinned standardizer implementation][metadata-construction]

No profile download is justified solely by nominal target overlap or a new barcode. First inspect bounded public metadata and object inventories, then propose a small named acquisition with exact objects, sizes, checksums and a distinct data manifest. Preserve the historical 12-file cohort.

## Query information and preprocessing

V1 deliberately exposes gene identity. V2 supplies category-only strings and cannot distinguish treatments within an identical text signature under identical fitting state and candidate sets. Different masks can produce different observed rankings without adding textual information. Therefore V1 minus V2 is useful as an information ablation, not proof of biological language understanding. Multiple guides sharing a gene may remain indistinguishable under V1.

Keep V2 as a weak control. Before any new representation, audit exact text collisions together with candidate-set and fitting-state equivalence; report pre-guard render counts separately from encodeable queries. The production F10 gene/well guard conflict remains unresolved; no exception is approved here. Use the proposed independently annotated query and provenance workflow in [query and preprocessing design](PHASE5_2_QUERY_AND_PREPROCESSING.md). Do not generate phenotype descriptions from the same morphology used to score success, and do not call absence of an annotation a verified biological negative.

For every upstream transform, record input hashes, software/configuration, fit population, application population and controls. Distinguish illumination correction, negative-control normalization, batch adjustment, feature selection, missingness handling, scaling and alignment. The filename `normalized_feature_select_negcon_batch` and an unchanged 904-column count do not establish fit boundaries or harmonization.

Three scopes must remain separate:

- Source-preprocessed descriptive feasibility can be reported with its unresolved or batch-global scope, without an inductive claim.
- Held-out plate controls may support an explicitly approved test-time calibration protocol, which is different from wholly train-only preprocessing.
- Inductive transfer requires suitable less-processed inputs and fitting/selection confined to training material. A new train-only scaler cannot undo upstream use of held-out profiles.

Matching the WGA flag defines a condition; it does not establish that the anomaly is harmless. A549 versus U2OS cannot estimate a WGA effect because cell context also differs. All QC restrictions must be chosen before inspecting retrieval scores.

## Analyses, estimands and statistical units

For the existing feasibility design, retain Phase 5.1's proposed paired V1-minus-V2 macro reagent AP. Filter individual gallery rows by each query's plate/well mask, then aggregate surviving scores by reagent using `mean_scores_after_filtering`. Keep the complete eligible non-control gallery, including unrecoverable query identities. With one positive reagent, AP is reciprocal rank; no positive means undefined AP, not zero.

Average paired row differences within reagent/rotation, then equally over that reagent's eligible rotations, then equally over reagents. Publish support for every averaging level. The proposed weighting differs from historical frozen results and still needs scientific approval. A common-support sensitivity may be unavailable; do not relax masks to manufacture it.

Report coverage beside performance: selected/query/training/gallery rows; reagent and gene groups; candidate and positive counts after filtering; exclusion reasons; collision size; and plate support. Compare retained versus excluded treatments descriptively using prescore metadata. The 13 eligible reagents are layout-selected, so macro averaging or bootstrapping does not make them representative of all treatments. Candidate-set size must be considered when interpreting random controls; missing positives cannot be repaired by invented labels.

The reagent is the endpoint weighting unit, not automatically the biological replicate. Claire must establish independent culture/manipulation units. If multiple guides share a gene, keep them together in target-cluster uncertainty; missing or multi-gene mappings require a reviewed rule. With few groups, show all group effects and describe interval instability rather than claiming assured precision. Shared plates also induce dependence that reagent clustering alone does not remove.

All twelve rotations reuse four physical plates. Report query-plate and gallery-plate role diagnostics; they are not twelve independent validations. Every rotation uses all four plates, so leave-one-plate-out changes the two-training/one-query/one-gallery design and requires separate approval. Seeds, crops, cells and pair counts are not extra biological replicates.

Permutation nulls need an exchangeability argument. Preserve reagent/guide repetitions, conditions and fixed candidate masks; independent row shuffling is inappropriate. If layout and treatment leave no credible exchangeability set, report that null unavailable. Select a meaningful effect and precision target before a larger study; any design simulation must state assumed variances and dependence, not invent statistical power from 104 rows.

## Figures and executable roadmap

| Step / figure | Work now | Output and decision |
| --- | --- | --- |
| A. Evidence and cohort flow | Reconcile transferred source and prior reported counts; original Mac verifies existing profile/source manifests and runs the Phase 5.1 planner | Provenance ledger and real per-rotation coverage; no new model execution |
| B. Identity-position support | Bounded public Target-1/Target-2 metadata plus private same-gene/different-guide assessment | Treatment-by-layout/position matrix, matched-condition coverage and ambiguity counts; decide which design merits acquisition |
| C. Query information | Existing renderers, collisions and candidate-set equivalence; synthetic checks | Information-content figure, scoped guard findings and eligible denominators; decide query/relevance contract |
| D. Future feasibility effects | Only after source-bound experiment approval | Individual reagent effects, macro paired endpoint, common-support coverage and plate-role diagnostics |
| E. Future biological relationships | Only after independent annotations and compatible cohort approval | Retrieval of prespecified relations with group uncertainty and unknown-label coverage; no phenocopy claim by default |

Figures D/E remain specifications until scored analyses actually run. Embedding plots are optional diagnostics, not independent biological validation. The two prepared BR00117011 sites are outside this CRISPR cohort; crops and full fields are derivatives, not new independent observations.

## Collaborator action plan

| Owner | Concrete responsibility | Decision still required |
| --- | --- | --- |
| Makenna | Choose a narrow reliability-audit manuscript or a stronger biological relationship primary aim; select the endpoint after metadata support is known | Manuscript scope, experiment selection, any additional data acquisition, and later publication |
| Claire | Review guide/gene identity, culture independence, WGA and controls; define biologically defensible relevance and annotation sources | Replicate unit, intervention direction, meaningful effect/precision, exclusions and biological interpretation |
| Adam | Verify original manifests; run existing plan; inspect layout crossing, identity standardization, preprocessing fit populations, split integrity and F10 guard | Technical validation and whether the intended claim is supported by provenance and implementation |
| Shared | Freeze population, relevance, text fields, preprocessing, masks, controls, tie policy, weighting, uncertainty and failure conditions | A source-bound scored-experiment decision; merged planning code does not supply this approval |

Preserve historical comparator evidence. Older generic claims documents say learned results are pending, while comparator documents and the strict-result CSV record historical BiomedBERT, MedCPT, BioLORD and CellCLIP evaluations. Reconcile wording and source lineage without overwriting results. The 641-treatment lexical reference, historical 1,079/180 comparator population and current strict-replication cohort are different denominators. None is a newly executed Phase 5.2 result.

DINOv2 remains optional. The immediate scientific bottlenecks are informative queries, defensible relevance, position-diverse measurements and preprocessing provenance—not additional pretrained models.

[cpjump-readme]: https://github.com/jump-cellpainting/JUMP-Target/blob/master/README.md
[production-paper]: https://www.nature.com/articles/s41592-025-02753-9
[metadata-construction]: https://github.com/broadinstitute/monorepo/blob/912315df698cc0f3e9daadcd6ef994a7af94fbdd/libs/smiles/src/smiles/standardize_smiles.py
