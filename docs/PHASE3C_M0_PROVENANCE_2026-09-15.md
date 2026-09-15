# Phase 3C M0 provenance and evaluability audit

**Status:** provenance and evaluability checks complete; gene-identity contract
under review.

## Verified provenance

- The historical CellCLIP M0 manifest contains 1,079 unique profiles.
- Every saved CellCLIP text-embedding record matched the corresponding
  historical profile/query-text SHA-256; there were no missing, extra, or
  mismatched records.
- MedCPT and BioLORD M0 query inventories were independently reconstructed
  twice from clean historical commit
  `92e031466fe70e46883dddbe521d9b87a723eb5a`.
- Both reconstructions matched each other and the historical CellCLIP M0
  inventory exactly.
- MedCPT and BioLORD are therefore classified as
  `reconstructed_verified`; their original aggregate output directories did
  not retain row-level text.

## Strict benchmark coverage

The strict held-out-plate benchmark contains:

| Quantity | Value |
|---|---:|
| Total queries | 1,079 |
| Evaluable queries | 180 |
| Nonevaluable queries | 899 |
| Query coverage | 16.68% |
| Maximum strict positives per query | 1 |

A correct retrieval is a candidate with the same frozen treatment label as the
query that remains after the configured same-plate and same-well exclusions.

mAP is calculated over the 180 evaluable queries and must be reported together
with coverage over all 1,079 queries.

## Evaluable-subset composition

The evaluable group is structurally more replicated than the nonevaluable
group. In the test split, evaluable queries have four profiles per treatment,
four represented wells, and two represented plates. Nonevaluable queries have
approximately 1.68 profiles/wells and 1.65 plates per treatment on average.

The evaluable group also has longer query text and higher maximum
same-treatment morphology similarity on average. These findings show that the
180-query subset is not exchangeable with the full 1,079-query population.
They do not, by themselves, establish a causal difference in biological
difficulty.

## Open gene-identity review

The historical text contains no literal metadata field names such as
`Metadata_gene`. However, a row-level audit matched the source
`Metadata_gene` value in 959 of 1,079 model-visible query strings:

- 845 long-value matches;
- 114 short or numeric matches.

This result is under review. It may indicate either:

1. an intended gene-aware biological-text condition whose documentation is too
   strong; or
2. a violation of an intended identity-free M0 condition.

The current audit does not classify the matches as harmless or as confirmed
leakage. Public M0 claims should remain qualified until the query-construction
contract is resolved.

## Prompt determinism

The current Phase 3C path uses deterministic text construction and encoder
inference rather than sampled language-model generation. Generation
temperature is therefore not applicable. A future generative prompt path must
pin its model, revision, template, seed, and decoding settings.
