# Phase 5.2 compound layout feasibility crosswalk

2026-10-14. Related issues: #30 and #52. Proposed scientific support tooling only.
This change adds an offline comparison of the two public JUMP compound layouts.
It does not reproduce the completed Phase 5.1 four-plate rotation planner, alter
the frozen benchmark, or authorize an experiment.

## What this code answers

Given the original compound metadata and platemap TSV for each of Target-1 and
Target-2, which **full standardized InChIKey groups** occur in both maps, and
which of those groups have a pair of different well coordinates?

The official JUMP standardization workflow includes charge, isotope, stereo and
tautomer parent operations. A full-key match is therefore a **standardized-parent
candidate bridge**, not proof of stereospecific chemical identity, identical
source stock, an exact reagent match, or equivalent biology. Distinct
`broad_sample` identifiers remain visible and separate. The auditor does not join
using a key prefix, compound display name, gene name, or rounded identifier.

Official source references to pin alongside the four inputs:

- `https://github.com/jump-cellpainting/JUMP-Target`
- `https://github.com/broadinstitute/monorepo/blob/912315df698cc0f3e9daadcd6ef994a7af94fbdd/libs/smiles/src/smiles/standardize_smiles.py`

The second link is provided as the recorded standardizer source revision; inspect
the exact implementation reference in the scientific evidence register before
treating chemical standardization as resolved. The auditor itself does not
contact either repository or reproduce chemistry processing.

## Additive implementation

- `src/perturb_lm/audits/layouts.py`: standard-library comparison and bounded TSV reader.
- `scripts/audit_phase5_2_layouts.py`: local input provenance verification and private outputs.
- `tests/test_phase5_2_layouts.py`: synthetic assertions and executable CLI tests.
- `tests/fixtures/phase5_2/`: four small invented TSVs; all sample and gene labels
  start with `SYNTH_`. Their fabricated key strings exercise format and join
  behavior; they are not actual chemicals or chemical-validity evidence.

API:

```python
summary, key_groups, map_ledger, annotation_ledger = compare_compound_layouts(
    target1_metadata_rows,
    target1_platemap_rows,
    target2_metadata_rows,
    target2_platemap_rows,
)
```

Each input is a list of dictionaries retaining TSV values as strings. Metadata
requires `broad_sample`, `InChIKey`, `pert_type` and `control_type`. Maps require
`well_position` and `broad_sample`; extra original annotation columns are retained
in the annotation ledger. The same source `broad_sample` namespace is assumed
for the two files from the pinned JUMP-Target repository. This utility must not
be reused with unrelated sample-ID namespaces without an explicit extension.

## Join, control and ambiguity rules

1. Canonicalize only surrounding whitespace and 384-well coordinate notation
   (`a1` becomes `A01`). Sample identifiers are never converted to numbers or
   chemically merged. Wells outside A01–P24 fail closed. Each layout reports
   `map_complete_384_wells` and `missing_384_well_coordinates`; a partial map is
   permitted for testing or bounded inspection, but must not be presented as a
   complete layout crosswalk.
2. Require each canonical well to appear at most once per map. Duplicate wells
   are an error, even if their rows look identical. The file is a layout design,
   not a list of repeated acquisitions.
3. Collapse duplicate annotation rows only when their complete trimmed records
   are identical, and record their number and input line. Conflicting annotations
   for the same sample abort. This specifically prevents duplicate metadata from
   multiplying a well-map join.
4. Require `pert_type=trt` with a missing `control_type` for the non-control key
   comparison. `pert_type=control` is explicitly excluded. Unknown classifications
   remain excluded. A treatment row with a nonmissing control designation fails
   closed as contradictory. This rule is for these source tables, not a new
   universal definition for production metadata.
5. Empty map sample IDs, unmatched IDs, unknown treatment/control status, and
   missing or malformed full keys remain in the map ledger with exclusion
   reasons. DMSO solvent alone does not certify a negative-control well.
6. A source sample ID that has conflicting key or control information between
   layouts aborts. Multiple distinct source IDs mapping to one full key are
   preserved and flagged; no first-match selection or implicit stock equivalence
   is applied.
7. Compare only valid non-control full-key groups and their sets of canonical
   map coordinates. Same-coordinate and different-coordinate pair counts are
   **layout-design counts**, never numbers of measured replicate pairs.

No minimal reagent-count threshold is supplied or assessed. All reports state
`PROPOSED_NOT_APPROVED`, `plan_only=true` and `execution_allowed=false`.

## Run the synthetic checks without installing project dependencies

From this source tree on a machine with Python 3.10–3.12:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p test_phase5_2_layouts.py -v

PYTHONPATH=src python3 scripts/audit_phase5_2_layouts.py \
  --synthetic-fixture \
  --out outputs/phase5_2/synthetic-layout-check

