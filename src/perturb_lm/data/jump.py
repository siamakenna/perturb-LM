"""JUMP Cell Painting pilot dataset helpers."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError

from perturb_lm.retrieval.embeddings import EmbeddingLoadResult, normalize_embeddings
from perturb_lm.retrieval.index import build_sklearn_index, save_sklearn_index

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
CELL_PAINTING_FEATURE_PREFIXES = ("Cells_", "Cytoplasm_", "Nuclei_", "Image_")
LOCAL_ONLY_NOTE = (
    "Generated outputs and downloaded data are local-only artifacts and should not be committed."
)

BATCH_COLUMN_CANDIDATES = [
    "Metadata_Batch",
    "Metadata_batch",
    "Metadata_Inferred_Batch",
    "Batch",
    "batch",
    "inferred_batch",
]
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
NON_FEATURE_COLUMNS = {
    "profile_id",
    "source_profile_file",
    "source_profile_row",
    "row_index",
}

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
    inferred_batches = sorted(
        {
            inferred
            for path in profile_files
            if (inferred := infer_batch_from_profile_path(path)) is not None
        }
    )
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
    if likely_batch_column is None and inferred_batches:
        likely_batch_column = "Metadata_Inferred_Batch"
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
    elif likely_batch_column == "Metadata_Inferred_Batch":
        warnings.append(
            "No batch column was detected in profile tables; inferred batch from profile paths."
        )
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
        "inferred_batches": inferred_batches,
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


def load_jump_profile_tables(
    data_root: Path | str = Path("data/raw/jump_pilot"),
    *,
    profile_files: list[Path | str] | None = None,
    expected_profile_kind: str = EXPECTED_PROFILE_KIND,
    max_rows: int | None = None,
) -> tuple[pd.DataFrame, list[Path], list[str]]:
    """Load discovered or explicit JUMP pilot profile tables."""

    root = Path(data_root)
    warnings: list[str] = []
    paths = [Path(path) for path in profile_files] if profile_files else find_profile_files(root)
    if not paths:
        raise FileNotFoundError(f"No JUMP profile files found under {root}")

    preferred = [path for path in paths if expected_profile_kind in path.name]
    if preferred:
        paths = preferred
    else:
        warnings.append(
            f"No profile filename contains expected profile kind '{expected_profile_kind}'; "
            "using all discovered profile-like files."
        )

    frames: list[pd.DataFrame] = []
    rows_remaining = max_rows
    for path in paths:
        nrows = rows_remaining if rows_remaining is not None else None
        frame = read_jump_table(path, nrows=nrows).copy()
        extra_columns: dict[str, Any] = {
            "source_profile_file": str(path),
            "source_profile_row": range(len(frame)),
        }
        batch_column = find_first_column(
            [str(column) for column in frame.columns],
            BATCH_COLUMN_CANDIDATES,
        )
        if batch_column is None:
            inferred_batch = infer_batch_from_profile_path(path)
            if inferred_batch:
                extra_columns["Metadata_Inferred_Batch"] = inferred_batch
        extras = pd.DataFrame(extra_columns, index=frame.index)
        frame = pd.concat([frame, extras], axis=1)
        frames.append(frame)
        if rows_remaining is not None:
            rows_remaining -= len(frame)
            if rows_remaining <= 0:
                break

    profiles = pd.concat(frames, ignore_index=True)
    return profiles, paths[: len(frames)], warnings


def read_jump_table(path: Path | str, *, nrows: int | None = None) -> pd.DataFrame:
    """Read a JUMP CSV/TSV table, including gzip-compressed variants."""

    path = Path(path)
    return pd.read_csv(path, sep=_separator_for(path), nrows=nrows)


def infer_batch_from_profile_path(path: Path | str) -> str | None:
    """Infer a CPJUMP1 batch name from a profile file path."""

    parts = [part for part in Path(path).parts if part]
    for index, part in enumerate(parts[:-1]):
        if part.lower() == "profiles":
            return parts[index + 1]
    for part in parts:
        if re.fullmatch(r"\d{4}_\d{2}_\d{2}_CPJUMP\d+", part):
            return part
    return None


def detect_jump_profile_schema(frame: pd.DataFrame) -> dict[str, Any]:
    """Detect profile metadata, feature, and likely biological label columns."""

    columns = [str(column) for column in frame.columns]
    metadata_columns = [column for column in columns if column.startswith("Metadata_")]
    likely_batch_column = find_first_column(columns, BATCH_COLUMN_CANDIDATES)
    likely_plate_column = find_first_column(columns, PLATE_COLUMN_CANDIDATES)
    likely_well_column = find_first_column(columns, WELL_COLUMN_CANDIDATES)
    likely_perturbation_columns = find_matching_columns(
        columns,
        PERTURBATION_COLUMN_CANDIDATES,
    )
    numeric_feature_columns, feature_warnings = detect_numeric_feature_columns(frame)

    warnings = [*feature_warnings]
    if not metadata_columns:
        warnings.append("No Metadata_* columns were detected.")
    if likely_batch_column is None:
        warnings.append("No likely batch column was detected.")
    if likely_plate_column is None:
        warnings.append("No likely plate column was detected.")
    if likely_well_column is None:
        warnings.append("No likely well column was detected.")
    if not likely_perturbation_columns:
        warnings.append("No likely perturbation or treatment columns were detected.")

    return {
        "metadata_columns": metadata_columns,
        "numeric_feature_columns": numeric_feature_columns,
        "likely_batch_column": likely_batch_column,
        "likely_plate_column": likely_plate_column,
        "likely_well_column": likely_well_column,
        "likely_perturbation_treatment_columns": likely_perturbation_columns,
        "warnings": warnings,
    }


def detect_numeric_feature_columns(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Detect numeric Cell Painting features without treating metadata as features."""

    excluded = {
        _normalize_column_name(column)
        for column in [
            *NON_FEATURE_COLUMNS,
            *BATCH_COLUMN_CANDIDATES,
            *PLATE_COLUMN_CANDIDATES,
            *WELL_COLUMN_CANDIDATES,
            *PERTURBATION_COLUMN_CANDIDATES,
        ]
    }
    numeric = [
        str(column)
        for column in frame.columns
        if not str(column).startswith("Metadata_")
        and _normalize_column_name(column) not in excluded
        and pd.api.types.is_numeric_dtype(frame[column])
    ]
    cell_painting = [
        column for column in numeric if column.startswith(CELL_PAINTING_FEATURE_PREFIXES)
    ]
    if cell_painting:
        return cell_painting, []
    if numeric:
        return numeric, [
            "No Cell Painting-prefixed numeric columns were detected; "
            "using all non-metadata numeric columns as profile features."
        ]
    return [], ["No numeric profile feature columns were detected."]


