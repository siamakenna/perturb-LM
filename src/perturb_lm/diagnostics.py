"""Leakage diagnostics for Phase 1 parser and split validation."""

from __future__ import annotations

import pandas as pd

from perturb_lm.data.rxrx_common import make_perturbation_key
from perturb_lm.schemas import validate_query_table, validate_site_manifest


def query_positive_leakage_diagnostics(
    queries: pd.DataFrame,
    site_manifest: pd.DataFrame,
) -> pd.DataFrame:
    """Report whether query-positive perturbations span batches, plates, or splits."""

    validate_query_table(queries)
    validate_site_manifest(site_manifest)
    manifest = _with_perturbation_key(site_manifest)
    rows: list[dict[str, object]] = []
    for _, query in queries.iterrows():
        positive_keys = _positive_set(query.get("positive_perturbation_keys", ""))
        positive_ids = _positive_set(query.get("positive_perturbation_ids", ""))
        matches = manifest[
            manifest["perturbation_key"].astype(str).isin(positive_keys)
            | manifest["perturbation_id"].astype(str).isin(positive_ids)
        ]
        batches = _unique_values(matches, "experiment")
        plates = _unique_values(matches, "plate")
        splits = _unique_values(matches, "split")
        query_split = str(query.get("split", "") or "")
        rows.append(
            {
                "query_id": str(query["query_id"]),
                "dataset": str(query.get("dataset", "")),
                "query_split": query_split,
                "n_positive_sites": int(len(matches)),
                "n_positive_batches": len(batches),
                "n_positive_plates": len(plates),
                "n_positive_splits": len(splits),
                "positive_batches": "|".join(batches),
                "positive_plates": "|".join(plates),
                "positive_splits": "|".join(splits),
                "positive_in_query_split": bool(query_split and query_split in splits),
                "positive_in_other_split": bool(query_split and any(split != query_split for split in splits)),
                "positive_cross_batch": len(batches) > 1,
                "positive_cross_plate": len(plates) > 1,
                "positive_cross_split": len(splits) > 1,
                "missing_positive_metadata": bool(matches.empty),
            }
        )
    return pd.DataFrame(rows)


def summarize_leakage_diagnostics(diagnostics: pd.DataFrame) -> pd.DataFrame:
    """Summarize query-level leakage diagnostics as metric/value rows."""

    if diagnostics.empty:
        return pd.DataFrame(
            [
                {"metric": "n_queries", "value": 0},
                {"metric": "queries_with_positive_cross_batch", "value": 0},
                {"metric": "queries_with_positive_cross_plate", "value": 0},
                {"metric": "queries_with_positive_cross_split", "value": 0},
                {"metric": "queries_with_missing_positive_metadata", "value": 0},
            ]
        )
    return pd.DataFrame(
        [
            {"metric": "n_queries", "value": int(len(diagnostics))},
            {
                "metric": "queries_with_positive_cross_batch",
                "value": int(diagnostics["positive_cross_batch"].sum()),
            },
            {
                "metric": "queries_with_positive_cross_plate",
                "value": int(diagnostics["positive_cross_plate"].sum()),
            },
            {
                "metric": "queries_with_positive_cross_split",
                "value": int(diagnostics["positive_cross_split"].sum()),
            },
            {
                "metric": "queries_with_positive_in_other_split",
                "value": int(diagnostics["positive_in_other_split"].sum()),
            },
            {
                "metric": "queries_with_missing_positive_metadata",
                "value": int(diagnostics["missing_positive_metadata"].sum()),
            },
        ]
    )


def _with_perturbation_key(site_manifest: pd.DataFrame) -> pd.DataFrame:
    work = site_manifest.copy()
    if "perturbation_key" not in work.columns:
        work["perturbation_key"] = [
            make_perturbation_key(
                row.dataset,
                row.perturbation_id,
                row.perturbation_name,
                row.cell_type,
                row.condition_label,
                row.concentration,
            )
            for row in work.itertuples(index=False)
        ]
    return work


def _positive_set(value: object) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    if pd.isna(value):
        return set()
    return {part.strip() for part in str(value).split("|") if part.strip()}


def _unique_values(frame: pd.DataFrame, column: str) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    values = frame[column].fillna("").astype(str).str.strip()
    return sorted(value for value in values.unique().tolist() if value)
