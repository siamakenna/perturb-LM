# Phase 5.2 cross-guide readiness

2026-10-22. **PROPOSED_NOT_APPROVED.** Issues: #30, #52.
This branch publishes metadata evidence and testable design contracts. It does
not run the proposed experiment or amend the frozen benchmark.

## Completed evidence and its provenance

The [aggregate census receipt](evidence/phase5_2/metadata-support-summary.json)
is a sanitized projection of the inspected October 22 report with SHA-256
`bf193358fdb31d06f68fdd7d937310787c7c686829b6f19b54c2251e4f6ba81a`.
That report records all 12 profile hashes, all 11 source hashes and reproduction
of the complete 4,524-row mapping. Its code revision is
`703039dfb11f5ce29c3bdb32b4d9ff568d0de7bf`; its counts reproduce October 20.
In this publication session we checked the receipt digest, the original mapping,
source provenance and CRISPR annotation digests needed for nomenclature matching.
We did **not** repeat the profile census, parse numeric profile features, score
profiles, repeat Batch8/MOA, train or infer.

The four matched U2OS/Cas9 CRISPR plates contain 1,040 noncontrol wells,
247 reagent IDs, 247 sequence strings and 130 source gene strings. Each directed
query/gallery comparison retains 260 queries and the full 260-well gallery.

| Relation | Different coordinate | Different row AND column |
| --- | --- | --- |
| Exact reagent A | 26/260 wells; 13 reagents | 22/260 wells; 11 reagents |
| Provisional different-reagent/sequence, same source string B | 234/260 wells; 117 groups | 180/260 wells; 90 groups |

The 12 overlapping assignments have the same aggregate capacity; query reagent
IDs occur on both designated training plates. Raw and training-supported counts
are separately retained in the receipt, as are no-positive queries, unique units,
conditions and exclusions. Historical 13-reagent/156-row and 104-row inventories
are not these denominators. A and B supported populations are disjoint here.

## Offline HGNC reference resolution

