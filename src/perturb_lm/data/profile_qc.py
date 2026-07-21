"""Aggregate morphology-profile QC for local JUMP profile tables."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from perturb_lm.data.jump import (
    BATCH_COLUMN_CANDIDATES,
    CELL_PAINTING_FEATURE_PREFIXES,
    EXPECTED_PROFILE_KIND,
    LOCAL_ONLY_NOTE,
    PERTURBATION_COLUMN_CANDIDATES,
    PLATE_COLUMN_CANDIDATES,
    WELL_COLUMN_CANDIDATES,
    detect_jump_profile_schema,
    find_first_column,
    find_profile_files,
    read_jump_table,
)

DEFAULT_NEAR_ZERO_VARIANCE_THRESHOLD = 1e-12
DEFAULT_EXTREME_VALUE_THRESHOLD = 1e6
HARMONIZATION_POLICIES = {"strict_intersection", "primary_schema_only", "explicit_feature_map"}


@dataclass(frozen=True)
class ProfileQcOptions:
    """Thresholds used by aggregate profile QC."""

    near_zero_variance_threshold: float = DEFAULT_NEAR_ZERO_VARIANCE_THRESHOLD
    extreme_value_threshold: float = DEFAULT_EXTREME_VALUE_THRESHOLD
    harmonization_policy: str = "strict_intersection"


def run_jump_profile_qc(
    data_root: Path | str = Path("data/raw/jump_pilot"),
    *,
    profile_files: list[Path | str] | None = None,
    expected_profile_kind: str = EXPECTED_PROFILE_KIND,
    max_rows: int | None = None,
    options: ProfileQcOptions | None = None,
) -> dict[str, Any]:
    """Inspect local JUMP morphology profiles and return aggregate-only QC."""

    root = Path(data_root)
    paths = [Path(path) for path in profile_files] if profile_files else find_profile_files(root)
    if not paths:
        raise FileNotFoundError(f"No JUMP profile files found under {root}")
    preferred = [path for path in paths if expected_profile_kind in path.name]
    warnings: list[str] = []
    if preferred:
        paths = preferred
    else:
        warnings.append(
            f"No profile filename contains expected profile kind '{expected_profile_kind}'; "
            "using all discovered profile-like files."
        )

    frames = [read_jump_table(path, nrows=max_rows) for path in paths]
    report = profile_qc_from_frames(frames, options=options)
    report["profile_file_count"] = len(paths)
    report["warnings"] = [*warnings, *report["warnings"]]
    report["local_only_note"] = LOCAL_ONLY_NOTE
    return report


def profile_qc_from_frames(
    frames: list[pd.DataFrame],
    *,
    options: ProfileQcOptions | None = None,
) -> dict[str, Any]:
    """Build public-safe aggregate QC from in-memory profile tables."""

    if not frames:
        raise ValueError("At least one profile table is required for profile QC.")
    options = options or ProfileQcOptions()
    if options.harmonization_policy not in HARMONIZATION_POLICIES:
        raise ValueError(f"Unsupported harmonization policy: {options.harmonization_policy}")
    warnings: list[str] = []
    total_rows = int(sum(len(frame) for frame in frames))
    duplicate_column_count = int(sum(frame.columns.duplicated().sum() for frame in frames))

    feature_sets: list[set[str]] = []
    dtype_by_feature: dict[str, set[str]] = {}
    per_file_feature_counts: list[int] = []
    aggregate_feature_frame_parts: list[pd.DataFrame] = []
    harmonized_feature_frame_parts: list[pd.DataFrame] = []
    duplicate_profile_rows = 0
    replicate_frames: list[pd.DataFrame] = []
    numeric_feature_sets: list[set[str]] = []
    schema_rows: dict[str, int] = {}
    schema_files: dict[str, int] = {}

    for frame in frames:
        schema = detect_jump_profile_schema(frame)
        candidate_columns = _candidate_morphology_columns(frame)
        feature_sets.append(set(candidate_columns))
        numeric_feature_columns = [
            column for column in candidate_columns if _is_numeric_column(frame, column)
        ]
        numeric_feature_sets.append(set(numeric_feature_columns))
        schema_key = _schema_key(numeric_feature_columns)
        schema_rows[schema_key] = schema_rows.get(schema_key, 0) + int(len(frame))
        schema_files[schema_key] = schema_files.get(schema_key, 0) + 1
        per_file_feature_counts.append(len(numeric_feature_columns))
        for column in numeric_feature_columns:
            selected = frame[column]
            if isinstance(selected, pd.DataFrame):
                dtype_by_feature.setdefault(column, set()).update(
                    str(dtype) for dtype in selected.dtypes
                )
            else:
                dtype_by_feature.setdefault(column, set()).add(str(selected.dtype))
        numeric_features = _numeric_feature_frame(frame, numeric_feature_columns)
        if numeric_feature_columns:
            duplicate_profile_rows += int(numeric_features.duplicated().sum())
            aggregate_feature_frame_parts.append(numeric_features)
        replicate_frame = _replicate_columns(frame, schema)
        if not replicate_frame.empty:
            replicate_frames.append(replicate_frame)

    if not aggregate_feature_frame_parts:
        warnings.append("No numeric morphology profile columns were available for QC.")

    union_numeric_features = set().union(*numeric_feature_sets) if numeric_feature_sets else set()
    intersection_numeric_features = (
        set.intersection(*numeric_feature_sets) if numeric_feature_sets else set()
    )
    for frame, feature_set in zip(frames, numeric_feature_sets, strict=False):
        selected = _harmonized_feature_columns(
            feature_set,
            intersection_numeric_features,
            numeric_feature_sets[0] if numeric_feature_sets else set(),
            options.harmonization_policy,
        )
        if selected:
            harmonized_feature_frame_parts.append(_numeric_feature_frame(frame, sorted(selected)))
    harmonized_features = (
        pd.concat(harmonized_feature_frame_parts, ignore_index=True)
        if harmonized_feature_frame_parts
        else pd.DataFrame()
    )
    stats = _feature_stats(
        harmonized_features,
        near_zero_variance_threshold=options.near_zero_variance_threshold,
        extreme_value_threshold=options.extreme_value_threshold,
    )
    duplicate_feature_value_count = _duplicate_feature_value_count(harmonized_features)
    dtype_inconsistency_count = int(
        sum(1 for dtypes in dtype_by_feature.values() if len(dtypes) > 1)
    )
    schema_consistent = len({frozenset(feature_set) for feature_set in feature_sets}) == 1
    features_present_some_missing = 0
    if feature_sets:
        union = set().union(*feature_sets)
        intersection = set.intersection(*feature_sets) if len(feature_sets) > 1 else union
        features_present_some_missing = int(len(union - intersection))
    replicate_summary = _replicate_summary(replicate_frames)

    report = {
        "dataset": "jump_pilot",
        "profile_file_count": len(frames),
        "total_profile_rows": total_rows,
        "candidate_morphology_column_count": int(
            len(set().union(*feature_sets)) if feature_sets else 0
        ),
        "union_numeric_morphology_feature_count": int(len(union_numeric_features)),
        "intersection_numeric_morphology_feature_count": int(len(intersection_numeric_features)),
        "usable_numeric_morphology_column_count": int(stats["usable_numeric_feature_count"]),
        "missing_value_count": int(stats["missing_value_count"]),
        "infinite_value_count": int(stats["infinite_value_count"]),
        "all_missing_feature_count": int(stats["all_missing_feature_count"]),
        "zero_variance_feature_count": int(stats["zero_variance_feature_count"]),
        "near_zero_variance_feature_count": int(stats["near_zero_variance_feature_count"]),
        "duplicate_feature_column_count": int(
            duplicate_column_count + duplicate_feature_value_count
        ),
        "duplicate_feature_name_count": duplicate_column_count,
        "duplicate_feature_value_count": duplicate_feature_value_count,
        "duplicate_profile_row_count": int(duplicate_profile_rows),
        "extreme_value_count": int(stats["extreme_value_count"]),
        "schema_consistent_across_files": bool(schema_consistent),
        "features_present_in_some_files_missing_from_others_count": features_present_some_missing,
        "features_missing_from_at_least_one_file_count": features_present_some_missing,
        "dtype_inconsistency_count": dtype_inconsistency_count,
        "definition_or_naming_conflict_count": dtype_inconsistency_count,
        "schema_group_count": int(len(schema_files)),
        "schema_group_summary": _schema_group_summary(
            schema_files,
            schema_rows,
            numeric_feature_sets,
        ),
        "harmonization_policy": options.harmonization_policy,
        "per_file_numeric_feature_count_min": int(
            min(per_file_feature_counts) if per_file_feature_counts else 0
        ),
        "per_file_numeric_feature_count_max": int(
            max(per_file_feature_counts) if per_file_feature_counts else 0
        ),
        "replicate_group_summary": replicate_summary,
        "thresholds": {
            "near_zero_variance": options.near_zero_variance_threshold,
            "extreme_abs_value": options.extreme_value_threshold,
        },
        "warnings": warnings,
        "local_only_note": LOCAL_ONLY_NOTE,
    }
    if not schema_consistent:
        report["warnings"].append("Profile feature schemas differ across input files.")
    if options.harmonization_policy == "strict_intersection" and not schema_consistent:
        report["warnings"].append(
            "Strict-intersection harmonization is required before multi-batch benchmarking."
        )
    if dtype_inconsistency_count:
        report["warnings"].append(
            "One or more morphology feature columns have inconsistent dtypes."
        )
    if stats["infinite_value_count"]:
        report["warnings"].append("Infinite values were detected in morphology features.")
    if stats["all_missing_feature_count"]:
        report["warnings"].append("All-missing morphology features were detected.")
    if stats["zero_variance_feature_count"]:
        report["warnings"].append("Zero-variance morphology features were detected.")
    return report


def dashboard_safe_profile_qc_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Return a dashboard-safe QC payload with aggregate counts only."""

    safe_keys = [
        "dataset",
        "profile_file_count",
        "total_profile_rows",
        "candidate_morphology_column_count",
        "union_numeric_morphology_feature_count",
        "intersection_numeric_morphology_feature_count",
        "usable_numeric_morphology_column_count",
        "missing_value_count",
        "infinite_value_count",
        "all_missing_feature_count",
        "zero_variance_feature_count",
        "near_zero_variance_feature_count",
        "duplicate_feature_column_count",
        "duplicate_feature_name_count",
        "duplicate_feature_value_count",
        "duplicate_profile_row_count",
        "extreme_value_count",
        "schema_consistent_across_files",
        "features_present_in_some_files_missing_from_others_count",
        "features_missing_from_at_least_one_file_count",
        "dtype_inconsistency_count",
        "definition_or_naming_conflict_count",
        "schema_group_count",
        "schema_group_summary",
        "harmonization_policy",
        "per_file_numeric_feature_count_min",
        "per_file_numeric_feature_count_max",
        "replicate_group_summary",
        "thresholds",
        "warnings",
        "local_only_note",
    ]
    return {key: report[key] for key in safe_keys if key in report}


