"""Offline Target-1/Target-2 compound layout crosswalk, not an experiment (#30, #52)."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

MISSING = {"", "na", "n/a", "nan", "null", "<na>"}
METADATA_COLUMNS = {"broad_sample", "InChIKey", "pert_type", "control_type"}
MAP_COLUMNS = {"well_position", "broad_sample"}
KEY_PATTERN = re.compile(r"[A-Z]{14}-[A-Z]{10}-[A-Z]")
WELL_PATTERN = re.compile(r"([A-Pa-p])(0?[1-9]|1[0-9]|2[0-4])")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a bounded, lossless string table; never coerce identifiers to numbers."""
    if path.stat().st_size > 5_000_000:
        raise ValueError("Layout metadata exceeds the 5 MB per-file bound")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        columns = reader.fieldnames or []
        if not columns or len(columns) != len(set(columns)) or any(not c for c in columns):
            raise ValueError("Empty or duplicate input TSV column names")
        rows = list(reader)
    if not rows or len(rows) > 10_000:
        raise ValueError("Expected between 1 and 10000 metadata rows")
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Ragged input TSV")
    return rows


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("All metadata values must remain strings")
    return value.strip()


def _missing(value: str) -> bool:
    return value.casefold() in MISSING


def _prepare_layout(metadata: list[dict], platemap: list[dict], label: str) -> tuple:
    if not metadata or not platemap:
        raise ValueError("Metadata and platemap must both be nonempty")
    if len(metadata) > 10_000 or len(platemap) > 384:
        raise ValueError("Expected a bounded annotation table and one 384-well layout")
    annotations, annotation_ledger = {}, []
    duplicates = 0
    for number, raw in enumerate(metadata, start=2):
        if not METADATA_COLUMNS <= raw.keys():
            raise ValueError(f"{label}: missing required metadata columns")
        if {"layout", "input_line", "status"} & raw.keys():
            raise ValueError("Annotation columns overlap reserved audit ledger fields")
        row = {key: _text(value) for key, value in raw.items()}
        sample = row["broad_sample"]
        status = "unique_annotation"
        if _missing(sample):
            status = "missing_sample_identifier"
        elif sample in annotations:
            if row != annotations[sample]:
                raise ValueError(f"{label}: conflicting annotations for one broad_sample")
            duplicates += 1
            status = "identical_duplicate_collapsed"
        else:
            annotations[sample] = row
        annotation_ledger.append(
            {"layout": label, "input_line": number, "status": status, **row}
        )

    seen_wells, records = set(), []
    for number, raw in enumerate(platemap, start=2):
        if not MAP_COLUMNS <= raw.keys():
            raise ValueError(f"{label}: missing required platemap columns")
        row = {key: _text(value) for key, value in raw.items()}
        match = WELL_PATTERN.fullmatch(row["well_position"])
        if not match:
            raise ValueError(f"{label}: invalid 384-well coordinate")
        well = f"{match[1].upper()}{int(match[2]):02d}"
        if well in seen_wells:
            raise ValueError(f"{label}: duplicate canonical well coordinate")
        seen_wells.add(well)
        sample = row["broad_sample"]
        annotation = annotations.get(sample)
        reasons = []
        if _missing(sample):
            reasons.append("missing_map_sample_identifier")
        elif annotation is None:
            reasons.append("unmatched_sample_identifier")
        key, pert_type, control_type = "", "", ""
        if annotation is not None:
            key = annotation["InChIKey"]
            pert_type = annotation["pert_type"].casefold()
            control_type = annotation["control_type"]
            if pert_type == "trt":
                if not _missing(control_type):
                    raise ValueError(f"{label}: contradictory treatment/control annotation")
            elif pert_type == "control":
                reasons.append("control")
            else:
                reasons.append("unknown_treatment_control_status")
            if _missing(key):
                key = ""
                reasons.append("missing_full_inchikey")
            elif not KEY_PATTERN.fullmatch(key):
                reasons.append("invalid_full_inchikey")
        records.append(
            {
                "layout": label,
                "input_line": number,
                "well_position": well,
                "broad_sample": "" if _missing(sample) else sample,
                "InChIKey": key,
                "pert_type": pert_type,
                "control_type": control_type,
                "included_in_key_comparison": not reasons,
                "exclusion_reasons": "|".join(reasons),
            }
        )
    used = {record["broad_sample"] for record in records}
    summary = {
        "annotation_rows": len(metadata),
        "identical_duplicate_annotation_rows_collapsed": duplicates,
        "distinct_annotation_sample_identifiers": len(annotations),
        "annotation_sample_identifiers_absent_from_map": len(set(annotations) - used),
        "annotation_rows_missing_sample_identifier": sum(
            item["status"] == "missing_sample_identifier" for item in annotation_ledger
        ),
        "layout_wells": len(records),
        "map_complete_384_wells": len(seen_wells) == 384,
        "missing_384_well_coordinates": 384 - len(seen_wells),
        "noncontrol_wells_with_valid_full_inchikey": sum(
            record["included_in_key_comparison"] for record in records
        ),
        "excluded_layout_wells": sum(
            not record["included_in_key_comparison"] for record in records
        ),
        "exclusion_reason_counts_nonexclusive": dict(
            sorted(
                Counter(
                    reason
                    for record in records
                    for reason in record["exclusion_reasons"].split("|")
                    if reason
                ).items()
            )
        ),
    }
    return summary, sorted(records, key=lambda row: row["well_position"]), annotation_ledger