The [reference manifest](evidence/phase5_2/hgnc-reference.json) pins the complete
official approved and withdrawn files by Google Storage generation and SHA-256,
retrieved October 22, with an October 16 modification date. The [HGNC archive
documentation](https://www.genenames.org/download/archive/) defines approved,
previous/alias and withdrawn fields. We downloaded whole public references and
matched locally; no private gene/guide list was submitted to a remote service.
The reference bytes and record-level ledger stay ignored on the original Mac.

Matching preserves source labels and case. An exact approved symbol takes
precedence while retaining historical/alias candidates. A unique previous symbol
can resolve nomenclature; alias-only matches remain candidates, multiple plausible
historical matches remain ambiguous, and withdrawn/merged/split reports are not
automatically followed. No label is split or guessed. The implementation is
`gene_identity.py`; the offline CLI binds its inputs to the preserved receipt and
reference hashes before writing private records.

The [aggregate identity result](evidence/phase5_2/identity-summary.json) records
130 exact approved-symbol matches and 130 HGNC IDs, no automatic merges/splits,
no unmapped/withdrawn entries, and no previous/alias-only assignments. Three exact
symbols also have secondary historical/alias candidates for other HGNC records;
those candidates and original labels are retained privately for intended-target
review. The source-string partition is unchanged, so nomenclature alone changes
none of the reported eligibility counts. This is computational nomenclature
resolution, not 130 independently reviewed biological targets. Guide identity,
historical target intent and study relevance remain unapproved.

## Guide and culture evidence

The pinned [JUMP-Target documentation](https://github.com/jump-cellpainting/JUMP-Target/blob/2da0551610a26548a384537b28d05f6fc72ea33c/README.md#jump-target-crispr)
defines the reagent ID as a GPP sgRNA identifier and the sequence column as sgRNA
sequence. The preserved annotation has six fields: reagent, gene, perturbation
type, control type, target sequence and negative-control type. It has no genome
assembly, chromosome, cut coordinate, strand, transcript or per-guide editing
measurement. We did not send IDs/sequences to GPP or a genome alignment service.
Different valid strings remain evidence of different strings, not independently
verified targeting loci, editing efficacy or off-target absence. Reverse-complement
and clone equivalence require explicit review, not automatic assumptions.

The [original methods, pages 8–9](https://cimini-lab.broadinstitute.org/files/ciminilab/files/three_million_images_and_morphological.pdf)
describe selection using Azimuth 2.0 and CFD predictions, four replicate plates
per primary CRISPR condition, and polyclonal Cas9 cell lines. They link a
CellTiter-Glo infection-efficiency workbook. Its pinned copy was inspected only
for sheet/header structure: the 144-hour Cas9 sheet includes a U2OS-Cas9 block
with plate and clone identifiers. No assay values, clone-to-cohort binding or
editing efficiency were analyzed. Prediction and infection measures do not prove
achieved knockout or independent cultures. Neither the experiment notebook nor
these sources bind independent cell preparations to the four selected barcodes.
Wells/sites, guides and repeated comparisons must not be counted as cultures.

## Artifact-specific preprocessing trace

All inspected public-file URLs, revisions and SHA-256 values are in the
[public-source manifest](evidence/phase5_2/public-source-manifest.json).
The CPJUMP1 source is pinned at
`56845c7d4dc322652952783d91dae0ffef47829f`. Its `run.sh` invokes
`config_crispr.yml`, followed by the combined feature-selection configuration;
`.gitmodules` identifies profiling-recipe, whose gitlink is
`342789895ec349a16ed38ccee1d6385e89063029`.

| Inspected source | Conditional recipe interpretation |
| --- | --- |
| `config_crispr.yml` | 18 CRISPR plates; both whole-plate and negative-control MAD normalization; epsilon 0, inferred features, image features disabled; aggregation and feature selection disabled in this invocation |
| `config_compounds_crispr_orf_feature_select.yml` | All 51 batch plates listed with processing enabled; batch-level variance, correlation, missing-column and blocklist filtering for normalized and negative-control-normalized variants |
| recipe `profiling_pipeline.py:43–50` and `profile.py:169–201` | Pass each plate's augmented table to normalization with `Metadata_control_type == 'negcon'` |
| recipe `profile.py:215–293` | Concatenate the configured batch plates, select features once, then split selected rows back to each plate's `normalized_feature_select_negcon_batch` output |
| recipe `environment.yml` | Pins Pycytominer at `36241269c4293c24484986568ca16b2d7eb9e808` |
| pinned Pycytominer `normalize.py:154–162` | Fit on the queried controls and transform the entire plate |
| pinned Pycytominer `feature_select.py:21–38` | Default samples `all`, Pearson correlation threshold 0.9, missingness cutoff 0.05, frequency cutoff 0.05 and uniqueness cutoff 0.1; recipe does not override those defaults |

Thus, **if this exact recipe produced the local bytes**, normalization uses
within-plate controls and feature selection uses all rows from the 51 configured
plates, including plates assigned held-out roles. This is more specific than
inferring fit scope from a filename. However, no execution receipt binds that
configuration, software environment, feature-selection/blocklist snapshot and
actual fit record IDs to these particular compressed profile hashes. Missing or
changed input files and software execution are not resolved by reading source.
Artifact-specific fit provenance therefore remains unverified; train-only or
inductive preprocessing cannot be certified. We did not execute upstream code,
download less-processed profiles or fit a replacement scaler.

## Proposed experiment and engineering boundary

The [protocol](PHASE5_CROSS_GUIDE_CONCORDANCE_PROTOCOL.md) proposes untrained
morphology-to-morphology concordance, using reviewed same-gene/different-guide
relationships under different physical plates and different row AND column as
primary; coordinate-only is sensitivity, subject to the same identity review.
The full noncontrol gallery stays visible. Exclude same canonical reagent/guide
and equivalent sequences; leave unknown relations unlabeled. Different-gene
references are not validated negatives. Keep zero-positive/reference queries in
coverage. Exact-reagent recovery remains separate.

`cross_guide_design.py` implements metadata relation labels and coverage plus
proposed balanced **weights**, not similarities or a scoring runner. For each
reviewed gene and qualifying unordered guide pair, require both guide directions
in each of 12 ordered plate comparisons. Balance wells within each cell, two
guide directions, two plate orientations, six unordered plate pairs, guide pairs
within gene and genes. Incomplete pairs remain excluded with input/complete
counts; duplicates or contradictory physical anchors fail. No observed effect
or synthetic study-size threshold chooses the population.

The changes to `rotations.py` relative to main only extract the existing well
alias expression into `canonical_wells` and the same ordered query/gallery
permutations with unordered training complement into `plate_roles`. The planner
uses those helpers without changing thresholds, exclusions or eligibility rules.
The census module additionally exposes per-training-plate populations and
both-plate versus union reagent presence; invented tests distinguish them.

No randomization test is executable in this proposal. Globally renaming gene
labels preserves every pair relationship and provides no null distribution.
A future pairing randomization must actually reassign partner relationships,
preserve approved condition/spatial/guide multiplicity constraints, and justify
exchangeability despite repeated wells, related genes and reused references.
Until that contract is approved, report no randomization p-value. The conditional
uncertainty proposal in the protocol also requires human review.

## Publication security follow-up

The first final-head CI inspection reported three high-severity
`py/path-injection` annotations: two in the new manifest-path helper and one at
its shared checksum reader. The manifest helper now normalizes paths with
`os.path.realpath`, checks containment with a directory-boundary prefix, and
returns the checked canonical path before file access. This avoids reopening
an unchecked symlink spelling. Synthetic tests cover valid in-root aliases,
missing files, symlink escapes, sibling-prefix escapes and traversal/absolute
paths. Shared cohort code, CodeQL policy and alerts are not altered. This follows
[CodeQL's path-validation guidance](https://codeql.github.com/codeql-query-help/python/py-path-injection/);
CI, rather than this text, establishes whether its gate clears.

## Remaining decisions

Claire must review intended stable target and canonical guide/locus/orientation,
including the three secondary nomenclature conflicts, efficacy and reference
relationships. Adam must establish or explicitly bound artifact-fit provenance,
physical culture units, dependence, masks, aggregation and any future scorer.
Makenna must approve the estimand, complete-support population, uncertainty and
intended claims against a frozen reviewed ledger/protocol. All execution gates
in the [review checklist](PHASE5_CROSS_GUIDE_REVIEW_CHECKLIST.md) remain active.

The smallest next experiment, after those decisions, is the prespecified
untrained finite-cohort concordance contrast. It tests neither unseen guides
nor unseen genes. The F10 production guard, WGA status and historical results
remain unchanged. Publication and synthetic tests authorize no real scores,
predictive queries, inference, model download, Biowulf workload or deployment.
