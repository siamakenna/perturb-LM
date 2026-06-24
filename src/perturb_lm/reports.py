"""Markdown reporting helpers for Phase 1 outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def make_phase1_report(
    *,
    dataset: str,
    queries: pd.DataFrame,
    site_manifest: pd.DataFrame,
    perturbation_results: pd.DataFrame,
    metrics: pd.DataFrame,
    out_path: Path,
    mode: str = "unknown",
    fixture: bool = False,
) -> Path:
    perturbations = (
        site_manifest["perturbation_key"].nunique()
        if "perturbation_key" in site_manifest.columns
        else perturbation_results["perturbation_key"].nunique()
    )
    lines = [
        f"# Perturb LM Phase 1 Report: {dataset}",
        "",
        f"- Dataset: `{dataset}`",
        f"- Retrieval mode: `{mode}`",
        f"- Number of queries: {len(queries)}",
        f"- Number of sites: {len(site_manifest)}",
        f"- Number of perturbations: {perturbations}",
        f"- Fixture outputs: {'yes' if fixture else 'no'}",
        "",
        "Phase 1 establishes the working retrieval pipeline, perturbation-level aggregation, metrics, and baselines. It does not prove biological retrieval without real RxRx data, real embeddings, batch-aware splits, and later VLM/alignment baselines.",
        "",
        "## Metrics",
        "",
        _markdown_table(metrics),
        "",
        "## Top Retrieval Examples",
        "",
    ]
    for query_id, group in perturbation_results.sort_values(["query_id", "rank"]).groupby("query_id"):
        query_text = queries.loc[queries["query_id"].astype(str) == str(query_id), "query_text"]
        lines.append(f"### {query_id}")
        if len(query_text):
            lines.append(f"Query: {query_text.iloc[0]}")
        for _, row in group.head(5).iterrows():
            lines.append(
                f"- rank {row['rank']}: `{row['perturbation_key']}` "
                f"(score={float(row['score']):.4f})"
            )
        lines.append("")
        if len(lines) > 80:
            break
    lines.extend(
        [
            "## Warnings",
            "",
            "- Raw image thumbnails are shown only when local image files exist.",
            "- Lexical/random/shuffled modes are baselines, not biological evidence.",
            "- Optional embedding mode requires compatible aligned text and image embeddings.",
            "",
        ]
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    return out_path


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(rows)
