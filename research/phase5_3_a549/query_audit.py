"""New, non-predictive description-information audit for Phase 5.3.

This module does not render historical V1/V2 descriptions or encoder queries.
It compares two *new* field-signature analogues on the supplied cohort.  The
unit of identity is a unique recorded reagent, not a well.  Source annotation
groups are not biological equivalence classes.

``analyze_query_information`` returns a dictionary containing a JSON-safe
``summary`` and a ``private_collision_ledger`` pandas DataFrame.  Only the
summary is suitable for an aggregate/public report.  The ledger contains source
identifiers and literal field values and must remain private.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
import numbers
import re
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = (
    "row_id", "plate", "well", "gene", "reagent", "sequence", "condition",
    "treatment", "control", "pert_type", "control_type", "negcon_control_type",
)
CATEGORY_FIELDS = ("pert_type", "control_type", "negcon_control_type")
DESCRIPTION_FIELDS = {
    "category_only": CATEGORY_FIELDS,
    "gene_aware": CATEGORY_FIELDS + ("gene",),
}
_MISSING = ("missing", "")
# A lexical ambiguity check, NOT a gene-symbol validator.  Some real gene
# symbols match well coordinates.  Preserve every such literal annotation.
_WELL_LIKE = re.compile(r"^(?:[A-Z]|A[A-F])(?:0?[1-9]|[1-3][0-9]|4[0-8])$", re.I)
_LEDGER_COLUMNS = (
    "description", "reagent", "signature_sha256", "signature_json",
    "equivalence_class_size", "is_collision", "included_in_identity_metrics",
    "reagent_has_conflicting_signatures", "observed_row_count",
    "observed_plate_count", "observed_row_ids_json", "recorded_gene_values_json",
    "gene_missing_observed", "gene_well_like_observed",
)


def _value_token(value: Any) -> tuple[str, str]:
    """A tagged scalar prevents literal missing-marker/signature collisions."""
    if not pd.api.types.is_scalar(value):
        raise ValueError("Audit fields must contain scalar values.")
    if pd.isna(value) or (isinstance(value, str) and not value.strip()):
        return _MISSING
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, bool) or pd.api.types.is_bool(value):
        return ("boolean", "true" if bool(value) else "false")
    if isinstance(value, numbers.Integral):
        return ("integer", str(int(value)))
    if isinstance(value, numbers.Real):
        return ("real", repr(float(value)))
    return (type(value).__name__, str(value))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _flag(value: Any, column: str) -> bool | None:
    token = _value_token(value)
    if token == _MISSING:
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1"}:
            return True
        if text in {"false", "0"}:
            return False
    elif isinstance(value, numbers.Real) or pd.api.types.is_bool(value):
        if value == 1:
            return True
        if value == 0:
            return False
    raise ValueError(
        f"Column '{column}' must use explicit boolean, 0/1, or true/false values."
    )


def _well_like(token: tuple[str, str]) -> bool:
    return token[0] == "string" and _WELL_LIKE.fullmatch(token[1].strip()) is not None


def _signature(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    # Names and tags make this an unambiguous serialization, not encoder text.
    return _json([[field, list(_value_token(row[field]))] for field in fields])


def _collision_statistics(group_sizes: list[int]) -> dict[str, Any]:
    """Uniform unique-reagent statistics for deterministic field signatures."""
    sizes = sorted(group_sizes)
    total = sum(sizes)
    collisions = [size for size in sizes if size > 1]
    counts = Counter(sizes)
    singletons = counts.get(1, 0)
    return {
        "analyzed_unique_reagent_count": total,
        "distinct_signature_count": len(sizes),
        "equivalence_class_size_histogram": [
            {"class_size": size, "signature_count": counts[size],
             "reagent_count": size * counts[size]}
            for size in sorted(counts)
        ],
        "minimum_equivalence_class_size": min(sizes) if sizes else None,
        "maximum_equivalence_class_size": max(sizes) if sizes else None,
        "collision_signature_count": len(collisions),
        "collision_reagent_count": sum(collisions),
        "minimum_collision_group_size": min(collisions) if collisions else None,
        "maximum_collision_group_size": max(collisions) if collisions else None,
        "unique_signature_reagent_count": singletons,
        "fraction_reagents_with_unique_signature": singletons / total if total else None,
        "conditional_identity_entropy_bits": (
            sum((size / total) * math.log2(size) for size in sizes) if total else None
        ),
        "tie_only_expected_exact_identity_hit_at_1": len(sizes) / total if total else None,
    }


def analyze_query_information(metadata: pd.DataFrame) -> dict[str, Any]:
    """Audit new category-only and recorded-gene-aware field signatures.

    ``metadata`` must have all columns in ``REQUIRED_COLUMNS``.  Only rows with
    an explicit true ``treatment`` flag enter identity statistics.  Null/blank
    reagent IDs are counted and excluded; missing categories remain explicit
    tagged signature components.  Null/blank genes form an unknown-annotation
    component, not a biological relation.  Nonblank literal values, including
    well-like strings and textual marker strings, are retained unchanged.

    A reagent observed with multiple signatures is excluded from that
    description's identity statistics and fully counted/retained privately.
    This avoids choosing an arbitrary well or inventing a synthetic description.
    Thus each analyzed reagent has one deterministic signature.

    Entropy is H(recorded reagent | field signature), with uniform weighting of
    the analyzed unique reagents.  The tie-only reference assumes uniform random
    choice among reagents sharing the signature.  These are information summaries,
    not measured retrieval performance or unrestricted learned-task bounds.
    The function performs no I/O and does not mutate the input.
    """
    if not isinstance(metadata, pd.DataFrame):
        raise TypeError("metadata must be a pandas DataFrame.")
    if not metadata.columns.is_unique:
        raise ValueError("Metadata column names must be unique.")
    missing_columns = [name for name in REQUIRED_COLUMNS if name not in metadata.columns]
    if missing_columns:
        raise ValueError("Missing required metadata columns: " + ", ".join(missing_columns))

    rows = metadata.loc[:, list(REQUIRED_COLUMNS)].to_dict(orient="records")
    treatment_flags = [_flag(row["treatment"], "treatment") for row in rows]
    control_flags = [_flag(row["control"], "control") for row in rows]
    treatment_rows = [row for row, flag in zip(rows, treatment_flags) if flag is True]
    # A dict key is a type-tagged identity; string and numeric IDs cannot collide.
    reagent_rows: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in treatment_rows:
        token = _value_token(row["reagent"])
        if token != _MISSING:
            reagent_rows[token].append(row)

    def count_missing(field: str) -> dict[str, int]:
        return {
            "treatment_row_count": sum(_value_token(row[field]) == _MISSING for row in treatment_rows),
            "unique_reagent_count_with_any_missing": sum(
                any(_value_token(row[field]) == _MISSING for row in group)
                for group in reagent_rows.values()
            ),
            "unique_reagent_count_with_all_missing": sum(
                all(_value_token(row[field]) == _MISSING for row in group)
                for group in reagent_rows.values()
            ),
        }

    plates = {_value_token(row["plate"]) for row in rows} - {_MISSING}
    row_ids = [_value_token(row["row_id"]) for row in rows]
    nonmissing_row_ids = [token for token in row_ids if token != _MISSING]
    well_like_rows = [row for row in treatment_rows if _well_like(_value_token(row["gene"]))]
    summary: dict[str, Any] = {
        "schema_version": "phase53.query_information.v1",
        "analysis_kind": "new_observed_field_signature_audit",
        "historical_description_equivalence_verified": False,
        "historical_641_query_results_recomputed": False,
        "predictive_query_renderer_called": False,
        "encoder_queries_generated": 0,
        "model_runs": 0,
        "input_accounting": {
            "row_count": len(rows),
            "plate_count": len(plates),
            "rows_with_missing_plate": sum(_value_token(row["plate"]) == _MISSING for row in rows),
            "treatment_row_count": len(treatment_rows),
            "control_row_count": sum(flag is True for flag in control_flags),
            "rows_flagged_both_treatment_and_control": sum(
                treatment is True and control is True
                for treatment, control in zip(treatment_flags, control_flags)
            ),
            "rows_with_missing_treatment_flag": sum(flag is None for flag in treatment_flags),
            "rows_with_missing_control_flag": sum(flag is None for flag in control_flags),
            "rows_with_missing_row_id": len(row_ids) - len(nonmissing_row_ids),
            "duplicate_nonmissing_row_id_count": len(nonmissing_row_ids) - len(set(nonmissing_row_ids)),
            "treatment_rows_with_missing_reagent": sum(
                _value_token(row["reagent"]) == _MISSING for row in treatment_rows
            ),
            "treatment_unique_reagent_count": len(reagent_rows),
        },
        "missing_category_accounting": {field: count_missing(field) for field in CATEGORY_FIELDS},
        "gene_annotation_accounting": {
            "missing": count_missing("gene"),
            "treatment_rows_with_well_like_recorded_gene": len(well_like_rows),
            "unique_reagents_with_well_like_recorded_gene": sum(
                any(_well_like(_value_token(row["gene"])) for row in group)
                for group in reagent_rows.values()
            ),
            "treatment_rows_with_gene_matching_recorded_well": sum(
                _value_token(row["gene"])[0] == "string"
                and _value_token(row["well"])[0] == "string"
                and row["gene"].strip().upper() == row["well"].strip().upper()
                for row in well_like_rows
            ),
            "well_like_values_are_unresolved_identifier_ambiguities_not_invalid_genes": True,
        },
        "descriptions": {},
        "interpretation": {
            "description_status": (
                "Both descriptions are new informational analogues; exact historical V1/V2 "
                "renderer equivalence has not been verified."
            ),
            "identity_unit": "Uniformly weighted unique recorded treatment reagent, not repeated wells.",
            "candidate_scope": (
                "Analyzed unique treatment reagents are pooled across the supplied plates; "
                "no per-plate candidate masks or retrieval scores are evaluated."
            ),
            "missing_value_policy": (
                "Null and blank values are explicit unknown components; all nonblank literal "
                "values are retained without gene curation, alias resolution, or biological equivalence."
            ),
            "conflict_policy": (
                "Reagents with multiple observed signatures are counted and excluded separately "
                "for each description; no well is chosen as authoritative. If exclusions differ, "
                "the analyzed populations differ, so a between-description difference cannot be "
                "attributed solely to adding the gene field."
            ),
            "entropy_definition": "H(reagent | signature) = sum over classes of (class size / N) * log2(class size).",
            "tie_reference_assumptions": (
                "Uniform prior over analyzed unique reagents and uniform random choice within "
                "each observed signature class; the reference equals signature count / reagent count."
            ),
            "limits": (
                "These are observed field-signature collisions, not retrieval scores or an "
                "upper bound for an arbitrary learned task. Literal recorded gene information "
                "can trivially help gene identity and does not establish biological understanding. "
                "Source-gene annotation resolution and same-gene multi-guide biology are separate tasks."
            ),
        },
    }

    ledger: list[dict[str, Any]] = []
    for description, fields in DESCRIPTION_FIELDS.items():
        by_reagent: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
        for reagent_key in sorted(reagent_rows):
            variants: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in reagent_rows[reagent_key]:
                variants[_signature(row, fields)].append(row)
            by_reagent[reagent_key] = variants
        consistent = {key: next(iter(variants)) for key, variants in by_reagent.items() if len(variants) == 1}
        identity_groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for key, variants in by_reagent.items():
            if key in consistent:
                identity_groups[consistent[key]].append(key)

        stats = _collision_statistics([len(group) for group in identity_groups.values()])
        conflicting_keys = {key for key, variants in by_reagent.items() if len(variants) > 1}
        stats.update({
            "fields": list(fields),
            "eligible_unique_reagent_count": len(reagent_rows),
            "excluded_conflicting_unique_reagent_count": len(conflicting_keys),
            "excluded_conflicting_treatment_row_count": sum(len(reagent_rows[key]) for key in conflicting_keys),
            "analyzed_reagent_fraction": len(consistent) / len(reagent_rows) if reagent_rows else None,
        })
        summary["descriptions"][description] = stats

        for key in sorted(by_reagent):
            variants = by_reagent[key]
            for signature in sorted(variants):
                observed = variants[signature]
                gene_tokens = sorted({_value_token(row["gene"]) for row in observed})
                gene_values = [list(token) for token in gene_tokens]
                plate_tokens = {_value_token(row["plate"]) for row in observed} - {_MISSING}
                # Pick an identical reagent value deterministically; keys already
                # enforce equality at the tagged source-value level.
                reagent_value = observed[0]["reagent"]
                included = key in consistent
                class_size = len(identity_groups[signature]) if included else None
                ledger.append({
                    "description": description,
                    "reagent": reagent_value,
                    "signature_sha256": hashlib.sha256(signature.encode("utf-8")).hexdigest(),
                    "signature_json": signature,
                    "equivalence_class_size": class_size,
                    "is_collision": bool(class_size is not None and class_size > 1),
                    "included_in_identity_metrics": included,
                    "reagent_has_conflicting_signatures": key in conflicting_keys,
                    "observed_row_count": len(observed),
                    "observed_plate_count": len(plate_tokens),
                    "observed_row_ids_json": _json(sorted({_value_token(row["row_id"]) for row in observed})),
                    "recorded_gene_values_json": _json(gene_values),
                    "gene_missing_observed": _MISSING in gene_tokens,
                    "gene_well_like_observed": any(_well_like(token) for token in gene_tokens),
                })

    private_ledger = pd.DataFrame(ledger, columns=list(_LEDGER_COLUMNS))
    # Fails locally if future modifications accidentally introduce non-JSON
    # scalars or nonfinite output; does not serialize any private ledger values.
    json.dumps(summary, allow_nan=False)
    return {"summary": summary, "private_collision_ledger": private_ledger}


__all__ = ["analyze_query_information", "REQUIRED_COLUMNS", "CATEGORY_FIELDS"]
