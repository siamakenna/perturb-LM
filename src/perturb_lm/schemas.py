"""Column schemas and lightweight DataFrame validation."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


SITE_MANIFEST_COLUMNS = [
    "dataset",
    "site_id",
    "experiment",
    "plate",
    "well",
    "site",
    "cell_type",
    "perturbation_id",
    "perturbation_name",
    "perturbation_type",
    "condition_label",
    "concentration",
    "image_path_ch1",
    "image_path_ch2",
    "image_path_ch3",
    "image_path_ch4",
    "image_path_ch5",
    "image_path_ch6",
    "split",
]

PERTURBATION_MANIFEST_COLUMNS = [
    "dataset",
    "perturbation_key",
    "perturbation_id",
    "perturbation_name",
    "perturbation_type",
    "condition_label",
    "cell_type",
    "concentration",
    "n_sites",
    "n_wells",
    "n_plates",
    "n_experiments",
]

QUERY_TABLE_COLUMNS = [
    "query_id",
    "dataset",
    "query_text",
    "query_type",
    "positive_perturbation_keys",
    "positive_perturbation_ids",
    "condition_label",
    "cell_type",
    "split",
]

RETRIEVAL_RESULTS_COLUMNS = [
    "query_id",
    "dataset",
    "rank",
    "site_id",
    "perturbation_key",
    "perturbation_id",
    "score",
    "experiment",
    "plate",
    "well",
    "site",
    "cell_type",
    "condition_label",
]


def validation_errors(frame: pd.DataFrame, required_columns: Sequence[str], table_name: str) -> list[str]:
    """Return human-readable validation errors for a table."""

    errors: list[str] = []
    if frame.empty:
        errors.append(f"{table_name} must contain at least one row.")
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        errors.append(f"{table_name} is missing required columns: {', '.join(missing)}.")
    return errors


def validate_table(frame: pd.DataFrame, required_columns: Sequence[str], table_name: str) -> pd.DataFrame:
    """Validate required columns and non-empty content, returning the input frame."""

    errors = validation_errors(frame, required_columns, table_name)
    if errors:
        raise ValueError(" ".join(errors))
    return frame


def validate_site_manifest(frame: pd.DataFrame) -> pd.DataFrame:
    return validate_table(frame, SITE_MANIFEST_COLUMNS, "site manifest")


def validate_perturbation_manifest(frame: pd.DataFrame) -> pd.DataFrame:
    return validate_table(frame, PERTURBATION_MANIFEST_COLUMNS, "perturbation manifest")


def validate_query_table(frame: pd.DataFrame) -> pd.DataFrame:
    return validate_table(frame, QUERY_TABLE_COLUMNS, "query table")


def validate_retrieval_results(frame: pd.DataFrame) -> pd.DataFrame:
    return validate_table(frame, RETRIEVAL_RESULTS_COLUMNS, "retrieval results")
