# Phase 5.1 reviewer checklist

2026-10-14. **PROPOSED_NOT_APPROVED.** Related issues: [#30](https://github.com/siamakenna/perturb-LM/issues/30), [#52](https://github.com/siamakenna/perturb-LM/issues/52), [#31](https://github.com/siamakenna/perturb-LM/issues/31).

Review the [decision packet](PHASE5_1_EXPERIMENT_DECISION_PACKET.md) and
[expansion options](PHASE5_1_COHORT_EXPANSION_OPTIONS.md) against the seven
Phase 5 scientific documents at audit commit
`0ee3a11d6e27975df79798ff6f67bfba08258074`. This checklist assigns proposed
review topics; it records no approval and sends no review request.

## Evidence to distinguish before deciding

| Evidence | What it establishes | What remains unresolved |
| --- | --- | --- |
| Committed Phase 5 audit | Reports 12 local plates, 4,524 profiles, 904 features and one original batch; documents position and query-information limitations | Private profiles and row-level audit outputs are absent from this checkout; these local counts have not been recomputed here |
| Prior four-plate U2OS CRISPR finding | Reports 13 eligible non-control reagent IDs and 104 rows before separate training/query/gallery rotations | Exact per-rotation positive counts, genes, usable training groups and retained population require the actual local mapping |
| Synthetic planning fixtures and tests | Exercise deterministic splitting, exclusions and blocking logic | They neither reproduce a 104-row cohort nor establish biological performance, power or independent replication |
| User-supplied two-site image preparation summary | Reports ten original channel TIFFs, full and cropped stacks, unchanged raw inputs and two technically accepted sites in each variant | No visual mask review, independent biological labels or connection to the 12-plate profile cohort is established; full/crop variants are the same two sites |

The two image sites are from plate `BR00117011`, outside the audited 12-plate
profile inventory. Keep this optional technical evidence separate. It does not
add profile rows, independent replicates or a validation endpoint. DINOv2 stays
optional and off the Phase 5.1 critical path.

## Makenna: scope, query information and dissemination

- [ ] Choose the narrow, explicitly exploratory query-information feasibility
  study or require cohort expansion before a primary scored experiment. A
  13-reagent subset does not support a broad generalization claim.
- [ ] Approve one primary question and the paired gene-aware-minus-category-only
  macro reagent AP endpoint with identical candidate eligibility between query
  conditions. Confirm the aggregation and exclusion ledger in the decision packet;
  retain no more than two secondary scientific analyses.
- [ ] Confirm `M0_GENE_AWARE_V1` remains gene-aware and historical results retain
  their original names and denominators. Decide whether `M0_IDENTITY_FREE_V2`
  is acceptable as a weak category control. Do not describe its identical category
  strings as informative treatment-specific biological queries. M1/M5 remain
  proposed; no renderer or relevance-contract change is approved here.
- [ ] Confirm publication direction and the level of independent evidence needed.
  Supply the accepted RCMLR version and applicable rights/archival terms before a
  related-work overlap statement or journal submission. Preserve the camera-ready.
- [ ] Separately decide whether to publish the design after review. The user's
  requested development-branch push and draft PR are authorized source sharing;
  they do not approve scientific execution, main-branch merge or manuscript claims.

## Claire: biology, replication and meaningful units

- [ ] Establish whether repeated reagents on different plates arose from
  independent culture preparations. Define the biological replicate unit using
  source records; plate, well, site, crop and analysis seed are not interchangeable
  independent units. Record unknown culture lineage and perturbation efficacy.
- [ ] Review all four U2OS CRISPR plates' WGA flags and their shared 144-hour,
  Cas9 and culture conditions. Decide whether this anomaly-bearing stratum is
  acceptable for a feasibility study, warrants a prespecified restriction, or
  requires expansion; do not choose exclusions after inspecting retrieval scores.
- [ ] Approve non-control primary eligibility, negative/positive control roles,
  condition matching and missing-label handling. The audited 652 eligible rows
  include 496 controls; pooled controls must not inflate biological recovery.
- [ ] Specify a minimum meaningful number of independent reagents/genes and a
  precision or feasibility criterion before scoring. Inspect per-rotation losses
  and the identity of retained versus unevaluable groups; 104 rows are not 104
  biological replicates, and a software minimum is not a power calculation.
- [ ] If the optional target-relation analysis proceeds, curate principal targets
  and expanded target lists separately, including disagreements, multi-target
  compounds and guide identities. Shared annotation is not a phenocopy label.
  Review knockout versus inhibition, direction of action, 24-hour compound versus
  144-hour CRISPR exposure and parental versus Cas9 confounding. Local ORF data
  remain absent; source inventory alone does not supply them.
- [ ] Approve an independent biological or blinded visual validation plan only
  after exact image/profile mappings and independent labels are available. The
  completed two-site technical processing is not that validation.

## Adam: estimand, split implementation and provenance

- [ ] Validate the actual local row mapping and checksums before constructing a
  real manifest. Enumerate ordered query/gallery plates with the remaining plates
  reserved for training, then inspect each assignment's exclusions and blocking
  reasons. Mathematical permutations are not evidence that every split is valid.
- [ ] Verify different physical plates and different well coordinates for each
  query-positive pair; apply these masks before replicate score aggregation.
  Include all eligible non-control gallery reagents in the chosen condition, not
  only the historically recoverable 13. Require identical masks, candidates and
  tie policy for the paired V1/V2 comparison.
- [ ] Inspect treatment and gene overlap with training for every rotation.
  Explicitly label seen-treatment transfer, and block any unseen-treatment or
  unseen-gene design that violates its exclusions or lacks training groups or
  positives. Seen-treatment feasibility does not meet the historical protocol's
  unseen-label generalization criterion or amend that protocol.
- [ ] Resolve source normalization and feature-selection fit scope. Train-only
  vocabulary/scaling/alignment cannot reverse prior use of held-out profiles.
  Approve a limited transductive interpretation or obtain suitable upstream
  inputs before any inductive claim. Do not infer independent batches from
  different directories or repeated acquisitions.
- [ ] Keep the production identifier guard unchanged. The prior audit's `F10`
  gene/well namespace collision and 23 blocked records remain a real execution
  gate; pre-guard render counts are not encoding permission. Any typed exception
  or exclusion policy requires separate issue review and paired denominators.
- [ ] Review all queried/evaluable/excluded counts, positive rows and positive
  reagent counts, training and gallery sizes, distinct genes, unique reagents and
  plate coverage by rotation. Distinguish row-weighted diagnostics from macro
  reagent AP and keep the same paired support across query conditions.
- [ ] Review paired gene-cluster uncertainty when reagents share genes, otherwise
  reagent clusters; resolve missing or ambiguous mappings before attaching an
  interval. Review a reagent-cluster sensitivity if justified. Preserve each group's
  repeated wells/rotations during resampling. Report query-/gallery-role diagnostics; four
  plates do not justify a precise population-level plate interval. Do not treat
  rotations, seeds, pair counts or duplicate texts as independent replicates.
- [ ] Confirm tests exercise synthetic and failure cases, private outputs remain
  Git-ignored, and no inference, model fitting, retrieval scoring or Slurm launch
  occurs in the plan generator. Record fresh validation separately from prior
  audit test counts and preserve historical reference checksums.

## Shared claim and execution decision

The [comparator review](PHASE5_COMPARATOR_SELECTION.md) records completed
historical BiomedBERT, MedCPT, BioLORD and CellCLIP strict M0 evidence, while older
public summaries retain learned-result-pending language. Reconcile source
versions, populations, query policies and approved wording before publication.
Do not assert that every comparator is unrun or promote historical runs to a new
Phase 5.1 result. The 641-treatment lexical reference, 1,079/180 historical strict
comparator population and present strict-replication feasibility population are
different denominators. Preserve their frozen outputs.

Record decisions with reviewer, date, exact design revision, scope, conditions
and unresolved items in the review issue/PR. No signatures or approvals are
prefilled. Plan-only review, permission to acquire additional data, permission to
run a scored experiment/pretrained inference, and permission to publish claims
are separate decisions. Until required reviews and a source-bound execution
proposal are recorded, status remains **PROPOSED_NOT_APPROVED**.
