# Phase 5.2 local same-gene support specification

2026-10-14. Related issues #30 and #52. **PROPOSED_NOT_APPROVED.**
This is a precise specification for the next private-data assessment, not a
claim that the algorithm below has been implemented or run. The implemented
Phase 5.2 utility audits the separate public compound-layout question.

## Input and scope

Use the complete existing `local_mapping_PRIVATE.csv`, original
`profile_manifest.json`, source `provenance.json` and source annotation tables.
Do not substitute the 13-reagent recoverable subset. Verify unchanged profile
paths, raw-byte hashes, row counts, observed plate IDs and ordered feature schema
against the completed audit before making a new derived mapping. Verify the
source table hashes too. Keep the separate timepoint outside the frozen cohort.

Use the four existing U2OS/Cas9 CRISPR plates specified in Phase 5.1, 144 hours,
no antibiotics, relative density 100, Day0, first imaging and the WGA flag.
Do not pool puromycin or A549 strata to gain support. Each physical well has one
stable record identifier; duplicate acquisition/site records require explicit
upstream reconciliation rather than being treated as additional wells.

Create a reviewed mapping from original reagent ID to guide identity and stable
human gene identifier. A gene symbol string alone is not evidence of a unique
gene, an independent guide or a successful knockout. Retain ambiguous,
multi-target and unavailable mappings, with exclusion reasons. Guide sequences
stay in the private identity-audit channel and never enter predictive text.

## Pair and population rules

For each ordered query/gallery plate choice already enumerated by Phase 5.1:

```text
Q = every non-control, labeled, unambiguously mapped row on query plate
G = every non-control, labeled, unambiguously mapped row on gallery plate
for q in Q:
    candidates = rows of G at a different canonical well coordinate
    exact_reagent = candidates with the same source reagent identity as q
    cross_guide = candidates with:
        same reviewed stable gene as q
        different source reagent identity
        independently verified different guide identity
    record exact_reagent and cross_guide separately
    retain q when either list is empty; absence is not zero AP
```

The two endpoints must not be combined into one positive set. Count after every
filter: rows, distinct reagents, distinct guides, stable genes, physical plates,
coordinates and documented culture preparations. Unknown culture counts remain
unknown. Also report same-row, same-column and edge/interior relations: different
coordinates do not remove all spatial structure. Compare covered and uncovered
genes using prescore metadata; do not infer that uncovered genes lack a phenotype.

Keep a full diagnostic gallery. For a later cross-guide retrieval endpoint,
exclude the query's exact reagent/guide from the entire candidate pool rather
than treating its profile as a negative. Record this extra candidate restriction
and its losses separately. The full-gallery identity diagnostic above and the
scored cross-guide candidate contract are different artifacts.

## Training policies to assess separately

1. **Seen-gene, held-out-guide:** remove the queried guide from fitting records;
   retain permitted alternative guides for the gene only under the declared
   policy. Report which gene and alternative-guide identities remain in training.
   Do not call this unseen-gene generalization. Gene-aware text may support a
   direct training-label association.
2. **Held-out-gene:** assign all guides and aliases for a gene to one fitting
   partition; all test-gene morphology is excluded from fitting and tuning.
   Query and positive gallery measurements still require distinct plates and
   coordinates. Test genes may appear in the retrieval gallery, which is not
   alignment training. Gene-family leakage needs its own stated policy.

Enumerate support before selecting an endpoint. No default minimum group count
or resampling rule is supplied. The existing Phase 5.1 implementation intentionally
does not enable these new policies; do not change its meaning through flags.

## Output specification

Local ignored output should contain a source-bound JSON summary and private
row/pair ledgers. Summary fields should include `status=PROPOSED_NOT_APPROVED`,
`execution_allowed=false`, input/implementation hashes, source revision, selected
stratum, policy, known/unknown provenance, counts at each filter, unique guides
and genes per rotation, reasons for unavailable support, and a distinction
between observed physical plates and documented independent cultures.

Avoid reporting only a single eligible count. Supply an exclusion waterfall and
support matrix with exact-reagent and cross-guide columns. No fitted model,
similarity score, AP, biological label or power estimate belongs in this audit.

## Synthetic acceptance cases for a future implementation

| Case | Required behavior |
|---|---|
| Same gene, different guide and coordinate, matched condition | Cross-guide support only; never exact-reagent support |
| Same reagent repeated on another plate | Exact-reagent support only when coordinate differs |
| Different sample IDs with identical guide sequence/identity | Not independent cross-guide support |
| Same gene and well coordinate on another plate | Excluded by the coordinate restriction |
| Different gene with similar symbol | Not a positive; no fuzzy/name-prefix rescue |
| Missing or multi-gene mapping | Explicit ambiguity; no automatic positive |
| Control, missing label or contradictory condition | Explicit exclusion/conflict without disappearing from totals |
| Repeated acquisition of one physical well | No new biological or plate replicate |
| Held-out guide or gene present in fit membership | Policy fails before scoring |
| Query with no remaining positive | Remains in coverage with an explicit reason |
| Many guides share one gene | Guide counts remain distinct; gene count is one |
| Record order shuffled | Identical sorted ledgers and summaries |

These test cases are not part of the executed test count in this transfer.
After the metadata assessment, Makenna selects the study scope, Claire adjudicates
guide/replicate biology, and Adam validates provenance and fitting partitions.
Any scored experiment then needs a separate versioned relevance and execution decision.
