"""Describe pinned public layout annotations; do not render queries or score models."""

import collections
import csv
import hashlib
import io
import json
from pathlib import Path


EXPECTED_SHA256 = {
    "layout_wells": "fff903fd3f9f61e45cb8b9c5506df06dc366fa7980f6cb7990077cf22e938d9f",
    "annotation_ledger": "0398a6a76910b7fc418a6d9457114d9a782ab86f37d02d0781ae6d3b4177b297",
}
CHECK_FIELDS = ("target_list", "pert_iname", "InChIKey")
MISSING_LABELS = frozenset(("", "na", "n/a", "nan", "none", "null", "unknown"))


def _describe(groups):
    sizes = collections.Counter(map(len, groups.values()))
    return {
        "distinct_groups": len(groups),
        "singleton_groups_and_ids": sizes[1],
        "collision_groups": sum(count for size, count in sizes.items() if size > 1),
        "ids_in_collision_groups": sum(size * count for size, count in sizes.items() if size > 1),
        "group_size_histogram": {str(size): count for size, count in sorted(sizes.items())},
        "largest_group_size": max(sizes, default=0),
    }


def _summarize(wells, ledger):
    included = {layout: set() for layout in ("Target1", "Target2")}
    for row in wells:
        if row.get("layout") not in included:
            raise ValueError("Unknown layout in the source well ledger")
        if row.get("included_in_key_comparison") not in ("True", "False"):
            raise ValueError("Invalid inclusion flag in the source well ledger")
        if row["included_in_key_comparison"] == "True":
            if not isinstance(row.get("broad_sample"), str) or not row["broad_sample"]:
                raise ValueError("Included well has no exact Broad sample ID")
            included[row["layout"]].add(row["broad_sample"])
    shared = included["Target1"] & included["Target2"]
    records = collections.defaultdict(list)
    for row in ledger:
        if row.get("broad_sample") in shared:
            if row.get("layout") not in included:
                raise ValueError("Unknown layout in annotation ledger")
            records[row["layout"], row["broad_sample"]].append(row)
    annotations = {}
    collapsed = 0
    for layout in included:
        for sample in sorted(shared):
            group = records[layout, sample]
            primary = [row for row in group if row.get("status") == "unique_annotation"]
            if len(primary) != 1:
                raise ValueError("Each included sample needs one unique annotation per layout")
            chosen = primary[0]
            if any(not isinstance(chosen.get(field), str) for field in CHECK_FIELDS):
                raise ValueError("Annotation identity and target fields must be strings")
            for row in group:
                if row is chosen:
                    continue
                if row.get("status") != "identical_duplicate_collapsed":
                    raise ValueError("Unexpected duplicate annotation status")
                if any(row.get(field) != chosen[field] for field in CHECK_FIELDS):
                    raise ValueError("Duplicate annotation fields disagree")
                collapsed += 1
            annotations[layout, sample] = chosen
    for sample in shared:
        for field in CHECK_FIELDS:
            if annotations["Target1", sample][field] != annotations["Target2", sample][field]:
                raise ValueError("Cross-layout annotation disagreement: " + field)
    for row in wells:
        if row["included_in_key_comparison"] == "True" and row["broad_sample"] in shared:
            if row.get("InChIKey") != annotations[row["layout"], row["broad_sample"]]["InChIKey"]:
                raise ValueError("Layout and annotation standardized keys disagree")

    raw_groups = collections.defaultdict(list)
    canonical_groups = collections.defaultdict(list)
    name_groups = collections.defaultdict(list)
    missing_targets = collections.Counter()
    lists_with_missing_tokens = 0
    missing_names = collections.Counter()
    for sample in sorted(shared):
        row = annotations["Target1", sample]
        name = row["pert_iname"]
        if name.strip().lower() in MISSING_LABELS:
            missing_names[name] += 1
        else:
            name_groups[name].append(sample)
        raw = row["target_list"]
        if raw.strip().lower() in MISSING_LABELS:
            missing_targets[raw] += 1
            continue
        tokens = [token.strip() for token in raw.split("|")]
        if any(token.lower() in MISSING_LABELS for token in tokens):
            lists_with_missing_tokens += 1
            continue
        raw_groups[raw].append(sample)
        canonical_groups[tuple(sorted(set(tokens)))].append(sample)

    return {
        "schema_version": 1,
        "analysis_kind": "public_layout_annotation_identifiability",
        "status": "PROPOSED_NOT_APPROVED",
        "plan_only": True,
        "shared_broad_sample_ids": len(shared),
        "standardized_key_groups": len({annotations["Target1", sample]["InChIKey"] for sample in shared}),
        "identical_duplicate_rows_collapsed": collapsed,
        "cross_layout_annotation_disagreements": {field: 0 for field in CHECK_FIELDS},
        "target_annotation_coverage_ids": sum(map(len, canonical_groups.values())),
        "missing_target_annotations_by_raw_value": dict(sorted(missing_targets.items())),
        "target_lists_with_missing_tokens": lists_with_missing_tokens,
        "raw_target_list_strings": _describe(raw_groups),
        "canonical_target_sets": _describe(canonical_groups),
        "name_annotation_coverage_ids": sum(map(len, name_groups.values())),
        "missing_name_annotations_by_raw_value": dict(sorted(missing_names.items())),
        "exact_pert_iname_strings": _describe(name_groups),
        "method": (
            "Intersect included exact Broad sample IDs; verify within- and cross-layout annotation "
            "agreement; use Target1 annotations. Canonical target sets split on '|', strip tokens, "
            "deduplicate, and sort with case preserved. Missing labels are accounted separately."
        ),
        "limitations": [
            "These are source annotation string/set counts, not actual rendered-query counts, tokenization, embeddings, or measured information content.",
            "Target labels have not been independently validated for gene nomenclature, target engagement, biological relevance, or cell-context effects.",
            "Reusing these annotations to generate queries and define biological positives can create circular evaluation; independent relevance evidence is still required.",
            "Distinct strings do not establish biologically meaningful discrimination; identical target sets cannot uniquely specify the exact compound or stock.",
            "Compound names carry identity information; their uniqueness is a descriptive contrast and does not approve them as biological-description queries.",
            "No retrieval scoring, model fitting, biological replication, statistical power, or scientific contract approval is established.",
            "Counts concern the shared public design cohort only and do not validate historical category-only queries or private experimental records.",
        ],
    }


