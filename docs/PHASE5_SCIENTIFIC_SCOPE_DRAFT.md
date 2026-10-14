# Phase 5 scientific scope — draft, not approved

2026-10-14. Related issues: [#30](https://github.com/siamakenna/perturb-LM/issues/30), [#52](https://github.com/siamakenna/perturb-LM/issues/52), [#31](https://github.com/siamakenna/perturb-LM/issues/31). No contract is approved by this document. The [cohort](PHASE5_CPJUMP1_COHORT_AUDIT.md), [query](PHASE5_QUERY_IDENTIFIABILITY_AUDIT.md) and [design](PHASE5_EXPERIMENTAL_DESIGN_REVIEW.md) audits provide the empirical constraints.

## Primary question and hypotheses

**How sensitive are biomedical language-to-morphology retrieval conclusions to query information, experimental structure, and the biological definition of a correct match?**

Hypotheses to prespecify:

1. Apparent exact-treatment retrieval is partly attributable to visible gene identity and fixed experimental layout. Removing these information sources changes both achievable discrimination and the evaluable population.
2. Matching target annotations is a distinct biological question from reproducing a reagent's morphology. Annotation uncertainty and unequal exposures can reduce concordance even with correct labels.
3. A representation advantage counts as biological evidence only if it improves an independently curated endpoint under matched information, preprocessing and evaluation conditions. Different embedding geometry alone is insufficient.

The audits already establish absent distinctions in V2 text and severe position-related eligibility loss. They do not establish how much of any historical performance is caused by either factor.

## One primary experiment: query-information sensitivity under strict replicate recovery

Use **Endpoint A**, narrowly framed as seen-treatment transfer across plates and well positions, with the U2OS 144 h CRISPR stratum as the initial cohort. Its four plates share recorded culture conditions and WGA status. The 13 non-control reagent IDs with different-coordinate exact-ID replicates supply 104 profile rows in this stratum; another 52 eligible rows in A549 with puromycin are a separate stratum, not pooled validation of the same cell context.

Before scoring, Claire must confirm that the repeated reagent IDs represent the intended replicate unit. Prespecify the candidate universe as all labeled non-control CRISPR treatments in the same condition (not only the 13 recoverable IDs); report excluded queries lacking positives. The primary estimand is the paired change in exact-treatment retrieval under gene-aware versus category-only query information with identical candidates. Preserve per-record plate/well masks and aggregate after filtering. The 13-reagent limit makes this an exploratory diagnostic, not a definitive biological generalization experiment.

Start with existing TF-IDF, CellProfiler profiles, random/shuffled controls and explicit gene lookup. If text-to-profile alignment is used, hold separate query and gallery plates out of fitting; fit vocabulary/scaling/ridge only on the other plates, and predefine all ordered query/gallery plate rotations. This evaluates treatments seen during training, not unseen-target generalization. Controls must use identical masks and folds. Do not directly apply cosine between unrelated-dimensional TF-IDF and morphology spaces. A new real-data runner/configuration needs an approved issue; the existing synthetic-only V2 worker must not be bypassed.

Use historical V1 and V2 **as named**, with V2 a proposed weak control. Resolve the F10 namespace guard conflict before any affected text is encoded. A later independently annotated biological-context condition is an extension requiring an approved M1 policy; it is not silently substituted here. Run at most one learned biomedical comparator after the information and replicate checks; MedCPT is the distinct retrieval-oriented choice, while BiomedBERT remains the historical anchor.

## At most two secondary analyses

1. **Experimental structure sensitivity:** contrast same-position-allowed versus different-position eligibility and results; report plate/coordinate diagnostics and controls separately. Compare the two A549 puromycin plates only as a distinct exploratory stratum. Already completed descriptive cosine moments motivate this analysis but are not its retrieval results.
2. **Endpoint B, curated target relationships:** retain original principal target and multi-target lists separately, review disagreements, require cell-matched pairs, exclude controls from biological positives, and explicitly label 24 h compound versus 144 h CRISPR comparisons as unmatched exposure. The available annotation intersections permit candidate construction; they do not approve a phenocopy rule. Prespecify signed versus absolute similarity only if biologically justified. Keep guide concordance, compound polypharmacology, direction of action and ambiguous pairs explicit. ORF comparison requires additional profiles.

**Endpoint C is deferred.** A future study can compare representation-specific recovery on independent annotations or blinded morphology judgments. Low-dimensional plots, neighbor changes and clustering separation remain diagnostics. Additional image encoders are not a substitute for endpoint independence or exact image mapping.

## Dataset eligibility and confounders

Use the immutable 12-file manifest and resolved sample IDs. Historical missing-label exclusions remain explicit, with negative-control QC handled separately. Preserve all cell type/Cas9, modality, exposure, dose provenance, density, antibiotics, batch, plate, coordinate, staining and acquisition annotations. Unknown culture lineage, achieved dose and perturbation efficacy remain limitations. Current profiles have source-level normalization and feature selection; approve their transductive scope or obtain appropriate less-processed profiles before claiming train-only generalization. One source batch cannot support cross-batch inference.

## Nulls, metrics and uncertainty

Nulls: random ranking with the same candidate sets; treatment-label permutations blocked within cell/modality/condition; neutral/category-only text; shuffled query-to-treatment mapping; explicit gene lookup as an identity shortcut comparator. Review which permutations preserve the estimand and plate structure. No score-based selection of queries or null settings.

Primary metric: macro treatment-level AP after filtering and prespecified replicate aggregation, reported with the paired condition difference. Secondary summaries: Hit/Recall@1, @5, @10; total/evaluable/excluded queries; number of positive candidates; same-plate/well/batch rates; control versus non-control strata. Counts must accompany every metric. Keep historical profile-row AP distinct from proposed treatment-level scoring; never compare them as if only the model changed.

Uncertainty: paired resampling over reagent groups for Endpoint A; over approved target/gene groups for Endpoint B, preserving multi-target dependencies. Report all plate rotations and leave-one-plate sensitivity. A small number of plates does not support precise population-level plate uncertainty. With 13 eligible non-control reagents, report broad intervals and exploratory status; do not count 104 profile rows as 104 independent biological units. Seeds are computation replicates, not biological replicates. Predeclare multiplicity handling for secondary analyses.

## Failure criteria and limits

Stop scored execution if identity/plate joins are ambiguous, the production leakage guard fails, train/test provenance is incomplete, or all positives vanish after filtering. Report unavailable comparisons without replacing missing positives or weakening filters. If differences vanish under strict structure controls, or fail to beat gene lookup and lexical controls on the paired population, do not claim added biological understanding. A V2 failure on indistinguishable queries is expected information insufficiency, not evidence against an encoder. A target mismatch does not establish lack of biological effect or causal mechanism.

No clinical, causal, broad natural-language microscopy search, batch-generalization or learned-model-superiority claim follows from this audit.

## Required human decisions

- **Makenna:** choose the manuscript's primary scope, supply the accepted RCMLR version/rights information, decide whether to prioritize the narrow existing-data diagnostic or a larger position-diverse cohort, and authorize any future data/compute use and publication.
- **Claire:** approve replicate identity, biological relevance, target/compound alias handling, exposure and control restrictions, anomaly treatment, minimum effective sample size and interpretation of V2. Decide whether 13 reagents are enough for an exploratory primary analysis or require expansion.
- **Adam:** review split/aggregation implementation, source normalization provenance, leakage guard namespace ambiguity and checkpoint/data overlap evidence; confirm technical reproducibility before a real run. This is a proposed technical-review assignment, not an assumption about authority to grant scientific approval.

Highest-value next executable step after design approval: construct and freeze a U2OS CRISPR query/gallery/training plate-rotation manifest from `local_mapping_PRIVATE.csv` and the 13 eligible IDs in `replication_PRIVATE.csv`, verifying positive counts against the full non-control gallery. That manifest should precede any pretrained run. The current audit intentionally does not execute or approve a new scientific benchmark.
