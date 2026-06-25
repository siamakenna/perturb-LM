"""JUMP Cell Painting pilot dataset helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

DATASET = "jump_pilot"
SOURCE_REPO_URL = "https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1"
EXPECTED_BATCH = "2020_11_04_CPJUMP1"
EXPECTED_PROFILE_KIND = "normalized_feature_select_negcon_batch"
EXPECTED_METADATA_FILES = [
    "JUMP-Target-1_compound_metadata.tsv",
    "JUMP-Target-1_compound_metadata_targets.tsv",
    "JUMP-Target-1_crispr_metadata.tsv",
    "JUMP-Target-1_orf_metadata.tsv",
    "experiment-metadata.tsv",
]
PROFILE_NAME_PATTERNS = [
    "normalized_feature_select_negcon_batch",
    "normalized_feature_select_negcon",
    "feature_select",
    "profile",
    "profiles",
]
LOCAL_ONLY_NOTE = (
    "Generated outputs and downloaded data are local-only artifacts and should not be committed."
)

BATCH_COLUMN_CANDIDATES = ["Metadata_Batch", "Metadata_batch", "Batch", "batch"]
PLATE_COLUMN_CANDIDATES = [
    "Metadata_Plate",
    "Metadata_plate",
    "Metadata_Assay_Plate_Barcode",
    "Assay_Plate_Barcode",
    "Metadata_Plate_Map_Name",
    "Plate_Map_Name",
    "plate",
]
WELL_COLUMN_CANDIDATES = ["Metadata_Well", "Metadata_well", "Metadata_Well_Position", "well"]
PERTURBATION_COLUMN_CANDIDATES = [
    "Metadata_broad_sample",
    "Metadata_pert_iname",
    "Metadata_pert_type",
    "Metadata_gene",
    "Metadata_pert_id",
    "Metadata_Perturbation",
    "Perturbation",
    "Metadata_treatment",
    "Metadata_Treatment",
]

SUPPORTED_TABLE_SUFFIXES = (
    ".csv",
    ".csv.gz",
    ".tsv",
    ".tsv.gz",
)


def audit_jump_pilot(
    data_root: Path | str = Path("data/raw/jump_pilot"),
    *,
    expected_batch: str = EXPECTED_BATCH,
    expected_profile_kind: str = EXPECTED_PROFILE_KIND,
) -> dict[str, Any]:
    """Inspect local CPJUMP1 pilot metadata and profile files."""

    root = Path(data_root)
    warnings: list[str] = []
    metadata_files = find_expected_metadata_files(root)
    profile_files = find_profile_files(root)
    found_metadata_names = {path.name for path in metadata_files}
    missing_expected_files = [
        name for name in EXPECTED_METADATA_FILES if name not in found_metadata_names
    ]

    if not root.exists():
        warnings.append(f"Local data root does not exist: {root}")
    if missing_expected_files:
        warnings.append("Missing expected metadata files: " + ", ".join(missing_expected_files))
    if not profile_files:
        warnings.append("No JUMP pilot profile files were found under the local data root.")
    if profile_files and not any(expected_profile_kind in path.name for path in profile_files):
        warnings.append(
            f"No profile filename contains expected profile kind '{expected_profile_kind}'."
        )

    readable_files: list[dict[str, Any]] = []
    for path in [*metadata_files, *profile_files]:
        summary = summarize_table_file(path, root)
        readable_files.append(summary)
        if not summary["readable"]:
            warnings.append(f"Could not read {summary['relative_path']}: {summary['error']}")

    detected_metadata_columns = sorted(
        {
            column
            for summary in readable_files
            for column in summary["metadata_columns"]
        }
    )
    detected_numeric_feature_columns = sorted(
        {
            column
            for summary in readable_files
            for column in summary["numeric_feature_columns"]
        }
    )
    ordered_columns = _ordered_columns(readable_files)
    likely_batch_column = find_first_column(ordered_columns, BATCH_COLUMN_CANDIDATES)
    likely_plate_column = find_first_column(ordered_columns, PLATE_COLUMN_CANDIDATES)
    likely_well_column = find_first_column(ordered_columns, WELL_COLUMN_CANDIDATES)
    likely_perturbation_columns = find_matching_columns(
        ordered_columns,
        PERTURBATION_COLUMN_CANDIDATES,
    )

    if not detected_metadata_columns:
        warnings.append("No Metadata_* columns were detected in readable files.")
    if not detected_numeric_feature_columns:
        warnings.append("No numeric feature columns were detected in readable files.")
    if likely_batch_column is None:
        warnings.append("No likely batch column was detected.")
    if likely_plate_column is None:
        warnings.append("No likely plate column was detected.")
    if likely_well_column is None:
        warnings.append("No likely well column was detected.")
    if not likely_perturbation_columns:
        warnings.append("No likely perturbation or treatment columns were detected.")

    return {
        "dataset": DATASET,
        "source_repo_url": SOURCE_REPO_URL,
        "local_data_root": str(root),
        "expected_batch": expected_batch,
        "expected_profile_kind": expected_profile_kind,
        "metadata_files_found": [_path_payload(path, root) for path in metadata_files],
        "profile_files_found": [_path_payload(path, root) for path in profile_files],
        "missing_expected_files": missing_expected_files,
        "readable_files": readable_files,
        "detected_metadata_columns": detected_metadata_columns,
        "detected_numeric_feature_columns": detected_numeric_feature_columns,
        "detected_metadata_column_count": len(detected_metadata_columns),
        "detected_numeric_feature_column_count": len(detected_numeric_feature_columns),
        "likely_batch_column": likely_batch_column,
        "likely_plate_column": likely_plate_column,
        "likely_well_column": likely_well_column,
        "likely_perturbation_treatment_columns": likely_perturbation_columns,
        "warnings": warnings,
        "local_only_note": LOCAL_ONLY_NOTE,
    }


def find_expected_metadata_files(data_root: Path | str) -> list[Path]:
    """Find expected CPJUMP1 metadata files by filename."""

    root = Path(data_root)
    if not root.exists():
        return []
    found: list[Path] = []
    for expected_name in EXPECTED_METADATA_FILES:
        matches = sorted(path for path in root.rglob(expected_name) if path.is_file())
        found.extend(matches)
    return found


def find_profile_files(data_root: Path | str) -> list[Path]:
    """Find likely CPJUMP1 profile tables by filename pattern."""

    root = Path(data_root)
    if not root.exists():
        return []
    paths: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        name = path.name.lower()
        if not _is_supported_table(path):
            continue
        if any(pattern in name for pattern in PROFILE_NAME_PATTERNS):
            paths.append(path)
    return paths


def summarize_table_file(
    path: Path,
    data_root: Path,
    *,
    sample_rows: int = 1000,
    chunksize: int = 10000,
) -> dict[str, Any]:
    """Return row, column, and schema hints for a readable CSV/TSV table."""

    payload: dict[str, Any] = {
        **_path_payload(path, data_root),
        "readable": False,
        "row_count": None,
        "column_count": None,
        "columns": [],
        "metadata_columns": [],
        "numeric_feature_columns": [],
        "error": None,
    }
    try:
        sep = _separator_for(path)
        sample = pd.read_csv(path, sep=sep, nrows=sample_rows)
        columns = [str(column) for column in sample.columns]
        payload["row_count"] = count_rows(path, sep=sep, columns=columns, chunksize=chunksize)
        payload["column_count"] = len(columns)
        payload["columns"] = columns
        payload["metadata_columns"] = [
            column for column in columns if column.startswith("Metadata_")
        ]
        if payload["kind"] == "profile":
            payload["numeric_feature_columns"] = [
                column
                for column in columns
                if not column.startswith("Metadata_")
                and pd.api.types.is_numeric_dtype(sample[column])
            ]
        payload["readable"] = True
    except EmptyDataError:
        payload["error"] = "empty table"
    except Exception as exc:  # pragma: no cover - defensive for varied local files
        payload["error"] = str(exc)
    return payload


def count_rows(path: Path, *, sep: str, columns: list[str], chunksize: int) -> int:
    """Count rows without loading all feature columns into memory."""

    if not columns:
        return 0
    first_column = columns[0]
    total = 0
    for chunk in pd.read_csv(path, sep=sep, usecols=[first_column], chunksize=chunksize):
        total += len(chunk)
    return total


def find_first_column(columns: list[str], candidates: list[str]) -> str | None:
    matches = find_matching_columns(columns, candidates)
    return matches[0] if matches else None


def find_matching_columns(columns: list[str], candidates: list[str]) -> list[str]:
    normalized_candidates = {_normalize_column_name(candidate) for candidate in candidates}
    matches: list[str] = []
    seen: set[str] = set()
    for column in columns:
        normalized = _normalize_column_name(column)
        if normalized in normalized_candidates and column not in seen:
            matches.append(column)
            seen.add(column)
    return matches


def _ordered_columns(readable_files: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    profile_summaries = [summary for summary in readable_files if summary["kind"] == "profile"]
    metadata_summaries = [summary for summary in readable_files if summary["kind"] == "metadata"]
    for summary in [*profile_summaries, *metadata_summaries]:
        for column in summary["columns"]:
            if column not in seen:
                columns.append(column)
                seen.add(column)
    return columns


def _path_payload(path: Path, data_root: Path) -> dict[str, str]:
    return {
        "path": str(path),
        "relative_path": _relative_path(path, data_root),
        "kind": "metadata" if path.name in EXPECTED_METADATA_FILES else "profile",
    }


def _relative_path(path: Path, data_root: Path) -> str:
    try:
        return str(path.relative_to(data_root))
    except ValueError:
        return str(path)


def _is_supported_table(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in SUPPORTED_TABLE_SUFFIXES)


def _separator_for(path: Path) -> str:
    name = path.name.lower()
    return "\t" if name.endswith((".tsv", ".tsv.gz")) else ","


def _normalize_column_name(column: object) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", str(column).strip())).strip("_").lower()