def compare_compound_layouts(
    target1_metadata: list[dict],
    target1_platemap: list[dict],
    target2_metadata: list[dict],
    target2_platemap: list[dict],
) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """Compare layout design by full standardized InChIKey, retaining source sample IDs.

    Return aggregate summary, PRIVATE key groups, PRIVATE map ledger and PRIVATE annotation
    ledger. No experimental measurements, physical plates, or relevance labels are inferred.
    Full keys may encode standardized parents after stereochemistry/salt processing; key
    equality is not proof of the same stock, exact reagent, or biological equivalence.
    """
    summaries, layouts, annotations = {}, {}, []
    for label, metadata, platemap in (
        ("Target1", target1_metadata, target1_platemap),
        ("Target2", target2_metadata, target2_platemap),
    ):
        summaries[label], layouts[label], ledger = _prepare_layout(metadata, platemap, label)
        annotations.extend(ledger)

    # Contradictory source IDs must not be hidden behind a chemical-key join.
    by_sample = {}
    for row in annotations:
        sample = row["broad_sample"]
        if _missing(sample):
            continue
        identity = (
            "" if _missing(row["InChIKey"]) else row["InChIKey"],
            row["pert_type"].casefold(),
            "" if _missing(row["control_type"]) else row["control_type"].casefold(),
        )
        if sample in by_sample and by_sample[sample] != identity:
            raise ValueError(
                "One source broad_sample has conflicting cross-layout identity/control"
            )
        by_sample[sample] = identity

    groups = {}
    for label, rows in layouts.items():
        for row in rows:
            if row["included_in_key_comparison"]:
                groups.setdefault(row["InChIKey"], {"Target1": [], "Target2": []})[label].append(
                    row
                )
    key_ledger = []
    for key, group in sorted(groups.items()):
        a, b = group["Target1"], group["Target2"]
        a_samples = {row["broad_sample"] for row in a}
        b_samples = {row["broad_sample"] for row in b}
        a_wells, b_wells = {row["well_position"] for row in a}, {row["well_position"] for row in b}
        same_coordinate_pairs = len(a_wells & b_wells)
        all_pairs = len(a_wells) * len(b_wells)
        key_ledger.append(
            {
                "InChIKey": key,
                "present_in_both_layouts": bool(a and b),
                "target1_sample_ids": sorted(a_samples),
                "target2_sample_ids": sorted(b_samples),
                "shared_source_sample_identifiers": sorted(a_samples & b_samples),
                "target1_coordinates": sorted(a_wells),
                "target2_coordinates": sorted(b_wells),
                "cross_layout_coordinate_pairs": all_pairs,
                "same_coordinate_pairs": same_coordinate_pairs,
                "different_coordinate_pairs": all_pairs - same_coordinate_pairs,
                "multiple_sample_ids_within_a_layout": len(a_samples) > 1 or len(b_samples) > 1,
                "identity_status": (
                    "standardized_key_match_requires_structure_and_stock_review"
                    if a and b
                    else "unmatched_standardized_key"
                ),
                "experimental_replication_status": "not_assessed_from_layouts",
            }
        )
    shared = [row for row in key_ledger if row["present_in_both_layouts"]]
    summary = {
        "status": "PROPOSED_NOT_APPROVED",
        "plan_only": True,
        "execution_allowed": False,
        "analysis_kind": "compound_layout_design_crosswalk",
        "identity_join": "full_InChIKey_standardized_parent_candidate_bridge",
        "layouts": summaries,
        "union_standardized_key_groups": len(key_ledger),
        "shared_standardized_key_groups": len(shared),
        "shared_groups_with_any_different_coordinate_pair": sum(
            row["different_coordinate_pairs"] > 0 for row in shared
        ),
        "shared_groups_with_only_same_coordinate_pairs": sum(
            row["different_coordinate_pairs"] == 0 for row in shared
        ),
        "shared_groups_with_multiple_source_samples_within_a_layout": sum(
            row["multiple_sample_ids_within_a_layout"] for row in shared
        ),
        "shared_groups_with_any_identical_source_sample_identifier": sum(
            bool(row["shared_source_sample_identifiers"]) for row in shared
        ),
        "cross_layout_different_coordinate_pairs": sum(
            row["different_coordinate_pairs"] for row in shared
        ),
        "measured_physical_plates": None,
        "independent_cultures": None,
        "independent_batches": None,
        "matched_dose_duration_cell_context_pairs": None,
        "biological_positive_pairs": None,
        "limitations": [
            "Layout wells and coordinate pairs are design entities, not measured replicates.",
            "Full InChIKey equality may collapse charge, isotopes, stereochemistry and tautomers.",
            "Different broad_sample identifiers remain separate source samples.",
            "Many-to-one sample-to-key groups require review; no first-match selection is used.",
            "Target gene annotations, biological relevance and preprocessing are not validated.",
            "No scientific sufficiency threshold, inference, or scoring is implemented.",
        ],
    }
    return summary, key_ledger, layouts["Target1"] + layouts["Target2"], annotations


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
