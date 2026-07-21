"""Split and leakage integrity checks for controlled modeling experiments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class IntegrityReport:
    """Aggregate split-integrity result."""

    ok: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checksum: str = ""
    aggregate_counts: dict[str, Any] = field(default_factory=dict)


def validate_split_integrity(
    frame: pd.DataFrame,
    *,
    split_column: str = "split",
    profile_id_column: str = "profile_id",
    plate_column: str | None = "plate",
    well_column: str | None = "well",
    batch_column: str | None = "batch",
    treatment_column: str | None = "treatment",
    split_type: str,
    min_evaluable_queries: int = 1,
    n_evaluable_queries: int | None = None,
) -> IntegrityReport:
    """Validate public-safe aggregate split properties."""

    errors: list[str] = []
    warnings: list[str] = []
    if split_column not in frame.columns:
        errors.append(f"Missing split column: {split_column}")
        return _report(frame, split_column=split_column, errors=errors, warnings=warnings)
    if profile_id_column not in frame.columns:
        errors.append(f"Missing profile ID column: {profile_id_column}")
    required_splits = {"train", "test"}
    observed_splits = set(frame[split_column].astype(str))
    missing_splits = sorted(required_splits.difference(observed_splits))
    if missing_splits:
        errors.append(f"Missing required split labels: {missing_splits}")

    train = frame[frame[split_column].astype(str) == "train"]
    test = frame[frame[split_column].astype(str) == "test"]
    if profile_id_column in frame.columns:
        overlap = set(train[profile_id_column].astype(str)).intersection(
            set(test[profile_id_column].astype(str))
        )
        if overlap:
            errors.append("Train and test profile IDs overlap.")
        comparable_columns = [column for column in frame.columns if column != split_column]
        row_overlap = train[comparable_columns].astype(str).merge(
            test[comparable_columns].astype(str),
            how="inner",
        )
        if not row_overlap.empty:
            errors.append("Train and test rows overlap.")

    if split_type == "held_out_plate":
        _validate_no_value_overlap(train, test, plate_column, errors, "held-out plate")
    elif split_type == "held_out_treatment":
        _validate_no_value_overlap(train, test, treatment_column, errors, "held-out treatment")
    elif split_type == "held_out_batch":
        if not _has_multiple_values(frame, batch_column):
            warnings.append("Held-out batch is unavailable because fewer than two batches exist.")
        else:
            _validate_no_value_overlap(train, test, batch_column, errors, "held-out batch")
    elif split_type in {
        "exclude_same_plate",
        "exclude_same_well",
        "exclude_same_plate_and_well",
    }:
        warnings.append(f"{split_type} is a retrieval filter, not a train/test split.")
    else:
        errors.append(f"Unsupported split_type: {split_type}")

    if n_evaluable_queries is None:
        warnings.append("n_evaluable_queries was not provided and must be reported explicitly.")
    elif n_evaluable_queries < min_evaluable_queries:
        errors.append(
            "n_evaluable_queries is below the configured minimum "
            f"({n_evaluable_queries} < {min_evaluable_queries})."
        )

    return _report(frame, split_column=split_column, errors=errors, warnings=warnings)


def evaluate_split_evaluable_thresholds(
    observed_counts: dict[str, dict[str, int | bool | str]],
    thresholds: dict[str, int | dict[str, object]],
    *,
    allow_synthetic_overrides: bool = False,
) -> pd.DataFrame:
    """Evaluate split-specific total/evaluable query thresholds."""

    rows: list[dict[str, object]] = []
    for split, threshold in thresholds.items():
        observed = observed_counts.get(split, {})
        total = int(observed.get("n_total_queries", 0) or 0)
        evaluable = int(observed.get("n_evaluable_queries", 0) or 0)
        if isinstance(threshold, dict):
            rows.append(
                {
                    "split": split,
                    "status": "unavailable",
                    "threshold": None,
                    "n_total_queries": total,
                    "n_evaluable_queries": evaluable,
                    "reason": str(threshold.get("reason", "Split is unavailable.")),
                }
            )
            continue
        if threshold < 2 and not allow_synthetic_overrides:
            raise ValueError("Scientific runs cannot use evaluable-query thresholds below 2.")
        status = "passed" if evaluable >= threshold else "failed"
        rows.append(
            {
                "split": split,
                "status": status,
                "threshold": int(threshold),
                "n_total_queries": total,
                "n_evaluable_queries": evaluable,
                "reason": ""
                if status == "passed"
                else f"{split} has {evaluable} evaluable queries below threshold {threshold}.",
            }
        )
    return pd.DataFrame(rows)


def validate_query_text_no_identifier_leakage(
    queries: pd.DataFrame,
    *,
    text_column: str = "query_text",
    prohibited_columns: list[str] | None = None,
    prohibited_values: list[str] | None = None,
) -> IntegrityReport:
    """Fail when plate, well, batch, or held-out treatment identifiers enter query text."""

    errors: list[str] = []
    warnings: list[str] = []
    if text_column not in queries.columns:
        errors.append(f"Missing query text column: {text_column}")
        return IntegrityReport(ok=False, errors=errors, warnings=warnings)
    values = list(prohibited_values or [])
    for column in prohibited_columns or []:
        if column not in queries.columns:
            warnings.append(f"Prohibited identifier source column is unavailable: {column}")
            continue
        values.extend(queries[column].dropna().astype(str).tolist())
    normalized_values = {
        value.strip().lower()
        for value in values
        if value is not None and str(value).strip()
    }
    for text in queries[text_column].fillna("").astype(str):
        lowered = text.lower()
        if any(value in lowered for value in normalized_values):
            errors.append("Query text contains a prohibited identifier value.")
            break
    return IntegrityReport(ok=not errors, errors=errors, warnings=warnings)


def validate_preprocessor_fit_scope(
    preprocessor: object,
    *,
    expected_fit_split: str = "train",
) -> IntegrityReport:
    """Validate that a fitted preprocessor records train-only fitting."""

    metadata = getattr(preprocessor, "fit_metadata_", {}) or {}
    fit_split = metadata.get("fit_split")
    errors = []
    if fit_split != expected_fit_split:
        errors.append(
            f"Preprocessor fit_split is {fit_split!r}; expected {expected_fit_split!r}."
        )
    return IntegrityReport(ok=not errors, errors=errors)


def split_public_checksum(
    frame: pd.DataFrame,
    *,
    split_column: str = "split",
    group_columns: list[str] | None = None,
) -> str:
    """Checksum aggregate split counts without serializing raw row-level values."""

    group_columns = group_columns or []
    payload: dict[str, Any] = {
        "n_rows": int(len(frame)),
        "split_counts": _value_counts(frame, split_column),
        "group_column_presence": {column: column in frame.columns for column in group_columns},
    }
    for column in group_columns:
        if column in frame.columns:
            payload[f"{column}_unique_count_by_split"] = (
                frame.groupby(split_column)[column].nunique(dropna=True).astype(int).to_dict()
            )
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validate_no_value_overlap(
    train: pd.DataFrame,
    test: pd.DataFrame,
    column: str | None,
    errors: list[str],
    label: str,
) -> None:
    if not column or column not in train.columns or column not in test.columns:
        errors.append(f"Missing {label} column.")
        return
    overlap = set(train[column].dropna().astype(str)).intersection(
        set(test[column].dropna().astype(str))
    )
    if overlap:
        errors.append(f"Train and test {label} values overlap.")


def _has_multiple_values(frame: pd.DataFrame, column: str | None) -> bool:
    return bool(column and column in frame.columns and frame[column].nunique(dropna=True) > 1)


def _value_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in frame.columns:
        return {}
    return {
        str(key): int(value)
        for key, value in frame[column].astype(str).value_counts(sort=True).sort_index().items()
    }


def _report(
    frame: pd.DataFrame,
    *,
    split_column: str,
    errors: list[str],
    warnings: list[str],
) -> IntegrityReport:
    counts = {"n_rows": int(len(frame)), "split_counts": _value_counts(frame, split_column)}
    return IntegrityReport(
        ok=not errors,
        warnings=warnings,
        errors=errors,
        checksum=split_public_checksum(frame, split_column=split_column),
        aggregate_counts=counts,
    )
