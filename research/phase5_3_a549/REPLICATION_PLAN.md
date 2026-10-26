# Parallel scientific development after the U2OS feasibility result

The executable arm in this branch is a same-batch A549 context extension.
Its actual result remains unestablished until the Mac verifies and scores the
four source-bound objects. It does not replace independent-cohort validation.
The following complementary compound arm is metadata-only and unexecuted.

# Next external-cohort task: bounded compound metadata selection

26 October 2026. **PROPOSED_METADATA_ONLY_NOT_EXECUTED.** No production cohort,
eligible-pair count, profile availability or independent culture unit was
established in this review. The sources below were inspected at their moving
`main` references; immutable revisions and byte receipts still need to be fixed
before execution.

The proposed arm asks whether a frozen compound comparison can transfer across
verified layouts and data-generating sources. It complements the individual-guide
CRISPR study. Production CRISPR uses pooled guides per gene, so it does not
automatically provide an independent replication of that endpoint. The A549 arm
remains a separate same-batch context assessment. [Dataset description][hub]

## What the public sources actually document

- `plate.csv.gz` provides `Metadata_Source`, `Metadata_Batch`, `Metadata_Plate`
  and `Metadata_PlateType`. The inspected database schema lists `TARGET1` and
  `TARGET2` among plate types. Its plate primary key is `Metadata_Plate`.
- `well.csv.gz` links `Metadata_Source`, `Metadata_Plate`, `Metadata_Well` and
  `Metadata_JCP2022`; its documented primary key is plate plus well. Compound
  identity metadata include `Metadata_JCP2022` and `Metadata_InChIKey`.
- `perturbation_control.csv` is the documented canonical control table. The
  schema also relates sources to microscope settings and CellProfiler versions.
  These identifiers do not establish independent cultures. [Schema][schema]
  [and complete definitions][sql]
- Target-1 and Target-2 compounds have different layouts and may have different
  `broad_sample` identifiers. The resource recommends identity matching through
  InChIKey. That is an identity crosswalk, not a claim that different compounds
  are biological positives. [JUMP-Target][target]

## Smallest executable investigation

1. **Pin and inventory.** Record immutable revisions for the metadata and target
   repositories. Inspect object sizes and LFS metadata before acquisition. Begin
   with schemas, plate/control catalogs and the two small target annotation/layout
   files. Record URLs, Git identities, byte counts and SHA-256 hashes. Keep a
   fixed file allowlist and explicit byte/row bounds. No profiles or images enter
   this step.
2. **Select candidate plate groups from actual rows.** Filter the pinned plate
   catalog by compound-relevant plate types and retain source, batch and plate.
   Check key uniqueness and conflicting source assignments. Do not invent a
   source/plate manifest from a manuscript or infer layout membership from a
   plate-name substring. Produce a candidate catalog before inspecting new
   morphology scores.
3. **Obtain only the selected well/identity rows.** Use a verified per-plate
   partition or a genuinely bounded row-query route, if available. Retain original
   physical keys and check plate/source consistency at each join. Match selected
   production JCP IDs to full chemical identity keys, then the target layouts.
   Preserve duplicate, missing, ambiguous and contradictory identities without
   join fanout. Do not join on display names or truncated chemical keys.
4. **Count feasibility losses.** Report coverage separately for wells, exact
   compound identities, plates, layouts, batches and sources. Count position-
   diverse matched identities under explicit spatial masks. Preserve unknown
   relations and control categories. Resolve dose, duration, cell context,
   acquisition lineage and fit populations from additional source evidence;
   missing fields remain unknown. A source or batch label alone is insufficient
   evidence of a new culture preparation.
5. **Freeze the holdout boundary.** Write an exact selected-object manifest,
   development/holdout roles, endpoint, candidate rules, exclusions and
   preprocessing policy before opening any new profile values. An exact-identity
   compound endpoint and a shared-target endpoint are distinct experiments;
   shared targets require an independent relevance specification. Source-wide
   preprocessing must remain explicit and cannot become an inductive claim by
   applying another scaler afterward.

## Present acquisition blocker and stopping rule

The inspected setup script imports the complete compressed `well.csv.gz` into a
local database. It does not establish an available remote row-filtering service
or per-plate metadata partition. No bounded well-row route was verified here.
Streaming or filtering a full gzip locally still transfers the full archive;
calling that archive metadata does not make it a bounded acquisition.

If no bounded selected-row route exists, finish the small-file catalog and
record **BLOCKED_SELECTED_WELL_ROWS_UNAVAILABLE**. Do not automatically download
the entire well table, build a full production database, recursively acquire
profiles, or claim chemical overlap/position eligibility. A later bounded extract
can complete the crosswalk. No collaborator message or new biological approval
is required merely to document this blocker.

The next deliverable is a source-bound feasibility manifest and exclusion ledger,
not a retrieval score. Different-source data may strengthen a future
generalization study once identity, conditions, lineage and preprocessing are
bound; this plan alone establishes none of those results.

[schema]: https://github.com/jump-cellpainting/datasets/blob/main/metadata/README.md
[sql]: https://raw.githubusercontent.com/jump-cellpainting/datasets/main/metadata/db/setup.sql
[target]: https://github.com/jump-cellpainting/JUMP-Target
[hub]: https://github.com/broadinstitute/jump_hub/blob/main/explanations/data_description.md
