"""Offline HGNC nomenclature matching, not biological identity approval (#30, #52)."""

from __future__ import annotations

from collections import Counter, defaultdict


def resolve_symbols(labels, approved, withdrawn):
    """Preserve exact labels; never guess case, split strings or resolve withdrawals.

    Exact approved symbols take precedence over historical/alias uses of the same
    string, which remain visible. Unique previous symbols resolve nomenclature;
    alias-only matches remain candidates requiring review. Multiple historical
    candidates remain ambiguous. Returned records are private when labels are.
    """
    indexes = {name: defaultdict(set) for name in ("symbol", "prev_symbol", "alias_symbol")}
    seen = set()
    for row in approved:
        identity = row["hgnc_id"]
        if not identity or identity in seen or row["status"] != "Approved":
            raise ValueError("HGNC approved reference has duplicate/invalid IDs or status")
        seen.add(identity)
        for field, index in indexes.items():
            for value in row.get(field, "").split("|"):
                if value:
                    index[value].add(identity)
    old = defaultdict(list)
    for row in withdrawn:
        old[row["WITHDRAWN_SYMBOL"]].append(dict(row))
    results = []
    for label in sorted(set(labels)):
        exact, previous, alias = (indexes[k].get(label, set()) for k in indexes)
        candidates = previous | alias
        assigned = None
        if len(exact) == 1:
            assigned, kind = next(iter(exact)), "approved_symbol"
        elif len(exact) > 1 or len(candidates) > 1:
            kind = "ambiguous"
        elif len(previous) == 1:
            assigned, kind = next(iter(previous)), "previous_symbol"
        elif alias:
            kind = "alias_candidate"
        elif old[label]:
            kind = "withdrawn"
        else:
            kind = "unmapped"
        results.append(
            {
                "source_label": label,
                "match_kind": kind,
                "hgnc_id": assigned,
                "approved_symbol_candidates": sorted(exact),
                "previous_symbol_candidates": sorted(previous),
                "alias_candidates": sorted(alias),
                "withdrawn_records": sorted(old[label], key=lambda r: tuple(sorted(r.items()))),
                "secondary_candidate_conflict": bool(exact and candidates - exact),
                "biological_identity_reviewed": False,
            }
        )
    return results


def resolution_summary(records):
    """Aggregate only; source labels and stable-ID lists stay in the private ledger."""
    groups = defaultdict(list)
    for row in records:
        if row["hgnc_id"]:
            groups[row["hgnc_id"]].append(row["source_label"])
    return {
        "source_gene_strings": len(records),
        "match_kind_counts": dict(sorted(Counter(r["match_kind"] for r in records).items())),
        "nomenclature_assigned_source_strings": sum(bool(r["hgnc_id"]) for r in records),
        "distinct_nomenclature_HGNC_IDs": len(groups),
        "stable_IDs_merging_multiple_source_strings": sum(len(g) > 1 for g in groups.values()),
        "source_strings_in_merged_groups": sum(len(g) for g in groups.values() if len(g) > 1),
        "ambiguous_source_strings": sum(r["match_kind"] == "ambiguous" for r in records),
        "source_strings_with_withdrawn_records": sum(bool(r["withdrawn_records"]) for r in records),
        "secondary_candidate_conflicts": sum(r["secondary_candidate_conflict"] for r in records),
        "independently_reviewed_biological_gene_identities": 0,
        "nomenclature_is_study_relevance_approval": False,
    }
