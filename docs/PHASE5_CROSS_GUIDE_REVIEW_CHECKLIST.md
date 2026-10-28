# Cross-guide diagnostic collaborator decisions

2026-10-20. **PROPOSED_NOT_APPROVED.** Related issues: #30 and #52.
Read the [closeout](PHASE5_GUIDE_SUPPORT_CLOSEOUT.md) and
[protocol](PHASE5_CROSS_GUIDE_CONCORDANCE_PROTOCOL.md). This is a decision packet;
no message was sent, signature supplied or decision recorded on anyone's behalf.

## Evidence to use

- The metadata census, independently checked over 48 assignment/mask/endpoint
  combinations, supports a stricter provisional population of 180 source reagent
  IDs / 180 distinct sequence strings / 90 source gene strings / four plates.
  Across plates there are 720 unique supported physical wells, not 720 independent
  perturbations. Reviewed stable gene and guide identities have not been supplied.
- Every old assignment's query and gallery populations contain 260 noncontrol
  wells and 247 reagents. All query sequences already occur on the other plates.
  Raw gallery capacity is not evidence of an unseen-guide trained evaluation.
- Exact-reagent and provisional cross-guide supported populations are disjoint.
  Keep their denominators separate. Distinct IDs, sequence inequality and a source
  gene label do not establish efficacy, independent cultures or biological truth.
- All four plates share the WGA flag and the recorded 144-hour U2OS/Cas9 CRISPR
  condition. Exact upstream normalization/selection fit scope is unresolved.

## Makenna — manuscript direction and scope

- [ ] Is a profile-only cross-guide concordance diagnostic the next experiment,
  with identity/preprocessing review first, or should the manuscript wait for
  cohort expansion? Record the chosen scope and rationale; no score is authorized
  by the metadata counts alone.
- [ ] Is the manuscript contribution an information/design sensitivity study with
  this diagnostic as biological feasibility evidence? Confirm that an untrained
  diagnostic does not validate natural-language retrieval or a learned model.
- [ ] Accept the proposed primary descriptive contrast and at most two stated
  sensitivities, or specify the change before observing any new scores. Keep
  exact-reagent recovery separate because its supported population differs.
- [ ] Decide whether the observed source cohort can support the intended claim
  after review, or whether a separately authorized expanded/independent cohort
  is required. Data acquisition, inference and Biowulf work require their own
  authorization for this project.
- [ ] Decide whether/when to share the reviewed code and safe aggregate documents.
  No push or PR is assumed. Journal/manuscript publication and any RCMLR revision
  remain separate decisions; existing accepted work is preserved.

## Claire — biological identities, units and references

- [ ] Which independent evidence establishes each intended guide's identity,
  source aliases, sequence equivalence, target locus and intervention compatibility?
  Can at least two reviewed distinct guides be assigned to each retained gene?
  Distinct sequence strings alone do not answer this question.
- [ ] Which stable gene namespace/version, species/assembly and reference evidence
  should resolve source strings and aliases? How will ambiguous/multigene guides,
  shared target sites and source discrepancies be handled without guessing?
- [ ] What do the source culture records establish about independent cell
  preparations? Which unit can support uncertainty: gene clusters, independent
  cultures, or only a conditional finite-cohort description? Distinguish plates,
  guides, wells and imaging sites.
- [ ] Are this WGA-bearing stratum and its CRISPR interventions acceptable for the
  narrow question? Specify any efficacy, cell-health or intervention restrictions
  from independent evidence before morphology is inspected. Unknown efficacy is
  not a confirmed failed intervention, and a similarity score cannot curate it.
- [ ] Are condition- and spatial-matched different-gene reference comparisons
  appropriate? Which known family/pathway/shared-target or intervention exclusions
  should be frozen? Review labels for the full reference gallery, not only the
  candidate anchors. Different genes may be biologically related; they are not
  automatically verified negatives.
- [ ] What minimum meaningful reviewed independent units and uncertainty/precision
  criterion are required? Are complete guide-pair/plate-direction support and the
  proposed conditional interval acceptable? No study minimum is preselected from
  the observed counts or the synthetic 3/2 thresholds.

## Adam — technical provenance, exposure and reproducibility

- [ ] Verify the original profile/source manifest hashes, mapping completeness,
  private identity ledger and post-inspection provenance chain. Check the
  difference between the base census and added overlap/next-step inspection;
  one CLI invocation does not currently produce the entire inspected artifact.
- [ ] Establish exact normalization and feature-selection fit populations,
  versions and parameters for these artifact bytes. If unavailable, is a limited
  conditional/transductive diagnostic technically supportable? If not, identify
  the exact less-processed input needed without acquiring it automatically.
- [ ] Verify shared canonical-well logic, distinct physical plates, different row
  AND different column, and all recorded conditions. Confirm the full base gallery,
  canonical-guide alias exclusions and unknown-relation accounting. Same-row or
  same-column comparisons are excluded by the strict mask, not just A01=A01.
- [ ] Verify gene/guide/well/plate weighting and the six unordered plate-pair
  aggregation. Preserve the 12 directional coverage tables as repeated roles.
  Zero-positive and zero-reference queries remain in the coverage denominator.
- [ ] Confirm the primary diagnostic has no training, tuning, scaler or new
  feature selection. For any later trained model, prove canonical guide/sequence
  closure across split roles; reagent-ID absence is not enough. Specify whether
  stable genes must also be held out for that separate estimand.
- [ ] Review reference reuse and the proposed conditional gene-cluster interval.
  Do not bootstrap individual wells/rotations as independent observations. If the
  assumptions or effective units fail, require an unavailable interval rather
  than a falsely precise result.
- [ ] Check the preserved F10 guard and prevent metadata/guide sequences from
  entering predictive text. Confirm no frozen benchmark, public-site output or
  historical result changes and no output artifacts in the staged Git diff.

## Record the decision before execution

For each item, record: reviewer, date, protocol revision/commit, decision,
evidence reference, private manifest digest where applicable, conditions and
remaining limitations. An unchecked box is unresolved, not tacit approval.
An approved design, authorization for data/compute, scientific execution and
publication are distinct decisions. No real scoring is authorized in this packet.

PR77/83 security remediation has a separate review path. Their failing CodeQL
gates must not be dismissed or bypassed to advance this metadata contribution;
passing local synthetic tests does not clear them. No collaborator is contacted
by creating this checklist.