def add_jump_profile_ids(frame: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    """Add stable profile IDs built from batch, plate, well, and source-row context."""

    work = frame.copy()
    profile_ids: list[str] = []
    batch_column = schema.get("likely_batch_column")
    plate_column = schema.get("likely_plate_column")
    well_column = schema.get("likely_well_column")
    for row_index, row in work.iterrows():
        batch = _clean_label(row.get(batch_column, "")) if batch_column else ""
        plate = _clean_label(row.get(plate_column, "")) if plate_column else ""
        well = _clean_label(row.get(well_column, "")) if well_column else ""
        parts = [DATASET, batch or "NA", plate or "NA", well or "NA", str(row_index)]
        profile_ids.append("::".join(part.replace(" ", "_") for part in parts))
    work["profile_id"] = profile_ids
    return work


def build_jump_profile_index(
    data_root: Path | str = Path("data/raw/jump_pilot"),
    *,
    out_dir: Path | str = Path("outputs/jump_pilot_index"),
    profile_files: list[Path | str] | None = None,
    expected_profile_kind: str = EXPECTED_PROFILE_KIND,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Build and save a sklearn cosine index from local JUMP profile tables."""

    root = Path(data_root)
    out_dir = Path(out_dir)
    profiles, loaded_paths, load_warnings = load_jump_profile_tables(
        root,
        profile_files=profile_files,
        expected_profile_kind=expected_profile_kind,
        max_rows=max_rows,
    )
    schema = detect_jump_profile_schema(profiles)
    warnings = [*load_warnings, *schema["warnings"]]
    feature_columns = schema["numeric_feature_columns"]
    if not feature_columns:
        raise ValueError("Cannot build JUMP profile index without numeric feature columns.")

    indexed_profiles = add_jump_profile_ids(profiles, schema)
    feature_matrix = (
        indexed_profiles[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
        .to_numpy(dtype=float)
    )
    embeddings = normalize_embeddings(feature_matrix)
    profile_metadata = _profile_metadata_frame(indexed_profiles, schema)
    result = EmbeddingLoadResult(
        ids=indexed_profiles["profile_id"].astype(str).tolist(),
        embeddings=embeddings,
        manifest=profile_metadata,
        matched=len(indexed_profiles),
        unmatched=0,
    )
    saved = save_sklearn_index(result, out_dir, dataset=DATASET, id_column="profile_id")
    profile_metadata_path = out_dir / "profile_metadata.csv"
    profile_metadata.to_csv(profile_metadata_path, index=False)

    metadata = {
        "dataset": DATASET,
        "local_data_root": str(root),
        "input_profile_file_path": str(loaded_paths[0]) if loaded_paths else "",
        "input_profile_file_paths": [str(path) for path in loaded_paths],
        "number_of_rows": int(len(indexed_profiles)),
        "number_of_numeric_feature_columns": int(len(feature_columns)),
        "number_of_metadata_columns": int(len(schema["metadata_columns"])),
        "detected_metadata_columns": schema["metadata_columns"],
        "detected_numeric_feature_columns": feature_columns,
        "detected_batch_column": schema["likely_batch_column"],
        "detected_plate_column": schema["likely_plate_column"],
        "detected_well_column": schema["likely_well_column"],
        "detected_perturbation_treatment_columns": schema[
            "likely_perturbation_treatment_columns"
        ],
        "profile_id_column": "profile_id",
        "profile_metadata_path": str(profile_metadata_path),
        "index_type": "sklearn-nearest-neighbors",
        "distance_metric": "cosine",
        "output_directory": str(out_dir),
        "warnings": warnings,
        "local_only_note": LOCAL_ONLY_NOTE,
        **result.summary(),
    }
    saved.metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def run_jump_profile_diagnostics(
    data_root: Path | str = Path("data/raw/jump_pilot"),
    *,
    profile_files: list[Path | str] | None = None,
    expected_profile_kind: str = EXPECTED_PROFILE_KIND,
    top_k: list[int] | None = None,
    max_rows: int | None = None,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Run same-label nearest-neighbor diagnostics for JUMP profiles."""

    top_k = sorted(set(top_k or [1, 5, 10]))
    if not top_k or min(top_k) <= 0:
        raise ValueError("top_k must contain positive integers.")

    root = Path(data_root)
    profiles, loaded_paths, load_warnings = load_jump_profile_tables(
        root,
        profile_files=profile_files,
        expected_profile_kind=expected_profile_kind,
        max_rows=max_rows,
    )
    schema = detect_jump_profile_schema(profiles)
    warnings = [*load_warnings, *schema["warnings"]]
    feature_columns = schema["numeric_feature_columns"]
    if not feature_columns:
        raise ValueError("Cannot run JUMP profile diagnostics without numeric feature columns.")

    indexed_profiles = add_jump_profile_ids(profiles, schema)
    feature_matrix = (
        indexed_profiles[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
        .to_numpy(dtype=float)
    )
    embeddings = normalize_embeddings(feature_matrix)
    if len(indexed_profiles) < 2:
        raise ValueError("At least two profile rows are required for nearest-neighbor diagnostics.")

    index = build_sklearn_index(embeddings)
    max_k = min(max(top_k), len(indexed_profiles) - 1)
    distances, neighbor_indices = index.kneighbors(embeddings, n_neighbors=max_k + 1)
    query_neighbors = _drop_self_neighbors(neighbor_indices, distances, max_k)

    diagnostic_columns = _diagnostic_columns(schema)
    if not diagnostic_columns:
        warnings.append("No batch, plate, well, or perturbation columns were available.")

    rng = np.random.default_rng(seed)
    per_query_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for label_name, column in diagnostic_columns:
        labels = indexed_profiles[column].map(_clean_label).to_numpy(dtype=str)
        shuffled_labels = rng.permutation(labels)
        base_note = _diagnostic_base_note(label_name, labels, column)
        if base_note and base_note not in warnings:
            warnings.append(base_note)
        label_rows = _same_label_diagnostic_rows(
            indexed_profiles["profile_id"].astype(str).tolist(),
            labels,
            shuffled_labels,
            query_neighbors,
            label_name=label_name,
            label_column=column,
            top_k=top_k,
        )
        per_query_rows.extend(label_rows)
        summary_rows.extend(
            _summarize_same_label_rows(
                label_rows,
                label_name,
                column,
                top_k,
                base_note=base_note,
            )
        )

    metadata = {
        "dataset": DATASET,
        "local_data_root": str(root),
        "input_profile_file_path": str(loaded_paths[0]) if loaded_paths else "",
        "input_profile_file_paths": [str(path) for path in loaded_paths],
        "number_of_rows": int(len(indexed_profiles)),
        "number_of_numeric_feature_columns": int(len(feature_columns)),
        "number_of_metadata_columns": int(len(schema["metadata_columns"])),
        "detected_batch_column": schema["likely_batch_column"],
        "detected_plate_column": schema["likely_plate_column"],
        "detected_well_column": schema["likely_well_column"],
        "detected_perturbation_treatment_columns": schema[
            "likely_perturbation_treatment_columns"
        ],
        "diagnostic_columns": [
            {"diagnostic": label_name, "column": column}
            for label_name, column in diagnostic_columns
        ],
        "top_k": top_k,
        "index_type": "sklearn-nearest-neighbors",
        "distance_metric": "cosine",
        "warnings": warnings,
        "local_only_note": LOCAL_ONLY_NOTE,
    }
    return pd.DataFrame(per_query_rows), pd.DataFrame(summary_rows), metadata


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
            payload["numeric_feature_columns"], _ = detect_numeric_feature_columns(sample)
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


def _profile_metadata_frame(indexed_profiles: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    columns = [
        "profile_id",
        "source_profile_file",
        "source_profile_row",
        *schema["metadata_columns"],
    ]
    for column in [
        schema["likely_batch_column"],
        schema["likely_plate_column"],
        schema["likely_well_column"],
        *schema["likely_perturbation_treatment_columns"],
    ]:
        if column and column not in columns:
            columns.append(column)
    existing = [column for column in columns if column in indexed_profiles.columns]
    return indexed_profiles[existing].copy()


def _diagnostic_columns(schema: dict[str, Any]) -> list[tuple[str, str]]:
    diagnostics: list[tuple[str, str]] = []
    if schema["likely_batch_column"]:
        diagnostics.append(("batch", schema["likely_batch_column"]))
    if schema["likely_plate_column"]:
        diagnostics.append(("plate", schema["likely_plate_column"]))
    if schema["likely_well_column"]:
        diagnostics.append(("well", schema["likely_well_column"]))
    perturbation_columns = schema["likely_perturbation_treatment_columns"]
    if perturbation_columns:
        diagnostics.append(("perturbation_treatment", perturbation_columns[0]))
    return diagnostics


def _drop_self_neighbors(
    neighbor_indices: np.ndarray,
    distances: np.ndarray,
    top_k: int,
) -> list[list[dict[str, float | int]]]:
    rows: list[list[dict[str, float | int]]] = []
    for query_index, neighbors in enumerate(neighbor_indices):
        query_rows: list[dict[str, float | int]] = []
        for distance, candidate_index in zip(distances[query_index], neighbors, strict=False):
            if int(candidate_index) == query_index:
                continue
            query_rows.append(
                {
                    "candidate_index": int(candidate_index),
                    "distance": float(distance),
                    "score": 1.0 - float(distance),
                }
            )
            if len(query_rows) == top_k:
                break
        rows.append(query_rows)
    return rows


def _same_label_diagnostic_rows(
    profile_ids: list[str],
    labels: np.ndarray,
    shuffled_labels: np.ndarray,
    query_neighbors: list[list[dict[str, float | int]]],
    *,
    label_name: str,
    label_column: str,
    top_k: list[int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query_index, profile_id in enumerate(profile_ids):
        label = _clean_label(labels[query_index])
        positives = labels == label
        positives[query_index] = False
        if _is_missing_label(label):
            positives[:] = False
        shuffled_label = _clean_label(shuffled_labels[query_index])
        shuffled_positives = shuffled_labels == shuffled_label
        shuffled_positives[query_index] = False
        if _is_missing_label(shuffled_label):
            shuffled_positives[:] = False

        row: dict[str, Any] = {
            "profile_id": profile_id,
            "diagnostic": label_name,
            "label_column": label_column,
            "label": label,
            "n_positive_candidates": int(positives.sum()),
        }
        neighbors = query_neighbors[query_index]
        for k in top_k:
            top = neighbors[:k]
            top_indices = [int(candidate["candidate_index"]) for candidate in top]
            row[f"same_{label_name}_at_{k}"] = bool(
                top_indices and positives[np.array(top_indices)].any()
            )
            row[f"random_same_{label_name}_at_{k}"] = _random_hit_probability(
                len(labels) - 1,
                int(positives.sum()),
                k,
            )
            row[f"shuffled_same_{label_name}_at_{k}"] = bool(
                top_indices and shuffled_positives[np.array(top_indices)].any()
            )
        rows.append(row)
    return rows


def _summarize_same_label_rows(
    rows: list[dict[str, Any]],
    label_name: str,
    label_column: str,
    top_k: list[int],
    *,
    base_note: str = "",
) -> list[dict[str, Any]]:
    if not rows:
        return []
    frame = pd.DataFrame(rows)
    evaluable = frame["n_positive_candidates"] > 0
    n_evaluable = int(evaluable.sum())
    n_positive_matches = int(frame["n_positive_candidates"].sum())
    summary_rows: list[dict[str, Any]] = []
    for k in top_k:
        for prefix in ["same", "random_same", "shuffled_same"]:
            column = f"{prefix}_{label_name}_at_{k}"
            value_all = float(frame[column].mean()) if len(frame) else 0.0
            value_evaluable = float(frame.loc[evaluable, column].mean()) if n_evaluable else 0.0
            note = _diagnostic_summary_note(
                label_name,
                label_column,
                n_queries=int(len(frame)),
                n_evaluable=n_evaluable,
                base_note=base_note,
            )
            summary_rows.append(
                {
                    "diagnostic": label_name,
                    "metric": column,
                    "value": value_all,
                    "value_all_queries": value_all,
                    "value_evaluable_queries": value_evaluable,
                    "n_queries": int(len(frame)),
                    "n_evaluable_queries": n_evaluable,
                    "n_positive_matches": n_positive_matches,
                    "k": k,
                    "label_column": label_column,
                    "warning": note,
                }
            )
    return summary_rows


def _diagnostic_base_note(label_name: str, labels: np.ndarray, label_column: str) -> str:
    unique_labels = sorted(
        {_clean_label(value) for value in labels if not _is_missing_label(value)}
    )
    if label_name == "plate" and len(unique_labels) == 1:
        return (
            "Same-plate diagnostics are not informative because all rows come from "
            f"one plate in {label_column}."
        )
    if label_name == "batch" and len(unique_labels) == 1:
        return (
            "Same-batch diagnostics are not informative because all rows come from "
            f"one batch in {label_column}."
        )
    return ""


def _diagnostic_summary_note(
    label_name: str,
    label_column: str,
    *,
    n_queries: int,
    n_evaluable: int,
    base_note: str,
) -> str:
    notes = []
    if base_note:
        notes.append(base_note)
    if n_evaluable == 0:
        notes.append(f"No queries have same-label positive candidates for {label_column}.")
    elif n_evaluable < n_queries:
        notes.append(
            f"Only {n_evaluable} of {n_queries} queries are evaluable for {label_column}; "
            "prefer value_evaluable_queries for replicate-sensitive interpretation."
        )
    if label_name == "perturbation_treatment":
        notes.append(f"Same-treatment matching uses label column {label_column}.")
    return " ".join(notes)


def _random_hit_probability(num_candidates: int, num_positives: int, k: int) -> float:
    if num_candidates <= 0 or num_positives <= 0 or k <= 0:
        return 0.0
    k = min(k, num_candidates)
    num_negatives = num_candidates - num_positives
    if k > num_negatives:
        return 1.0
    log_no_hit = (
        math.lgamma(num_negatives + 1)
        - math.lgamma(k + 1)
        - math.lgamma(num_negatives - k + 1)
        - math.lgamma(num_candidates + 1)
        + math.lgamma(k + 1)
        + math.lgamma(num_candidates - k + 1)
    )
    return float(1.0 - math.exp(log_no_hit))


def _clean_label(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _is_missing_label(value: object) -> bool:
    return _clean_label(value).lower() in {"", "nan", "none", "null", "<na>"}


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