def analyze(layout_path, ledger_path):
    """Return an aggregate report from the exact two previously reviewed source files.

    Raise ValueError on a hash mismatch, malformed source, or annotation contradiction.
    Read local files only; no repository changes, downloads, or output writes occur.
    """
    payloads = {}
    hashes = {}
    for role, path in (("layout_wells", layout_path), ("annotation_ledger", ledger_path)):
        payload = Path(path).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != EXPECTED_SHA256[role]:
            raise ValueError("Pinned source SHA-256 mismatch: " + role)
        payloads[role] = payload
        hashes[role] = digest
    reader = csv.DictReader(io.StringIO(payloads["layout_wells"].decode("utf-8"), newline=""))
    required = {"layout", "broad_sample", "InChIKey", "included_in_key_comparison"}
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("Missing or duplicate well-ledger headers")
    if not required.issubset(reader.fieldnames):
        raise ValueError("Required well-ledger columns are missing")
    wells = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in wells):
        raise ValueError("Ragged well-ledger rows")
    ledger = json.loads(payloads["annotation_ledger"].decode("utf-8"))
    if not isinstance(ledger, list) or any(not isinstance(row, dict) for row in ledger):
        raise ValueError("Annotation ledger must be a list of records")
    result = _summarize(wells, ledger)
    result["source_sha256"] = hashes
    return result
