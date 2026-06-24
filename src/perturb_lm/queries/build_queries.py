"""Build text queries from perturbation manifests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from perturb_lm.queries.templates import templates_for_dataset
from perturb_lm.schemas import validate_perturbation_manifest, validate_query_table


def build_queries(dataset: str, manifest: pd.DataFrame) -> pd.DataFrame:
    dataset = dataset.lower()
    validate_perturbation_manifest(manifest)
    templates = templates_for_dataset(dataset)
    rows: list[dict[str, str]] = []
    for _, row in manifest.iterrows():
        values = {column: _string(row.get(column)) for column in manifest.columns}
        for template_index, template in enumerate(templates, start=1):
            query_text = template.format(**values)
            rows.append(
                {
                    "query_id": f"{row['perturbation_key']}::template_{template_index}",
                    "dataset": dataset,
                    "query_text": query_text,
                    "query_type": f"{dataset}_template_{template_index}",
                    "positive_perturbation_keys": str(row["perturbation_key"]),
                    "positive_perturbation_ids": _string(row["perturbation_id"]),
                    "condition_label": _string(row["condition_label"]),
                    "cell_type": _string(row["cell_type"]),
                    "split": _string(row.get("split", "train")) or "train",
                }
            )
    queries = pd.DataFrame(rows)
    validate_query_table(queries)
    return queries


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _string(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)
