# Public-safe guide-support figure specifications

2026-10-20. Related issues: #30 and #52. **Specifications only; no new scores.**
Evidence source: the inspected census and provenance chain in the
[closeout](PHASE5_GUIDE_SUPPORT_CLOSEOUT.md). These panels may communicate metadata
capacity after review; they are not biological-performance figures.

## Figure 1 — Cohort and identity-review flow

Purpose: distinguish physical observations from annotation groups and reviewed
biological identities. Use a flow diagram with separate unit labels; do not
merge wells, sequences and genes onto a common numerical scale.

| Stage | Safe aggregate label |
| --- | --- |
| Original selected historical cohort | 12 profile files; 4,524 wells; matching 904-feature schema |
| Four matched U2OS/Cas9 CRISPR plates | 1,536 wells; WGA retained; 144 h; one original source batch |
| Excluded from noncontrol population | 480 labeled controls; 16 missing-label wells |
| Full noncontrol population | 1,040 wells; 247 reagent IDs; 247 sequence strings; 130 source gene strings; four physical plates |
| Coordinate-only provisional B capacity | 936 unique query wells across four plates; 234 reagents/sequences; 117 source gene strings |
| Different-row-and-column provisional B capacity | 720 unique query wells across four plates; 180 reagents/sequences; 90 source gene strings |
| Stable identity / independence review | Pending; 0 reviewed stable gene IDs supplied; actual stable-gene count unknown |

Branch the coordinate-only and strict masks from the same full population, or
clearly mark the strict branch as a subset of the coordinate-only branch. Do not
add the branches together. Include the full-gallery denominator: 260 wells /
247 reagent IDs per gallery plate, including rows without same-gene support.
Show source gene strings as candidate annotation groups; do not label 90 as
independently verified stable genes. Use no gene names, sequences, well lists,
reagent IDs, image thumbnails, filesystem paths or row hashes.

Proposed caption: "Metadata capacity in the preserved CPJUMP1 subset. Distinct
sequences and source gene annotations await independent biological identity
review. Wells and repeated plate roles do not establish independent cultures."

## Figure 2 — Spatial support and population separation

Panel A: grouped bars for supported query-well coverage, with fixed denominator
260 per assignment. Distinguish exact reagent (A) and provisional same-source-gene /
different-sequence capacity (B) using color plus direct labels. Report no-positive
queries in accompanying text/table, not hidden exclusions.

| Mask | A supported / 260 | B supported / 260 | A no-positive | B no-positive |
| --- | ---: | ---: | ---: | ---: |
| Different coordinate | 26 / 260 (10.00%) | 234 / 260 (90.00%) | 234 | 26 |
| Different row AND column | 22 / 260 (8.46%) | 180 / 260 (69.23%) | 238 | 80 |

All 12 assignments share these counts. Use one aggregate bar per endpoint/mask,
with an explicit "12 dependent assignments; four reused plates" annotation.
Do not draw bootstrap error bars across assignments or imply n=12 independent
experiments. Optional small-multiple coverage tables can show all ordered public
plate roles; identical bars add no independent evidence.

Panel B: separate source-gene-string sets, not a score comparison. Coordinate-only
A=13 and B=117, intersection=0; strict A=11 and B=90, intersection=0. Label the
sets as endpoint-specific supported populations. Do not infer this intersection
from marginal bar heights; it was independently enumerated from metadata.
A synthetic counterexample confirms overlap is possible under the definitions.

Proposed caption: "Cross-guide metadata support covers a different population
from exact-reagent support. This figure reports candidate support, not retrieval
accuracy, efficacy or biological relevance. Raw and training-supported reagent-ID
coverage coincide; no model was trained and all guide sequences were exposed on
the other plates."

## Export and provenance rules

A future figure should use only the safe aggregate values above; preserve a
versioned aggregate input table and this document's exact design revision. Put
source code SHA `60af90117836b5b563f7ca8113a8a285b0956a46`, source revision and
inspected-summary digest in the caption/supplement or linked provenance table.
Use the existing counts without running a profile scorer. Prefer an accessible
palette, unit labels and exportable SVG/PDF with legible text. No UMAP, neighbor
plot, microscope image, confidence interval or performance claim is supplied by
this metadata evidence. A future scored-result panel requires separate approval.
