# Phase 5.1 experiment decision packet

2026-10-14. **PROPOSED_NOT_APPROVED.** Related issues:
[#30](https://github.com/siamakenna/perturb-LM/issues/30),
[#52](https://github.com/siamakenna/perturb-LM/issues/52), and
[#31](https://github.com/siamakenna/perturb-LM/issues/31).
No inference, fitting, retrieval scores, profile downloads, or scientific approvals
are produced by this change. This packet does not amend a frozen benchmark.

## Decision proposed

**Primary question:** How does supplied gene identity change apparent exact-reagent
recovery when query and gallery measurements come from different plates and well
coordinates within one matched CPJUMP1 condition?

Start with a plan-only feasibility assessment of the four existing U2OS CRISPR
plates. Keep cohort expansion as a separate decision informed by the
[expansion assessment](PHASE5_1_COHORT_EXPANSION_OPTIONS.md). Select fewer models
only after the information and sample-eligibility questions are resolved.
DINOv2 is an optional reviewer-response/general-vision baseline and is not on the
development path for this experiment.

The proposed primary endpoint is the **paired difference, gene-aware V1 minus
category-only V2, in macro reagent-average AP** on exactly the same evaluable
query records and per-query candidate masks. This is an information-sensitivity
feasibility endpoint. It cannot establish recovery of mechanisms or generalization
to unseen treatments, genes, batches, or laboratories.

## Evidence ledger and cohort boundaries

The supplied Git bundle was verified at audit commit
`0ee3a11d6e27975df79798ff6f67bfba08258074`; its complete history contains both audit
commits and the seven original Phase 5 documents. The separately supplied remote
head record names the same commit. Direct live GitHub verification was unavailable
in this development environment; this is verification of the transferred source,
not a new live remote observation.

| Evidence | Status and permitted use |
| --- | --- |
| 12 selected profile files, 4,524 rows, 904 features, 334 missing treatment labels, 84 absent wells, 1,009 CID discrepancies | Prior completed [cohort audit](PHASE5_CPJUMP1_COHORT_AUDIT.md); original profiles and private row-level outputs were not transferred and these analytics were not rerun here. |
| 156 strictly eligible non-control rows / 13 CRISPR reagent IDs across matched strata | Prior audit eligibility, not an independent sample count or the new rotation denominator. |
| Four U2OS CRISPR plates, reported 104 rows / 13 reagent IDs in the strict subset | Prior [scope draft](PHASE5_SCIENTIFIC_SCOPE_DRAFT.md); must be revalidated against the complete local mapping after training/query/gallery separation. No real 104-row manifest is synthesized. |
| Historical 641 treatment queries: 161 V1 strings; eight V2 strings with 640 queries in collisions | Prior [query audit](PHASE5_QUERY_IDENTIFIABILITY_AUDIT.md); these global counts are not per-rotation denominators. |
| Two JUMP fluorescence sites on BR00117011, five channels each; full and cropped stacks each accepted 2/2 by exploratory pixel QC | Separate operator-supplied preparation summary reviewed 2026-10-14. Technical decoding, checksums and segmentation-path completion only; visual/biological validation is pending. |

BR00117011 is a 48-hour U2OS compound plate outside the frozen 12-plate profile
cohort. Its two sites do not add profile rows, CRISPR replicates or an independent
batch to this design. Full fields and their center crops are paired derivatives
of the same sites. Keep their raw data, previews and masks with the local run.
The previous image-review and DINOv2 staging sequence is optional and does not
block the scientific design work.

The image summary is bound by SHA-256
`a34e2b0c40780cf769ecdf3dff21de81b8aff12369ebba88e6e6213e533a55f0`;
its preparation source is `bbd5aab2c2803623d7e21f6eee7193042ab157dd`.
This privately retained aggregate artifact is not a public raw-image release.

## Candidate plate assignments

The fixed proposed stratum is `2020_11_04_CPJUMP1`, CRISPR, U2OS, Cas9,
144 hours, no antibiotics, relative density 100, Day0, first imaging, WGA flag.
Keep the WGA flag; a successful reader or profile loader does not remove it.

| Alias | Physical plate |
| --- | --- |
| P1 | BR00116996 |
| P2 | BR00116997 |
| P3 | BR00116998 |
| P4 | BR00116999 |

Use exactly one query plate, a different gallery plate, and the remaining two
plates for training. The training pair is unordered. Thus there are exactly
**12 structural candidates**, not 24 independent experiments or 12 approved folds:

| Query | Gallery | Training |
| --- | --- | --- |
| P1 | P2 | P3, P4 |
| P1 | P3 | P2, P4 |
| P1 | P4 | P2, P3 |
| P2 | P1 | P3, P4 |
| P2 | P3 | P1, P4 |
| P2 | P4 | P1, P3 |
| P3 | P1 | P2, P4 |
| P3 | P2 | P1, P4 |
| P3 | P4 | P1, P2 |
| P4 | P1 | P2, P3 |
| P4 | P2 | P1, P3 |
| P4 | P3 | P1, P2 |

Actual row, positive, reagent and gene counts per candidate remain **pending local
metadata validation**. The code enumerates candidates deterministically and checks
them; it does not assume that all 12 survive.

### Eligibility and failure rules

Use the complete Phase 5 `local_mapping_PRIVATE.csv`, not a handpicked table
containing only the 13 recoverable IDs. Verify its provenance against the
unchanged 12-file profile manifest on the data-holding machine first.

1. Preserve batch, physical plate, canonical well coordinate, source row,
   reagent and gene in a scoring-only metadata channel. They are not extra
   predictive fields. Reject ambiguous identity or duplicate physical well records.
2. Select the four stated plates and complete, matched acquisition/culture
   conditions. Record rows outside the stratum and all exclusion reasons.
3. Exclude controls and missing treatment labels from the non-control endpoint,
   retaining their counts and separate QC roles. Ambiguous or contradictory
   selected mappings stop planning for correction; they are not silently dropped.
4. Use **all** eligible labeled non-control gallery rows on the gallery plate,
   including treatments lacking strict positives. Do not shrink the gallery to
   the 13 recoverable IDs.
5. For each query, remove candidates at the same well coordinate before finding
   positives. Query and gallery physical plates must differ. A positive has the
   same exact reagent ID; sharing a gene does not make it an Endpoint A positive.
6. A seen-treatment query must have its reagent represented in the training
   population. Report unsupported queries separately. Record treatment and gene
   overlap between roles as intentional exposure for this estimand, never as
   evidence of unseen-target generalization.
7. Keep queries with zero remaining positives in the eligibility ledger and
   denominator; they have undefined AP and are not silently scored as zero or
   removed from coverage reporting.
8. Require usable non-control rows on both assigned training plates and explicitly
   chosen minimum training and evaluable reagent-group counts.
   Missing thresholds, insufficient groups and no-positive rotations cannot
   become executable designs. Numerical thresholds are review decisions, not
   defaults inferred from sample availability or claimed power calculations.

The planner supports the stated seen-treatment design. Treatment-disjoint and
gene-disjoint alternatives require an explicit group assignment and a separate
review; requesting them does not silently reuse the seen-treatment folds. They
are blocked here, not claimed impossible in all expanded designs.

## Query policy, model role and leakage

| Condition | Role in the proposed experiment |
| --- | --- |
| `M0_GENE_AWARE_V1` | Historical gene-aware renderer, clearly labeled. Pair with an explicit gene-lookup control. Multiple guides for one gene can remain text-identical. |
| `M0_IDENTITY_FREE_V2` | Proposed deliberately weak category control. Ordinary non-control treatment strings lack treatment-specific content; identical strings cannot supply treatment-specific rankings under otherwise identical settings. |
| M1 / functional or phenotypic descriptions | Deferred: require independent source provenance, approved allowed fields/relevance, annotation-overlap review and fresh collision/identifier audit. |

The `F10` gene/well namespace collision remains an unresolved production-guard
finding. Neither this planner nor its tests relax the guard. Before scoring,
rerun the unchanged identifier audit using the complete relevant identifier
universe and report paired query eligibility after guard checks. A failed guard
blocks affected encoding; a design-only plan does not approve an exception or
silently define a new query population.

For a future approved run, start with the existing lexical/profile machinery and
random, shuffled and gene-lookup controls. A train-only TF-IDF-to-profile ridge
alignment is a candidate information-sensitivity implementation, not a direct
cosine comparison between incompatible text and morphology coordinates. Fix all
settings without held-out score tuning; any tuning must stay inside training
plates and adds a separate feasibility requirement. One biomedical comparator
(MedCPT) is conditional on a scientific need after the controls. No new encoder
is needed to establish that category-identical inputs lack within-category
information.

The proposed seen-treatment feasibility endpoint intentionally differs from
criterion 5 in [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md), which requires
unseen training labels for a generalization success claim. This packet grants no
exception to that criterion and does not replace the historical protocol.

### Upstream normalization is an independent limitation

The input selection is already `normalized_feature_select_negcon_batch`.
Treat fit scope as unresolved unless provenance establishes which source records
entered normalization and feature selection. A newly fit training-only scaler
does not undo held-out information in upstream transformations.

Unknown scope blocks an inductive interpretation. Known batch-global fitting
supports, at most, a separately reviewed transductive feasibility interpretation.
A claim of train-only preprocessing needs suitable less-processed inputs and
verified fit populations. The planner records scope and limitations; setting a
scope label is not an approval. Every generated artifact remains
`PROPOSED_NOT_APPROVED` and cannot launch a model.

## Endpoint, denominators and uncertainty

**Primary:** paired V1-minus-V2 macro reagent AP under the strict plate-and-well
filter. Preserve the existing M0 treatment-gallery rule
`mean_scores_after_filtering`: apply each query's plate/well mask to individual
gallery profiles, then average surviving profile scores by reagent ID. Do not
create a gallery centroid before the query-specific mask. Rank the resulting
treatment candidates. Exact-reagent relevance gives one positive treatment, so
AP equals its reciprocal rank for an evaluable query. A missing positive is
undefined AP, not zero.

Average paired query-row AP differences within each query reagent and rotation,
average eligible rotations equally within each reagent, then average reagents
equally. Report rotation support per reagent and a sensitivity restricted to
common rotation support. If that support is empty, report the sensitivity
unavailable and its coverage; do not relax eligibility. This proposed query
weighting and cohort do not replace historical frozen mAP or make the scores
directly comparable. Treatment-gallery aggregation is preserved; the new
estimand still requires scientific approval. No scores are computed by the planner.

Use identical eligible rows, candidate masks, preprocessing/fitting rules and
tie handling between V1 and V2. A candidate mask is fixed *between methods for
one query*; different query wells can legitimately have different masks. Exact
score ties must not be broken using biological labels; prespecify a stable,
label-independent order and inspect tie sensitivity. Identical V2 inputs repeat
the same ranking under identical candidate sets and settings; they do not
necessarily give tied scores to different morphology candidates. Different masks
can change those rankings without adding query information.

**Secondary 1:** plate/well structure sensitivity: compare same-position-allowed
and strict-position-filtered designs, report coverage separately, and compare
paired scores only on their common evaluable population.

**Secondary 2, conditional:** curated compound–gene relationship recovery. It is
deferred unless independent relevance annotations and an adequate cohort are
approved; no morphology-positive labels are manufactured from shared targets.
Principal target and `target_list` are separate evidence sources with documented
disagreement. Preserve multi-target compounds, guide identity and annotation
ambiguity; knockout, inhibition and overexpression are different interventions.
The local compound/CRISPR comparison is 24 versus 144 hours and parental versus
Cas9, so it cannot establish time-matched phenocopy or causal mechanism.

| Reported denominator or unit | Required interpretation |
| --- | --- |
| Input rows, stratum rows, role rows, exclusions, query rows before filtering | Account for every row; controls and missing/unresolved labels remain visible. |
| Evaluable query rows and reagent IDs, per-query eligible candidates and positives | Recomputed after every mask and training-support rule; no reuse of the global 641-query count or the unseparated 104 rows. |
| Unique gallery rows versus summed query-candidate pairs | Distinct counts; a candidate reused for many queries is not a new observation. |
| Reagent IDs and mapped genes | Reagent is the endpoint weighting unit. Report distinct genes separately; unknown gene mapping is not counted as a new gene. |
| Four physical plates and repeated rotations | Plate sensitivity, not 12 independent validation experiments. Culture independence remains unresolved. |

Propose paired cluster resampling at the gene level when multiple reagent IDs
share a gene, keeping all their rows and rotations together; if each reagent maps
uniquely to a distinct gene this reduces to reagent clustering. Resolve ambiguous
or missing group maps before attaching an interval. Report a reagent-cluster
sensitivity if biologically justified. This uncertainty describes the small
observed cohort, not a population of independent batches. Report diagnostics by
query-plate and gallery-plate role. Every rotation uses all four plates, so a
leave-one-plate-out analysis would change the two-training/one-query/one-gallery
design and would require separate review. Four plates cannot supply precise
population-level plate uncertainty. Seeds and image sites are not additional
biological units.

Minimum meaningful independent groups, the exact interval procedure and the
common-support rule remain decisions for review. Even 13 surviving reagents would
support feasibility language only. Coverage, collision counts, nulls and
Hit/Recall summaries are supporting diagnostics, not additional primary endpoints.

## Proposed figures and publication scope

1. Cohort flow: source versus local inventory, modality/condition balance,
   anomalies, missing labels and eligibility losses; distinguish prior audit
   findings from newly computed rotation counts.
2. Query information: V1/V2 text-collision structure, guard findings and the
   gene-identity lookup path. No embeddings are necessary for this figure.
3. Plate/well design sensitivity: all 12 candidate rotations, exclusions,
   positive counts and independent-group counts; future approved paired endpoint
   with clustered uncertainty and common-support coverage.
4. Optional target-relation panel only after curated labels and scope approval;
   include target-list disagreement and exposure/modality limitations.

Retain the [Phase 5 publication strategy](PHASE5_PUBLICATION_STRATEGY.md) as a
review draft. Verify accepted RCMLR rights, overlap and extension plans before
submission. Publishing a development branch/draft PR does not approve manuscript
publication, a revised query contract or a scientific experiment.

Historical comparator documents report genuine BiomedBERT, MedCPT, BioLORD and
CellCLIP results, while the generic claims ladder retains pending-result wording.
Preserve both source records; a human-reviewed provenance reconciliation is still
needed. Do not claim all pretrained work is unrun, or that historical results
validate this new endpoint. No Phase 5.1 inference has run.

## What happens next

Use the [reviewer checklist](PHASE5_1_REVIEWER_CHECKLIST.md) for decisions and the
[plan-only CLI instructions](PHASE5_1_VALIDATION.md) for metadata feasibility.
Its input is the previously audited
private mapping, with explicit minimum group counts and normalization scope.
Run it on the original data-holding machine after confirming the unchanged
profile manifest; keep all row-level plans under ignored `outputs/phase5_1/`.

The highest-value next scientific step is to measure per-rotation eligibility
from those real metadata rows and review the effective reagent/gene units with
Claire and Adam. That determines whether to keep the narrow feasibility study or
approve the specific expansion. It precedes any scored or pretrained experiment.