def write_profile_qc_outputs(report: dict[str, Any], out_dir: Path | str) -> dict[str, str]:
    """Write aggregate local QC outputs and return their paths."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    safe = dashboard_safe_profile_qc_summary(report)
    json_path = out / "jump_profile_qc_summary.json"
    dashboard_path = out / "jump_profile_qc_dashboard_safe.json"
    csv_path = out / "jump_profile_qc_summary.csv"
    markdown_path = out / "jump_profile_qc_report.md"
    harmonization_path = out / "jump_profile_harmonization_report.json"
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    dashboard_path.write_text(json.dumps(safe, indent=2) + "\n")
    pd.DataFrame([_flatten_for_csv(safe)]).to_csv(csv_path, index=False)
    markdown_path.write_text(_markdown_report(safe))
    harmonization_path.write_text(
        json.dumps(
            {
                "harmonization_policy": report.get("harmonization_policy"),
                "union_numeric_morphology_feature_count": report.get(
                    "union_numeric_morphology_feature_count"
                ),
                "intersection_numeric_morphology_feature_count": report.get(
                    "intersection_numeric_morphology_feature_count"
                ),
                "schema_group_count": report.get("schema_group_count"),
                "schema_group_summary": report.get("schema_group_summary"),
                "warnings": report.get("warnings", []),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return {
        "summary_json": str(json_path),
        "dashboard_safe_json": str(dashboard_path),
        "summary_csv": str(csv_path),
        "summary_markdown": str(markdown_path),
        "harmonization_json": str(harmonization_path),
    }


def _candidate_morphology_columns(frame: pd.DataFrame) -> list[str]:
    return [
        str(column)
        for column in frame.columns
        if str(column).startswith(CELL_PAINTING_FEATURE_PREFIXES)
    ]


def _is_numeric_column(frame: pd.DataFrame, column: str) -> bool:
    value = frame[column]
    if isinstance(value, pd.DataFrame):
        return all(
            pd.api.types.is_numeric_dtype(value.iloc[:, idx])
            for idx in range(value.shape[1])
        )
    return bool(pd.api.types.is_numeric_dtype(value))


def _numeric_feature_frame(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if not columns:
        return pd.DataFrame(index=frame.index)
    deduped = frame.loc[:, columns]
    if isinstance(deduped, pd.Series):
        deduped = deduped.to_frame()
    deduped = deduped.loc[:, ~deduped.columns.duplicated()]
    return deduped.apply(pd.to_numeric, errors="coerce")


def _feature_stats(
    features: pd.DataFrame,
    *,
    near_zero_variance_threshold: float,
    extreme_value_threshold: float,
) -> dict[str, int]:
    if features.empty:
        return {
            "usable_numeric_feature_count": 0,
            "missing_value_count": 0,
            "infinite_value_count": 0,
            "all_missing_feature_count": 0,
            "zero_variance_feature_count": 0,
            "near_zero_variance_feature_count": 0,
            "extreme_value_count": 0,
        }
    values = features.to_numpy(dtype=float)
    infinite_mask = np.isinf(values)
    missing_mask = pd.isna(features).to_numpy() | infinite_mask
    finite_features = features.replace([np.inf, -np.inf], np.nan)
    variances = finite_features.var(axis=0, skipna=True, ddof=0)
    all_missing = finite_features.isna().all(axis=0)
    zero_variance = (variances == 0) & ~all_missing
    near_zero = (variances > 0) & (variances <= near_zero_variance_threshold)
    invalid = all_missing | zero_variance | near_zero
    return {
        "usable_numeric_feature_count": int((~invalid).sum()),
        "missing_value_count": int(missing_mask.sum()),
        "infinite_value_count": int(infinite_mask.sum()),
        "all_missing_feature_count": int(all_missing.sum()),
        "zero_variance_feature_count": int(zero_variance.sum()),
        "near_zero_variance_feature_count": int(near_zero.sum()),
        "extreme_value_count": int(
            (np.abs(values[~np.isnan(values)]) > extreme_value_threshold).sum()
        ),
    }


def _duplicate_feature_value_count(features: pd.DataFrame) -> int:
    if features.empty or features.shape[1] < 2:
        return 0
    comparable = features.replace([np.inf, -np.inf], np.nan)
    transposed = comparable.T
    return int(transposed.duplicated().sum())


def _schema_key(columns: list[str]) -> str:
    digest = json.dumps(sorted(columns), separators=(",", ":"))
    import hashlib

    return hashlib.sha256(digest.encode("utf-8")).hexdigest()


def _harmonized_feature_columns(
    feature_set: set[str],
    intersection: set[str],
    primary_schema: set[str],
    policy: str,
) -> set[str]:
    if policy == "strict_intersection":
        return set(intersection)
    if policy == "primary_schema_only":
        return set(feature_set).intersection(primary_schema)
    if policy == "explicit_feature_map":
        raise ValueError("explicit_feature_map requires a feature map and is not implicit.")
    raise ValueError(f"Unsupported harmonization policy: {policy}")


def _schema_group_summary(
    schema_files: dict[str, int],
    schema_rows: dict[str, int],
    feature_sets: list[set[str]],
) -> list[dict[str, int]]:
    unique_feature_counts = sorted(
        {
            _schema_key(sorted(feature_set)): len(feature_set)
            for feature_set in feature_sets
        }.items()
    )
    feature_count_by_key = dict(unique_feature_counts)
    rows = []
    for index, key in enumerate(sorted(schema_files), start=1):
        rows.append(
            {
                "schema_group": index,
                "file_count": int(schema_files[key]),
                "row_count": int(schema_rows[key]),
                "numeric_feature_count": int(feature_count_by_key.get(key, 0)),
            }
        )
    return rows


def _replicate_columns(frame: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    columns = {
        "treatment": find_first_column(frame.columns, PERTURBATION_COLUMN_CANDIDATES),
        "plate": schema.get("likely_plate_column")
        or find_first_column(frame.columns, PLATE_COLUMN_CANDIDATES),
        "well": schema.get("likely_well_column")
        or find_first_column(frame.columns, WELL_COLUMN_CANDIDATES),
        "batch": schema.get("likely_batch_column")
        or find_first_column(frame.columns, BATCH_COLUMN_CANDIDATES),
    }
    available = {public: column for public, column in columns.items() if column in frame.columns}
    if not available:
        return pd.DataFrame(index=frame.index)
    return pd.DataFrame({public: frame[column].astype(str) for public, column in available.items()})


def _replicate_summary(frames: list[pd.DataFrame]) -> dict[str, Any]:
    if not frames:
        return {
            "available_groupings": [],
            "warnings": ["No replicate label columns were available."],
        }
    combined = pd.concat(frames, ignore_index=True)
    summary: dict[str, Any] = {"available_groupings": sorted(combined.columns.tolist())}
    for grouping in [
        ["treatment"],
        ["plate"],
        ["well"],
        ["treatment", "plate"],
        ["treatment", "well"],
    ]:
        if not set(grouping).issubset(combined.columns):
            continue
        sizes = combined.groupby(grouping, dropna=False).size()
        name = "_by_".join(grouping)
        summary[name] = {
            "group_count": int(len(sizes)),
            "replicate_count_min": int(sizes.min()) if len(sizes) else 0,
            "replicate_count_median": float(sizes.median()) if len(sizes) else 0.0,
            "replicate_count_max": int(sizes.max()) if len(sizes) else 0,
        }
    return summary


def _flatten_for_csv(payload: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            flattened[key] = json.dumps(value, sort_keys=True)
        else:
            flattened[key] = value
    return flattened


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# JUMP Profile QC Summary",
        "",
        (
            "This aggregate report is public-safe by construction and excludes row-level "
            "values, local paths, filenames, raw identifiers, profile IDs, and feature names."
        ),
        "",
        "## Counts",
        "",
    ]
    for key, value in payload.items():
        if key in {"replicate_group_summary", "thresholds", "warnings", "local_only_note"}:
            continue
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Replicates",
            "",
            "```json",
            json.dumps(payload.get("replicate_group_summary", {}), indent=2),
            "```",
            "",
        ]
    )
    warnings = payload.get("warnings", [])
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    lines.append(str(payload.get("local_only_note", LOCAL_ONLY_NOTE)))
    return "\n".join(lines) + "\n"
