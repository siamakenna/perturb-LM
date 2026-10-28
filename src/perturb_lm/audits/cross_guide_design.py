"""Proposed metadata relation and balanced-weight contracts; no scorer (#30, #52)."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations, permutations

import pandas as pd

from perturb_lm.audits.guide_support import sequence
from perturb_lm.audits.rotations import canonical_wells


def relation(anchor, candidate, mask="different_row_and_column"):
    """Classify supplied reviewed identities; never infer guide review from HGNC.

    Records carry explicit reviewed, gene_id, guide_id, sequence, plate, well and
    condition fields. Unknown relationships stay unlabeled in the full gallery.
    This helper does not perform independent identity review or read profiles.
    """
    if mask not in {"different_coordinate", "different_row_and_column"}:
        raise ValueError("Unknown spatial mask")
    for row in (anchor, candidate):
        if not all(row.get(k) for k in ("plate", "well", "condition")):
            raise ValueError("Physical identity and recorded condition required")
    wells = canonical_wells(pd.Series([anchor["well"], candidate["well"]]))
    if not wells.str.fullmatch(r"[A-P](?:0[1-9]|1[0-9]|2[0-4])").all():
        raise ValueError("Invalid physical well")
    a, b = (sequence(row.get("sequence", "")) for row in (anchor, candidate))
    same_reagent = bool(anchor.get("reagent_id")) and anchor.get("reagent_id") == candidate.get(
        "reagent_id"
    )
    same_guide = bool(anchor.get("guide_id")) and anchor.get("guide_id") == candidate.get(
        "guide_id"
    )
    if (same_reagent or same_guide) and (
        (a and b and a != b)
        or (
            anchor.get("gene_id")
            and candidate.get("gene_id")
            and anchor["gene_id"] != candidate["gene_id"]
        )
    ):
        raise ValueError("Canonical guide identity contradicts sequence or gene")
    if anchor["plate"] == candidate["plate"]:
        return "excluded_same_plate"
    if anchor["condition"] != candidate["condition"]:
        return "excluded_condition"
    if wells[0] == wells[1] or (
        mask == "different_row_and_column"
        and (wells[0][0] == wells[1][0] or wells[0][1:] == wells[1][1:])
    ):
        return "excluded_position"
    if same_reagent or same_guide or (a and a == b):
        return "excluded_same_guide_or_sequence"
    if not all(
        row.get("reviewed") is True and row.get("gene_id") and row.get("guide_id")
        for row in (anchor, candidate)
    ) or not (a and b):
        return "unlabeled"
    return "same_gene_other_guide" if anchor["gene_id"] == candidate["gene_id"] else "reference"


def coverage(anchors, gallery, mask="different_row_and_column"):
    """Preserve the complete supplied gallery and no-positive/reference anchors."""
    if mask not in {"different_coordinate", "different_row_and_column"}:
        raise ValueError("Unknown spatial mask")
    for population in (anchors, gallery):
        physical = set()
        for row in population:
            relation(row, row, mask)  # validate even when the opposite population is empty
            well = canonical_wells(pd.Series([row["well"]]))[0]
            key = (row["plate"], well)
            if key in physical:
                raise ValueError("Duplicate physical wells in supplied population")
            physical.add(key)
    counts = Counter(
        {
            key: 0
            for key in (
                "supported_anchors",
                "no_positive_anchors",
                "no_reference_anchors",
                "contrast_eligible_anchors",
            )
        }
    )
    for anchor in anchors:
        labels = Counter(relation(anchor, candidate, mask) for candidate in gallery)
        positive, reference = bool(labels["same_gene_other_guide"]), bool(labels["reference"])
        counts["supported_anchors"] += positive
        counts["no_positive_anchors"] += not positive
        counts["no_reference_anchors"] += not reference
        counts["contrast_eligible_anchors"] += positive and reference
    return {
        "total_anchors": len(anchors),
        "base_gallery_records": len(gallery),
        **dict(counts),
        "execution_allowed": False,
    }


def balanced_comparison_weights(records, plates):
    """Weight metadata cells equally by gene/pair/plate pair/orientations/wells.

    Each record identifies one anchor well, canonical partner guide, reviewed gene,
    and ordered physical plate pair. It must already have positive AND reference
    support. No numerical features or effects enter this function. Incomplete
    guide pairs are excluded in their entirety; no minimum study size is chosen.
    Well aliases are canonicalized before physical-identity checks. Duplicate
    observations fail, rather than adding apparent replication.
    """
    if len(plates) != 4 or len(set(plates)) != 4:
        raise ValueError("Exactly four distinct physical plates required")
    expected = set(permutations(plates, 2))
    cells = defaultdict(list)
    observed = set()
    physical_anchors = {}
    for row in records:
        row = tuple(row)
        gene, guide, partner, p, q, well = row
        if not all(row) or guide == partner or (p, q) not in expected:
            raise ValueError("Invalid comparison metadata")
        canonical = canonical_wells(pd.Series([well], dtype="string"))
        if not canonical.str.fullmatch(r"[A-P](?:0[1-9]|1[0-9]|2[0-4])").fillna(False).all():
            raise ValueError("Invalid physical well")
        well = canonical.iloc[0]
        row = (gene, guide, partner, p, q, well)
        if row in observed:
            raise ValueError("Duplicate comparison observation")
        physical = (p, well)
        if physical in physical_anchors and physical_anchors[physical] != (gene, guide):
            raise ValueError("Physical anchor identity contradiction")
        physical_anchors[physical] = (gene, guide)
        observed.add(row)
        pair = tuple(sorted((guide, partner)))
        cells[(gene, pair, p, q, guide)].append(well)
    pairs = defaultdict(set)
    for gene, pair, *_ in cells:
        pairs[gene].add(pair)
    complete = {
        gene: {
            pair
            for pair in candidates
            if all((gene, pair, p, q, g) in cells for p, q in expected for g in pair)
        }
        for gene, candidates in pairs.items()
    }
    complete = {gene: pairs for gene, pairs in complete.items() if pairs}
    weights = []
    for key, wells in sorted(cells.items()):
        gene, pair, p, q, guide = key
        if pair not in complete.get(gene, set()):
            continue
        denominator = len(complete) * len(complete[gene]) * len(list(combinations(plates, 2)))
        denominator *= 2 * 2 * len(wells)  # plate direction, guide direction, anchor wells
        for well in sorted(wells):
            partner = next(g for g in pair if g != guide)
            weights.append(((gene, guide, partner, p, q, well), 1 / denominator))
    return {
        "weights": weights,
        "eligible_gene_groups": len(complete),
        "input_gene_groups": len(pairs),
        "complete_guide_pairs": sum(map(len, complete.values())),
        "input_guide_pairs": sum(map(len, pairs.values())),
        "independent_experiments": None,
        "execution_allowed": False,
    }