(cd outputs/phase5_2/synthetic-layout-check && shasum -a 256 -c SHA256SUMS)
```

Use a fresh output name for each execution. Outputs are private (directory mode
0700 and file mode 0600), deterministic for identical inputs and code, and
restricted to this source tree's ignored `outputs/`. The supplied source archive
does not have to be a Git checkout; its unconditional `/outputs/` ignore rule is
checked. In a Git checkout every prospective output must also pass
`git check-ignore`. Paths redirected outside `outputs/` fail closed.

Synthetic expectations are three shared key groups; two have a different-
coordinate pair, one has only a same-coordinate pair, and one shared key group
has multiple source samples within a layout. These are **invented test cases**,
not measurements from JUMP. The tests also distinguish same source sample IDs
from different IDs, verify that full keys with the same first block do not join,
exercise duplicate/conflict and provenance failures, and run the actual CLI
twice to check private permissions, checksums and deterministic output bytes.

## Run on the four public source files

First obtain the four small TSVs at one reviewed immutable upstream revision.
Record their exact downloaded bytes and source URLs. This program has no network
mode and does not download data. It bounds each TSV to 5 MB, each annotation
table to 10,000 rows, and each map to 384 wells; these are input-size protections,
not scientific sufficiency thresholds.

Create a local `provenance.json` with this schema; replace the angle-bracket
placeholders with actual values. There must be exactly the four role keys shown.

```json
{
  "schema_version": 1,
  "repository": "jump-cellpainting/JUMP-Target",
  "revision": "<40-character lowercase Git commit SHA>",
  "files": {
    "target1_metadata": {
      "path": "JUMP-Target-1_compound_metadata.tsv",
      "sha256": "<64-character SHA256>",
      "url": "https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/<revision>/JUMP-Target-1_compound_metadata.tsv"
    },
    "target1_platemap": {
      "path": "JUMP-Target-1_compound_platemap.tsv",
      "sha256": "<64-character SHA256>",
      "url": "https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/<revision>/JUMP-Target-1_compound_platemap.tsv"
    },
    "target2_metadata": {
      "path": "JUMP-Target-2_compound_metadata.tsv",
      "sha256": "<64-character SHA256>",
      "url": "https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/<revision>/JUMP-Target-2_compound_metadata.tsv"
    },
    "target2_platemap": {
      "path": "JUMP-Target-2_compound_platemap.tsv",
      "sha256": "<64-character SHA256>",
      "url": "https://raw.githubusercontent.com/jump-cellpainting/JUMP-Target/<revision>/JUMP-Target-2_compound_platemap.tsv"
    }
  }
}
```

The manifest's SHA256 values are checked against the local files. The source
revision and URL binding are recorded declarations; the offline audit cannot
independently establish where the bytes were downloaded. Paths must resolve
inside the supplied metadata directory. Source URLs must bind the declared
repository and immutable revision. No private user path is written to the
aggregate summary.

```bash
PYTHONPATH=src python3 scripts/audit_phase5_2_layouts.py \
  --metadata-dir outputs/phase5_2/public-inputs \
  --provenance outputs/phase5_2/public-inputs/provenance.json \
  --out outputs/phase5_2/layout-crosswalk-review
```

Outputs:

| File | Content |
| --- | --- |
| `summary.json` | Aggregate design counts, exclusions, input/implementation hashes and limitations |
| `standardized-key-groups_PRIVATE.json` | Full key groups, distinct source IDs, both coordinate sets, ambiguity flags and pair counts |
| `layout-wells_PRIVATE.csv` | Every map well, classification and explicit exclusion reasons |
| `annotation-ledger_PRIVATE.json` | Every source annotation row and any duplicate-collapse decision |
| `SHA256SUMS` | SHA256 of the four result files |

## What remains to be implemented only after review

This crosswalk does not create a measured cohort. A separate measurement
inventory must join actual public `(source, plate, well)` rows to pinned layouts,
preserve physical plate identity across acquisitions, and establish cell
background, dose, exposure, protocols, culture lineage and batch provenance.
Different plate labels, source labels, acquisition folders, map coordinates and
profile rows are not interchangeable replicate units.

Source key normalization must be audited against original structures and sample
preparation before defining a compound retrieval positive. The compounds with
several source IDs per standardized key need explicit adjudication. Target-gene
overlap is a different relation requiring independent annotation provenance,
direction and relevance rules; this utility never promotes it to a positive.

Feature compatibility and upstream normalization/selection scope remain
unresolved by layout metadata. The program deliberately reports measured plate,
culture, batch, matched-condition and biological-positive counts as `null`, not
zero and not estimates. It performs no profile scoring, train/test assignment,
preprocessing, pretrained inference, statistical power calculation or biological
validation.
