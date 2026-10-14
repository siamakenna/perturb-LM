# Phase 5 query identifiability audit

2026-10-14; [#52](https://github.com/siamakenna/perturb-LM/issues/52), [#30](https://github.com/siamakenna/perturb-LM/issues/30). Completed read-only text audit, not a new retrieval experiment. Neither relevance contract nor historical reference was changed.

## What was counted

`scripts/audit_phase5_queries.py` uses the existing `QueryPolicyTransformer` renderer. Repeated allowed-field signatures are rendered once and expanded back to all records. Rendering-only counts precede the full identifier guard; they do not authorize blocked queries for encoding. A batched literal/Unicode/token-boundary scan retains every supplied identifier value; suspected matches are checked using the unchanged production `audit_text`. Fixture tests compare the scan with production behavior.

Both the full QC population and labeled subset are reported. The historical builder separately generates one query per treatment using the first record. Its output agrees exactly with the first-record-per-treatment V1 text; all local treatments have a single rendering, so record ordering does not alter this result. The historical 641 count is not the V2 record-level query count or a held-out-split denominator.

| Population / condition | Queries | Unique strings | Collision groups | Queries in collisions |
| --- | ---: | ---: | ---: | ---: |
| Historical treatment-level gene-aware | 641 | 161 | 161 | 641 (100%) |
| V1, all QC records | 4,524 | 162 | 161 | 4,496 (99.38%) |
| V1, labeled records | 4,190 | 161 | 161 | 4,190 (100%) |
| V2, all QC records | 4,524 | 10 | 7 | 4,176 (92.31%) |
| V2, labeled records | 4,190 | 8 | 7 | 4,176 (99.67%) |
| V2, first record per treatment (descriptive) | 641 | 8 | 7 | 640 (99.84%) |

A collision means **distinct treatment IDs share exactly the same rendered text**. It does not assert distinct morphology or distinct molecular entities. Multiple reagents can share a gene, and compound identifiers can encode related structures. Blank labels never create a second treatment identity. Collision-free text is not automatically biologically informative.

## Information content

V1 renders `cells with perturbation of <gene>` where a gene exists, otherwise a perturbation-type fallback. The historical name “identifier-stripped” permits gene identity. It must never be relabeled identity-free. Gene is present in 3,770 records; 754/4,524 (16.67%) have only generic fallback content. Among labeled rows this is 420/4,190 (10.02%). Exact reagent distinctions are absent when multiple treatments share a gene, even if the gene itself is meaningful biological information.

V2 renders only `Metadata_pert_type`, `Metadata_control_type` and `Metadata_negcon_control_type`, deduplicating repeated field values. **100% of its text is generic category content under this explicit operational definition.** There are ten category signatures and no text variation within a signature. In particular `trt` is treatment status, not a compound-versus-CRISPR modality label; the source modality is not available in those fields. Thus the ordinary-treatment text does not even distinguish the two modalities. Twenty-eight records have none of the allowed fields and render neutral fallback text. Removing genes does not create descriptions of morphology, mechanism, pathway, target function, dose or duration.

A deterministic encoder receiving identical strings returns identical vectors under identical inference settings. With a shared gallery and filters, it cannot assign treatment-specific rankings from those strings. Different query-specific plate/well masks or tie ordering can create different observed retrieval results, but that distinction comes from evaluation structure, not recovered textual biology. A learned projection cannot manufacture missing within-category distinctions. These statements need no model run.

## Leakage and guard findings

V2 has zero matches to prohibited identifiers in the supplied universe. This is a scoped dictionary audit, not proof that all implicit identity or unprovided aliases are absent. Source plate, well, batch, compound names, sample IDs and target sequences are not rendering inputs. Acquisition conditions should remain separate evaluation metadata.

V1 intentionally exposes genes and allows a gene-based lookup shortcut. It also has **23 record-level guard failures in one text group**: the permitted gene symbol `F10` matches a well-coordinate token in the supplied universe. The guard reports `Metadata_Well` and normalized `well`. This is a gene/coordinate namespace ambiguity; it does not demonstrate that the renderer read a well field. The production transformer still rejects that text when supplied the complete universe. The audit reports pre-guard rendering counts and blocked counts separately; it neither suppresses this failure nor changes the frozen query condition. A future exception or typed identifier rule requires review under #52.

Identifiers are preserved in provenance and scoring channels. Those channels must never be concatenated into encoder input. Removing batch labels from queries does not justify removing them from auditing or split validation. Short symbols, Unicode forms, boundary collisions and cross-record identifiers are tested; external ontology expansion remains absent.

## Interpretation and next decision

Treat `M0_IDENTITY_FREE_V2` as a **deliberately weak category control**, pending explicit scientific approval of that role. It is not presently a discriminative biological language-retrieval task. Keep `M0_GENE_AWARE_V1` as a clearly labeled historical sensitivity condition, with an exact-gene lookup control. A primary biological query requires independently sourced, provenance-bearing functional or phenotypic content, an approved definition of relevance, and a new collision audit before encoder selection. M1 remains proposed, not approved.

Aggregate outputs are `outputs/phase5/queries/query_summary.json`, `query_groups.csv` (hashes and counts, no rendered identifiers) and `profile_manifest.json`. Tests cover collisions, deterministic counting, missing optional fields, unknown identity, forbidden gene/sample/well/plate/sequence values and the F10 namespace ambiguity. No frozen scores, checksums, benchmark definitions or reference files were altered.
