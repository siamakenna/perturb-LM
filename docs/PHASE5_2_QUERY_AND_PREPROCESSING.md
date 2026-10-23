# Phase 5.2 query information and preprocessing

2026-10-14. **PROPOSED_NOT_APPROVED.** Related issues: [#30](https://github.com/siamakenna/perturb-LM/issues/30), [#52](https://github.com/siamakenna/perturb-LM/issues/52). Companion to the [Phase 5.2 scientific plan](PHASE5_2_SCIENTIFIC_DEVELOPMENT.md). Preserve [CLAIMS_LADDER](CLAIMS_LADDER.md), [EVALUATION_PROTOCOL](EVALUATION_PROTOCOL.md), [Phase 3C](PHASE3C_TEXT_PROFILE_ALIGNMENT.md), and the [Phase 5.1 decision packet](PHASE5_1_EXPERIMENT_DECISION_PACKET.md).

The supplied source and documents were inspected. Main commit `c0518710d38adb17a21e150db45b0388a503b030` is user-reported; this document does not claim a fresh authenticated GitHub verification. Private data and actual per-rotation eligibility were unavailable. No fitting, encoding, biological annotation curation, or scoring was performed for this review.

## Scientific decision

Keep V1 versus V2 as limited information-sensitivity feasibility. V1 supplies gene identity; V2 supplies category information. Their difference cannot establish biological mechanism retrieval. Develop a new description-based endpoint only after position-diverse measurements, interpretable biological units, independent annotation evidence, and preprocessing provenance support it. More encoders do not resolve those requirements.

| Question | Positive relationship | Permitted interpretation |
|---|---|---|
| Exact reagent | Same stable reagent after distinct plate/well filters | Reagent recovery under stated experimental conditions |
| Same gene, different guide | Distinct verified reagents for the same gene | Cross-guide phenotype consistency; not unseen-gene transfer |
| Functional relationship | Different genes connected by independently adjudicated function/reaction/complex evidence | Recovery of the specified relationship; not mechanism discovery |
| Compound–gene | Independently supported target/action relationship | Annotated relationship recovery; not proof of morphological phenocopy |

Each row needs its own relevance contract. Shared pathway is not exact treatment; shared target is not measured phenotype similarity. Knockout, inhibition, activation, and overexpression are different interventions. Current 24-hour compound and 144-hour CRISPR data do not identify a time-matched comparison.

## Conditional query identifiability

V1 intentionally allows `Metadata_gene`. Multiple guides may share its string, and seen-gene training can learn a gene-to-profile association. V2's prior eight unique strings across 641 historical treatment identities are global audit counts, not current rotation counts. Ordinary `trt` text does not even specify perturbation modality. V2 is a useful category control, not a discriminative biological-description benchmark.

Identical text produces identical representations under identical deterministic inference settings. Identical **rankings** additionally require the same fitted model, gallery identities/representations, candidate mask, score aggregation and tie rule. Different well masks or fitted rotations can change rankings without adding query information. Identical query vectors need not assign equal scores to all gallery profiles.

Before new encoding, group queries by:

```text
policy/version + exact rendered text + fitted-state identity
+ gallery identity/representation hash + candidate-mask hash
+ scoring/aggregation settings + tie rule
```

Report rows, reagents, validated gene groups, zero-positive rows and missing mappings for each conditional class. Keep text-only collision counts separately. A query ID or well must not be appended to encoder text to manufacture uniqueness. Include all eligible non-control gallery rows, including nonrecoverable reagents.

For a class of N evaluable queries with the same gallery/mask and one exact positive identity per query, let n_j count queries whose positive is candidate j. Any common ranking has top-1 fraction at most `max(n_j)/N`; its retrospective best mean reciprocal rank is `sum_j n_(j)/j / N`, sorting counts descending. These label-informed bounds are descriptive, not deployable scores. Different weights, multiple positives or varying candidate sets require different calculations. The eight-string count alone supplies no universal mAP ceiling.

For an approved sensitivity experiment, compare V1/V2 on identical paired rows and masks with the existing random/shuffled controls and existing exact-gene lookup. Lookup uses gallery identities and is an identity-exposure control, not morphology inference. A train-only gene one-hot/prototype predictor is a useful proposed check for label memorization before adding biomedical encoders. Label-independent tie handling and common-support coverage remain required. V1 improvement alone cannot isolate pretrained biomedical knowledge.

## A defensible description condition

Use a new versioned query/relevance contract; do not relabel M0 or alter its frozen results. Initially construct short deterministic templates from approved functional assertions. LLM-generated prose adds unreviewed assertions and provenance questions without solving identification. Symbol removal should be called **symbol redaction**, not identity freedom: synonyms, rare functions, complexes, enzyme names and disease labels can identify a gene.

Proposed annotation schema, with lists preserved rather than flattened:

```text
annotation_id, entity_namespace, entity_id, canonical_gene_id, taxon_id,
source_database, source_release, source_url, record_version, retrieval_date,
source_record_sha256, assertion_text, assertion_kind, relation, qualifier,
ontology_id, ontology_release, evidence_code, evidence_species,
reference_ids[], with_from_ids[], transferred_from[],
supports_query, supports_relevance, derived_from_jump,
review_status, reviewer_role, decision_reason
```

Proposed query audit schema:

```text
query_key, policy_name, policy_version, input_annotation_ids[],
template_version, rendered_text_sha256, redaction_policy_version,
identifier_universe_sha256, redacted_spans[], remaining_alias_findings[],
text_collision_group, conditional_equivalence_group, approval_status
```

Keep provenance/identifiers separate from encoder input. Source quotations and private joins stay local. A nonempty provenance string is insufficient.

| Source | Proposed use | Required audit |
|---|---|---|
| UniProtKB reviewed records | Function/localization query assertions | Assertion-level ECO and references; reviewed records can contain curated computational or transferred assertions [S1] |
| GO | Structured function/context and separately specified relation evidence | Evidence, qualifiers, relations, aspect, With/From, references, extensions and release [S2–S4] |
| Reactome | Reaction/complex/pathway relationship evidence | Relevant granularity, primary references, human evidence versus inference from another species [S5] |

GO evidence codes describe evidential origin, not a universal confidence hierarchy. Its guidance recommends inclusion of valid codes and flags RCA retirement. A direct-experimental subset can be an explicitly narrower sensitivity, not a blanket superior gold standard. ND does not supply a specific positive function; NOT cannot become a positive. Missing annotation means unknown, not negative. Preserve obsolete-term, taxon, relation and conflict handling. [S2–S4]

Different databases do not guarantee independent evidence. UniProt, GO and Reactome can share publications or imported assertions. Audit provenance down to supporting experiments, not URLs alone. Exclude evaluation relevance derived from the same JUMP morphology measurements. Flag overlap in publications, transfer ancestry, ontology assertions, and query terms that directly reveal the scoring relationship. Freeze annotations and selection rules before viewing ranks.

A practical strongest candidate uses independently evidenced descriptions and relations, with Claire adjudicating relevance while blinded to scores. If independence cannot be established, describe **annotation-consistency retrieval**. If a query repeats the GO term defining positive membership, the experiment measures annotation-informed retrieval, not independent biological discovery. Gene descriptions paired with exact-reagent labels instead measure description-to-reagent recovery. Neither should be presented as a new biological relation without additional evidence.

Pretraining exposure to public gene-function literature is distinct from exposure to the paired morphology evaluation set. A pretrained encoder knowing gene function is expected background knowledge; reuse of evaluation images, profiles or pairs creates another contamination question. Record both where knowable. A publication-date cutoff cannot prove absence from undocumented model training, and symbol redaction cannot remove memorized functional identity.

## Split choices depend on the claim

- Seen reagent/gene with new plate/well: acquisition stability and information sensitivity.
- Held-out reagent, seen gene: cross-guide transfer, after guide identity and quality review.
- Held-out gene: all guides/aliases for a gene grouped together; no test-gene morphology in alignment training. Gallery profiles may belong to test genes because they are retrieval targets, not training examples.
- Held-out family/pathway: optional stronger transfer stress test; overlapping pathways require explicit grouping/connected components and size reporting. Do not call overlapping groups disjoint.
- Held-out compound scaffold/target: future alternative requiring verified chemical and action mappings; ID disjointness alone does not exclude related compounds or shared targets.

Actual feasibility is unknown for the current 13 reagents. No automatic cutoff or approved experiment follows from this table.

## Preprocessing provenance and intended deployment

The audited kind `normalized_feature_select_negcon_batch` indicates preprocessing already occurred. Its name does not prove the fitted population. A fresh train-only scaler cannot undo earlier global normalization or feature selection.

Public source inspection provides a concrete risk to investigate: the fetched CPJUMP1 `main` runner invokes a combined-modality configuration enabling batch-level feature selection. That configuration includes the four U2OS CRISPR plates and other plates. The profiling submodule linked from that fetched tree, revision `342789895ec349a16ed38ccee1d6385e89063029`, concatenates configured plate frames, passes the combined frame to feature selection, then writes separate batch-suffixed plate outputs. Its negative-control normalization is a distinct per-plate operation. [S6–S8] Thus negative-control normalization does not imply control-only feature selection. This is evidence about a public processing recipe: the connection to the audit's pinned source revision `56845c7d4dc322652952783d91dae0ffef47829f` and to the user's local output bytes remains unverified. Do not relabel local upstream scope as verified solely from this code inspection.

Record every stage: assay/segmentation, site aggregation, control normalization, feature selection, imputation, scaling, dimensionality reduction or batch correction, vocabulary/IDF, alignment, tuning. Minimal stage ledger:

```text
stage_id, parent_hashes[], output_sha256, software_commit, config_sha256,
operation, statistic_or_parameter, fit_population_kind, fit_record_set_sha256,
fit_plates[], fit_batches[], fit_control_rule, uses_treatment_labels,
heldout_treatment_rows_accessed, heldout_control_rows_accessed,
information_available_at_prediction_time, deployment_claim,
evidence_artifact, provenance_status, reviewer_decision
```

Scope labels include `fixed_external`, `train_only`, `heldout_controls_only`, `source_batch_all_rows`, `source_batch_controls_only`, `per_plate_all_rows`, and `unknown`. Labels describe evidence; they do not authorize execution.

Choose one primary regime supported by provenance:

1. **Strict inductive:** compatible less-processed measurements; data-dependent selection/fitting uses training plates only. Apply frozen transforms to test plates and report drift. Assay processing such as illumination correction needs an explicit protocol, not automatic classification as model leakage.
2. **Prospective plate-calibrated:** a prespecified set of new-plate controls is available at deployment and fits a defined calibration. This can be valid but is not “no held-out data access.” Specify control scarcity and failure rules.
3. **Transductive feasibility:** known source-global fitting supports a separately reviewed transductive interpretation. Unknown fit scope does not establish a fully characterized transductive protocol and blocks inductive claims.

Do not create extra primary endpoints merely by running all three. Verify source processing scripts/submodule/configuration, parent profile hashes, output hashes and fit populations on the data-holding machine. Script instructions alone are not proof they generated the local bytes. If provenance is missing, keep that uncertainty explicit.

Equal feature count is not compatibility: compare ordered names, units, aggregation, segmentation, stain/channel definitions, missingness and processing version. Schema-only alignment using held-out column names must be distinguished from selecting features using held-out values. Before encoders, examine control behavior, plate/row/column structure, morphology-only repeatability, coverage and train/test drift. Plate predictability alone does not prove exploitation; combine it with masked/matched comparisons. WGA annotation does not remove its effect; U2OS-versus-A549 cannot identify a staining effect.

## Implementation priorities and acceptance cases

Existing `QueryPolicyTransformer`, exact-gene control, `MorphologyPreprocessor` and Phase 5.1 planner already cover rendering, identity control, local train fitting and structural rotations. Reuse them. `pipeline.py` correctly blocks provisional M1 on real data; retain that guard. The F10 gene/well collision remains blocked. An audit may explain field provenance without authorizing an exception.

Only implement the following when their outputs directly resolve the next scientific decision:

| Proposed component | Acceptance cases |
|---|---|
| Conditional-equivalence audit | Same text/settings joins; new mask or fitted state separates; query ID alone does not; zero-positive rows retained; tiny synthetic oracle checked by exhaustive ranking |
| Structured annotation audit | Missing release/hash/reference unverified; NOT/ND not positive; cross-database shared PMID flagged; JUMP-derived labels not independent; ambiguous genes unresolved; evidence policy explicit |
| Fit-scope ledger audit | Train-only declaration containing held-out rows fails; test-control calibration separately classified; new scaling never clears upstream unknown/global flag; equal column counts with changed names fail compatibility |
| Typed identifier diagnostic | F10 explained without bypass; any proposed future typed exception must be versioned and reject injected well tokens elsewhere; no global token allowlist |

These are future implementation specifications, not claims that these tests ran. Keep real outputs ignored and local. Approve scientifically necessary behavior before extending production query contracts.

## Decisions and sources

Makenna selects manuscript question and primary experiment; Claire adjudicates biological relevance, intervention compatibility, independent units and annotation evidence; Adam validates lineage, splits, aliases, fit populations and implementation. All scientific decisions remain pending. Review should bind exact source/data/annotation versions. DINOv2 remains optional.

Primary documentation inspected 2026-10-14; no cohort annotation coverage was inferred:

- [S1: UniProt/EMBL-EBI, Data evidence](https://www.ebi.ac.uk/training/online/courses/uniprot-exploring-protein-sequence-and-functional-info/where-does-the-data-come-from/data-evidence/).
- [S2: GO evidence codes](https://geneontology.org/docs/guide-go-evidence-codes/).
- [S3: GO external-resource guidelines](https://geneontology.org/docs/guidelines-external/).
- [S4: GAF 2.2](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/) and [GO annotations](https://www.geneontology.org/docs/go-annotations/).
- [S5: Reactome Details Panel](https://reactome.org/userguide/details-panel).
- [S6: CPJUMP1 README](https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/blob/main/README.md). This fetched moving-branch documentation is not a checksum-bound local-file lineage proof.
- [S7: CPJUMP1 runner](https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/blob/main/run.sh) and [combined feature-selection configuration](https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/blob/main/config_files/config_compounds_crispr_orf_feature_select.yml), fetched moving branch.
- [S8: Profiling submodule processing implementation](https://github.com/jump-cellpainting/profiling-recipe/blob/342789895ec349a16ed38ccee1d6385e89063029/profiles/profile.py) and [wrapper](https://github.com/jump-cellpainting/profiling-recipe/blob/342789895ec349a16ed38ccee1d6385e89063029/profiles/profiling_pipeline.py), pinned submodule revision. Parent audit-revision linkage and local-file lineage remain pending.
