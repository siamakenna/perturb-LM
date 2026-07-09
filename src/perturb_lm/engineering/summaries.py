"""Aggregate split and leakage summaries for engineering reliability reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

SCHEMA_VERSION = "1.0"

BATCH_COLUMN_CANDIDATES = [
    "experiment",
    "batch",
    "Batch",
    "Metadata_Batch",
    "Metadata_Inferred_Batch",
]
PLATE_COLUMN_CANDIDATES = ["plate", "Plate", "Metadata_Plate"]
WELL_COLUMN_CANDIDATES = ["well", "Well", "Metadata_Well"]
TREATMENT_COLUMN_CANDIDATES = [
    "perturbation_key",
    "perturbation_id",
    "Metadata_broad_sample",
    "Metadata_pert_iname",
    "Metadata_gene",
    "Metadata_pert_id",
]

EXPECTED_LEAKAGE_DIAGNOSTICS = {
    "batch": "same_batch",
    "plate": "same_plate",
    "well": "same_well",
    "perturbation_treatment": "same_treatment",
}


def build_split_summary(
    frame: pd.DataFrame,
    *,
    split_name: str,
    split_type: str,
    split_column: str = "split",
    batch_columns: Iterable[str] | None = None,
    plate_columns: Iterable[str] | None = None,
    well_columns: Iterable[str] | None = None,
    treatment_columns: Iterable[str] | None = None,
    n_evaluable_queries: int | None = None,
) -> dict[str, Any]:
    """Summarize a held-out split without exposing row-level metadata."""

    warnings: list[str] = []
    split_type = str(split_type)
    if split_column not in frame.columns:
        warnings.append(f"Split column '{split_column}' is missing.")
        empty = _empty_split_summary(split_name, split_type, split_column, len(frame), warnings)
        return empty

    work = frame.copy()
    work[split_column] = work[split_column].fillna("").astype(str)
    train = work[work[split_column] == "train"]
    test = work[work[split_column] == "test"]
    val = work[work[split_column] == "val"]
    other = work[~work[split_column].isin(["train", "test", "val"])]

    batch_column = _first_existing(work, batch_columns or BATCH_COLUMN_CANDIDATES)
    plate_column = _first_existing(work, plate_columns or PLATE_COLUMN_CANDIDATES)
    well_column = _first_existing(work, well_columns or WELL_COLUMN_CANDIDATES)
    treatment_column = _first_existing(work, treatment_columns or TREATMENT_COLUMN_CANDIDATES)

    summary = _empty_split_summary(split_name, split_type, split_column, len(work), warnings)
    summary.update(
        {
            "train_row_count": int(len(train)),
            "val_row_count": int(len(val)),
            "test_row_count": int(len(test)),
            "other_row_count": int(len(other)),
            "batch_column": batch_column,
            "plate_column": plate_column,
            "well_column": well_column,
            "treatment_column": treatment_column,
            "train_batch_count": _unique_count(train, batch_column),
            "test_batch_count": _unique_count(test, batch_column),
            "train_plate_count": _group_count(train, [batch_column, plate_column]),
            "test_plate_count": _group_count(test, [batch_column, plate_column]),
            "train_well_count": _group_count(train, [batch_column, plate_column, well_column]),
            "test_well_count": _group_count(test, [batch_column, plate_column, well_column]),
            "train_perturbation_count": _unique_count(train, treatment_column),
            "test_perturbation_count": _unique_count(test, treatment_column),
        }
    )

    train_treatments = _unique_values(train, treatment_column)
    test_treatments = _unique_values(test, treatment_column)
    if treatment_column is None:
        warnings.append("No perturbation or treatment column was available for overlap counts.")
    else:
        overlap = train_treatments & test_treatments
        test_overlap_rows = test[test[treatment_column].fillna("").astype(str).isin(overlap)]
        summary.update(
            {
                "treatment_overlap_count": int(len(overlap)),
                "treatment_overlap_rate": _rate(len(overlap), len(test_treatments)),
                "n_evaluable_queries": (
                    int(n_evaluable_queries)
                    if n_evaluable_queries is not None
                    else int(len(test_overlap_rows))
                ),
            }
        )

    _append_missing_label_warnings(
        warnings,
        batch_column=batch_column,
        plate_column=plate_column,
        well_column=well_column,
        treatment_column=treatment_column,
    )
    _append_one_group_warnings(
        warnings,
        work,
        split_type=split_type,
        batch_column=batch_column,
        plate_column=plate_column,
        well_column=well_column,
        treatment_column=treatment_column,
    )
    if len(test) == 0:
        warnings.append("No test rows are present for this split.")
    if len(train) == 0:
        warnings.append("No train rows are present for this split.")

    summary["warnings"] = _dedupe(warnings)
    return summary


def split_summary_to_frame(summary: dict[str, Any]) -> pd.DataFrame:
    """Return a one-row CSV-friendly split summary."""

    row = {
        key: (" | ".join(value) if isinstance(value, list) else value)
        for key, value in summary.items()
    }
    return pd.DataFrame([row])


def write_split_summary(
    summary: dict[str, Any],
    out_dir: Path | str,
    *,
    json_name: str = "split_summary.json",
    csv_name: str = "split_summary.csv",
) -> dict[str, Path]:
    """Write aggregate split summary JSON and CSV files."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / json_name
    csv_path = out_dir / csv_name
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    split_summary_to_frame(summary).to_csv(csv_path, index=False)
    return {"split_summary_json": json_path, "split_summary_csv": csv_path}


