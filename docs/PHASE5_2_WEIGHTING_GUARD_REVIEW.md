# Phase 5.2 physical-well weighting guard (#30, #52)

26 October 2026. Software correction for the proposed, unscored cross-guide
design. This record approves no scientific experiment or data transfer.

## Reproduced source defect

Independent review of the supplied PR84 source checkpoint
`e470bec0bd8a934bc5de2a7ba3766c20e0797779` found that
`balanced_comparison_weights()` used the original well spelling in its duplicate
and physical-anchor checks. The relation and coverage helpers already use
canonical physical-well coordinates.

An invented complete four-plate/two-guide design yielded 24 weighted rows.
Appending its existing `A01` anchor under the equivalent spelling `a1` silently
yielded 25 rows instead of rejecting the duplicate. This is a synthetic defect
reproduction, not a cohort measurement. Duplicate spellings can inflate the
reported anchor inventory and distort relative well contributions when a
comparison cell contains other wells.

The reviewed module's before-change SHA-256 was
`bd813066d643281bcfd1788aa98e649aca29372973ad6c9444cb2c2489908b1c`.
The Mac application helper compares the current GitHub target files against the
reviewed before/after hashes before applying this patch. A changed live source
requires fresh review rather than an unchecked application.

## Correction and regression scope

The correction canonicalizes and validates each physical well before duplicate,
anchor-identity and comparison-cell bookkeeping. Equivalent coordinates have
one canonical representation. Alias-based duplicates and contradictory physical
identities fail before weights are returned. Invalid physical coordinates fail
rather than becoming apparent well observations. Input records remain unchanged.

Tests use valid invented 384-well coordinates and exercise well aliases,
contradictory aliases, invalid positions, canonical output, input order and
existing equal-weight/completeness behavior. The weighting formula, plate and
guide directions, complete-support requirements and intended scientific
population are unchanged. The F10 guard, benchmark definitions and all historical
results are unchanged.

The transfer kit records the validation actually executed in the review runtime.
That runtime lacks pytest, so it does not claim a full pytest run. The Mac helper
requires the real focused pytest suites and public-copy check to pass before a
non-force push. New-head GitHub CI remains a separate observation after publication.

## Scientific interpretation remains pending

This change handles physical metadata identity. It does not validate a guide,
target, biological relationship, independent culture or preprocessing fit scope.
No private input was used, and no profile concordance, retrieval, model training,
pretrained inference, census, HGNC preparation, Batch8 or MOA analysis was rerun.
The helper retains `execution_allowed=False`.

The next scientific decisions remain those in
[the review checklist](PHASE5_CROSS_GUIDE_REVIEW_CHECKLIST.md) and
[the proposed concordance protocol](PHASE5_CROSS_GUIDE_CONCORDANCE_PROTOCOL.md):

- Claire: intended guide/target identities, acceptable relationships and
  independent biological units.
- Adam: artifact-specific preprocessing provenance, split exposure, gallery
  integrity and the proposed weighting/scorer contract.
- Makenna: experiment scope, estimand, uncertainty and written execution approval.

The smallest proposed next experiment remains an untrained profile-only
cross-guide diagnostic after those decisions. Source-Mac checksum verification
does not establish recipient-side verification on Biowulf. Scientific approval,
institutional compute permission and any private-data staging remain separate.