def build_neighbor_leakage_summary(
    summary: pd.DataFrame,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a public-safe aggregate summary from nearest-neighbor diagnostics."""

    metadata = metadata or {}
    rows: list[dict[str, Any]] = []
    warnings = [str(warning) for warning in metadata.get("warnings", [])]
    if not summary.empty and "warning" in summary.columns:
        warnings.extend(
            str(warning)
            for warning in summary["warning"].dropna().astype(str)
            if warning.strip()
        )

    for _, row in summary.iterrows():
        raw_metric = str(row.get("metric", ""))
        diagnostic = str(row.get("diagnostic", ""))
        public_prefix = EXPECTED_LEAKAGE_DIAGNOSTICS.get(diagnostic)
        if not public_prefix or not raw_metric.startswith(f"same_{diagnostic}_at_"):
            continue
        k = _safe_int(row.get("k"))
        n_queries = _safe_int(row.get("n_queries"))
        n_evaluable = _safe_int(row.get("n_evaluable_queries"))
        rate_all = _safe_float(row.get("value_all_queries", row.get("value")))
        rate_evaluable = _safe_float(row.get("value_evaluable_queries", 0.0))
        rows.append(
            {
                "diagnostic": _public_diagnostic_name(diagnostic),
                "raw_diagnostic": diagnostic,
                "metric": f"{public_prefix}_at_{k}",
                "raw_metric": raw_metric,
                "filter_name": str(row.get("filter_name", "")),
                "k": k,
                "n_queries": n_queries,
                "n_evaluable_queries": n_evaluable,
                "count": int(round(rate_all * n_queries)),
                "rate_all_queries": rate_all,
                "rate_evaluable_queries": rate_evaluable,
                "n_queries_with_candidates": _safe_int(row.get("n_queries_with_candidates")),
                "warning": str(row.get("warning", "") or ""),
            }
        )

    available_raw = {row["raw_diagnostic"] for row in rows}
    skipped = []
    available_metadata = {
        str(item.get("diagnostic", ""))
        for item in metadata.get("diagnostic_columns", [])
        if isinstance(item, dict)
    }
    for diagnostic in EXPECTED_LEAKAGE_DIAGNOSTICS:
        if diagnostic in available_raw:
            continue
        if diagnostic not in available_metadata:
            reason = f"No {diagnostic} label column was available."
        else:
            reason = f"No same-{_public_diagnostic_name(diagnostic)} rows were produced."
        skipped.append(
            {
                "diagnostic": _public_diagnostic_name(diagnostic),
                "raw_diagnostic": diagnostic,
                "reason": reason,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": "dashboard_leakage_summary",
        "dataset": str(metadata.get("dataset", "")),
        "n_queries": max((row["n_queries"] for row in rows), default=0),
        "n_evaluable_queries": max((row["n_evaluable_queries"] for row in rows), default=0),
        "metrics": rows,
        "skipped_diagnostics": skipped,
        "warnings": _dedupe(warnings),
        "data_policy": (
            "Aggregate counts and rates only; no row-level metadata, local paths, "
            "image names, embeddings, or raw identifiers are included."
        ),
    }


def leakage_summary_to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    """Return CSV rows for the metric list in a leakage payload."""

    columns = [
        "diagnostic",
        "metric",
        "filter_name",
        "k",
        "n_queries",
        "n_evaluable_queries",
        "count",
        "rate_all_queries",
        "rate_evaluable_queries",
        "n_queries_with_candidates",
        "warning",
    ]
    rows = [{column: metric.get(column) for column in columns} for metric in payload["metrics"]]
    return pd.DataFrame(rows, columns=columns)


def write_leakage_summary(
    payload: dict[str, Any],
    out_dir: Path | str,
    *,
    json_name: str = "leakage_summary.json",
    csv_name: str = "leakage_summary.csv",
    dashboard_json_name: str = "dashboard_leakage_summary.json",
) -> dict[str, Path]:
    """Write public-safe leakage summary JSON/CSV artifacts."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / json_name
    csv_path = out_dir / csv_name
    dashboard_path = out_dir / dashboard_json_name
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    dashboard_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    leakage_summary_to_frame(payload).to_csv(csv_path, index=False)
    return {
        "leakage_summary_json": json_path,
        "leakage_summary_csv": csv_path,
        "dashboard_leakage_summary_json": dashboard_path,
    }


def build_query_leakage_dashboard_summary(
    summary: pd.DataFrame,
    *,
    dataset: str = "",
) -> dict[str, Any]:
    """Build a public-safe aggregate summary for query-positive leakage diagnostics."""

    metrics = {
        str(row["metric"]): _safe_int(row["value"])
        for _, row in summary.iterrows()
        if "metric" in summary.columns and "value" in summary.columns
    }
    n_queries = metrics.get("n_queries", 0)
    rows = []
    for name, metric in [
        ("cross_batch", "queries_with_positive_cross_batch"),
        ("cross_plate", "queries_with_positive_cross_plate"),
        ("cross_split", "queries_with_positive_cross_split"),
        ("positive_in_other_split", "queries_with_positive_in_other_split"),
        ("missing_positive_metadata", "queries_with_missing_positive_metadata"),
    ]:
        count = metrics.get(metric, 0)
        rows.append(
            {
                "diagnostic": name,
                "metric": metric,
                "n_queries": n_queries,
                "count": count,
                "rate_all_queries": _rate(count, n_queries),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": "dashboard_query_leakage_summary",
        "dataset": dataset,
        "n_queries": n_queries,
        "metrics": rows,
        "warnings": [],
        "data_policy": (
            "Aggregate counts and rates only; no row-level metadata, local paths, "
            "image names, embeddings, or raw identifiers are included."
        ),
    }


def _empty_split_summary(
    split_name: str,
    split_type: str,
    split_column: str,
    row_count: int,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": "split_summary",
        "split_name": split_name,
        "split_type": split_type,
        "split_column": split_column,
        "row_count": int(row_count),
        "train_row_count": 0,
        "val_row_count": 0,
        "test_row_count": 0,
        "other_row_count": 0,
        "batch_column": None,
        "plate_column": None,
        "well_column": None,
        "treatment_column": None,
        "train_batch_count": None,
        "test_batch_count": None,
        "train_plate_count": None,
        "test_plate_count": None,
        "train_well_count": None,
        "test_well_count": None,
        "train_perturbation_count": None,
        "test_perturbation_count": None,
        "treatment_overlap_count": None,
        "treatment_overlap_rate": None,
        "n_evaluable_queries": None,
        "warnings": warnings,
        "data_policy": "Aggregate split counts only; no row-level metadata is included.",
    }


def _append_missing_label_warnings(
    warnings: list[str],
    *,
    batch_column: str | None,
    plate_column: str | None,
    well_column: str | None,
    treatment_column: str | None,
) -> None:
    if batch_column is None:
        warnings.append("No batch column was available for batch counts.")
    if plate_column is None:
        warnings.append("No plate column was available for plate counts.")
    if well_column is None:
        warnings.append("No well column was available for well counts.")
    if treatment_column is None:
        warnings.append("No perturbation or treatment column was available.")


def _append_one_group_warnings(
    warnings: list[str],
    frame: pd.DataFrame,
    *,
    split_type: str,
    batch_column: str | None,
    plate_column: str | None,
    well_column: str | None,
    treatment_column: str | None,
) -> None:
    lowered = split_type.lower()
    checks = [
        ("batch", batch_column),
        ("plate", plate_column),
        ("well", well_column),
        ("perturbation", treatment_column),
        ("treatment", treatment_column),
    ]
    for label, column in checks:
        if label not in lowered or column is None:
            continue
        count = _unique_count(frame, column)
        if count <= 1:
            warnings.append(
                f"Held-out {label} split is not meaningful because only {count} "
                f"{label} group is present."
            )


def _first_existing(frame: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    for column in candidates:
        if column in frame.columns:
            return str(column)
    return None


def _unique_values(frame: pd.DataFrame, column: str | None) -> set[str]:
    if column is None or column not in frame.columns or frame.empty:
        return set()
    values = frame[column].fillna("").astype(str).str.strip()
    return {value for value in values if value}


def _unique_count(frame: pd.DataFrame, column: str | None) -> int | None:
    if column is None:
        return None
    return len(_unique_values(frame, column))


def _group_count(frame: pd.DataFrame, columns: Iterable[str | None]) -> int | None:
    existing = [column for column in columns if column is not None and column in frame.columns]
    if not existing:
        return None
    if frame.empty:
        return 0
    values = frame[existing].fillna("").astype(str).agg("::".join, axis=1).str.strip(":")
    return int(values[values != ""].nunique())


def _rate(count: int | float, denominator: int | float) -> float:
    return float(count / denominator) if denominator else 0.0


def _safe_int(value: object) -> int:
    if pd.isna(value):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: object) -> float:
    if pd.isna(value):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _public_diagnostic_name(diagnostic: str) -> str:
    return "treatment" if diagnostic == "perturbation_treatment" else diagnostic


def _dedupe(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = str(value).strip()
        if value and value not in seen:
            output.append(value)
            seen.add(value)
    return output
