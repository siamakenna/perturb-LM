"""Markdown reporting helpers for Perturb LM outputs."""

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
        (
            "Phase 1 establishes the working retrieval pipeline, perturbation-level "
            "aggregation, metrics, and baselines. It does not prove biological retrieval "
            "without real RxRx data, real embeddings, batch-aware splits, and later "
            "VLM/alignment baselines."
        ),
        "",
        "## Metrics",
        "",
        _markdown_table(metrics),
        "",
        "## Top Retrieval Examples",
        "",
    ]
    ranked_results = perturbation_results.sort_values(["query_id", "rank"])
    for query_id, group in ranked_results.groupby("query_id"):
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


def make_rxrx_readiness_report(
    *,
    dataset: str,
    inventory: dict[str, object],
    out_path: Path,
    manifest_build_report: dict[str, object] | None = None,
    index_metadata: dict[str, object] | None = None,
    leakage_summary: pd.DataFrame | None = None,
    composite_manifest: pd.DataFrame | None = None,
) -> Path:
    """Write a Phase 2 readiness report for local RxRx assets and baseline artifacts."""

    metadata_files = list(inventory.get("metadata_files", []))
    embedding_files = list(inventory.get("embedding_files", []))
    image_file_counts = dict(inventory.get("image_file_counts", {}))
    manifest_paths_checked = int(inventory.get("manifest_image_paths_checked", 0) or 0)
    manifest_paths_found = int(inventory.get("manifest_image_paths_found", 0) or 0)
    manifest_paths_missing = int(inventory.get("manifest_image_paths_missing", 0) or 0)
    image_path_resolution = _ratio(manifest_paths_found, manifest_paths_checked)
    image_count_detail = (
        ", ".join(f"{suffix}: {count}" for suffix, count in image_file_counts.items())
        or "none"
    )
    readiness_rows = [
        {
            "checkpoint": "local metadata discovered",
            "status": _status(bool(metadata_files)),
            "detail": f"{len(metadata_files)} file(s)",
        },
        {
            "checkpoint": "local embeddings discovered",
            "status": _status(bool(embedding_files)),
            "detail": f"{len(embedding_files)} file(s)",
        },
        {
            "checkpoint": "local image files discovered",
            "status": _status(bool(image_file_counts)),
            "detail": image_count_detail,
        },
        {
            "checkpoint": "manifest image paths checked",
            "status": _status(manifest_paths_checked > 0),
            "detail": f"{manifest_paths_found}/{manifest_paths_checked} found",
        },
        {
            "checkpoint": "manifest build report available",
            "status": _status(manifest_build_report is not None),
            "detail": _manifest_report_detail(manifest_build_report),
        },
        {
            "checkpoint": "embedding/index metadata available",
            "status": _status(index_metadata is not None),
            "detail": _index_metadata_detail(index_metadata),
        },
        {
            "checkpoint": "leakage diagnostics available",
            "status": _status(leakage_summary is not None and len(leakage_summary) > 0),
            "detail": _leakage_detail(leakage_summary),
        },
        {
            "checkpoint": "rendered composites available",
            "status": _status(composite_manifest is not None and len(composite_manifest) > 0),
            "detail": _composite_detail(composite_manifest),
        },
    ]
    lines = [
        f"# RxRx Phase 2 Readiness Report: {dataset}",
        "",
        (
            "This report checks whether real local RxRx assets and baseline artifacts can "
            "move through the repo safely. It is a readiness and leakage-control artifact, "
            "not biological evidence."
        ),
        "",
        "## Readiness Checklist",
        "",
        _markdown_table(pd.DataFrame(readiness_rows)),
        "",
        "## Local Asset Inventory",
        "",
        f"- Data root: `{inventory.get('data_root', '')}`",
        f"- Metadata files: {len(metadata_files)}",
        *_bullet_paths(metadata_files),
        f"- Embedding/profile files: {len(embedding_files)}",
        *_bullet_paths(embedding_files),
        f"- Image file counts: {image_file_counts or 'none'}",
        f"- Manifest image paths checked: {manifest_paths_checked}",
        f"- Manifest image paths found: {manifest_paths_found}",
        f"- Manifest image paths missing: {manifest_paths_missing}",
        f"- Manifest image path resolution: {image_path_resolution}",
        "",
    ]
    missing_examples = list(inventory.get("missing_manifest_examples", []))
    if missing_examples:
        lines.extend(["## Missing Image Path Examples", "", *_bullet_paths(missing_examples), ""])
    if manifest_build_report is not None:
        lines.extend(_manifest_build_section(manifest_build_report))
    if index_metadata is not None:
        lines.extend(_index_metadata_section(index_metadata))
    if leakage_summary is not None and len(leakage_summary):
        lines.extend(["## Leakage Summary", "", _markdown_table(leakage_summary), ""])
    if composite_manifest is not None and len(composite_manifest):
        lines.extend(_composite_section(composite_manifest))
    lines.extend(
        [
            "## Interpretation Guardrail",
            "",
            (
                "- Passing this checklist means the local data plumbing and baseline "
                "artifacts are present."
            ),
            "- It does not mean natural-language biological retrieval has been demonstrated.",
            (
                "- Before Phase 3, require at least one real-data baseline with "
                "random/shuffled controls and leakage diagnostics."
            ),
            (
                "- Keep `data/`, `outputs/`, `results/`, embeddings, indexes, model "
                "weights, parquet files, and raw images out of git."
            ),
            "",
        ]
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    return out_path


def make_phase2_jump_report(
    *,
    inventory: dict[str, object],
    index_metadata: dict[str, object],
    diagnostics_summary: pd.DataFrame,
    out_path: Path,
    diagnostics_metadata: dict[str, object] | None = None,
    text_profile_summary: pd.DataFrame | None = None,
) -> Path:
    """Write a reproducible Phase 2 report from local JUMP profile artifacts."""

    metadata_files = _artifact_records(inventory.get("metadata_files_found", []))
    profile_files = _artifact_records(inventory.get("profile_files_found", []))
    diagnostics_metadata = diagnostics_metadata or {}
    warnings = _jump_warnings(inventory, index_metadata, diagnostics_summary, diagnostics_metadata)
    same_treatment = _jump_same_treatment_rows(diagnostics_summary)
    leakage_rows = _jump_leakage_rows(diagnostics_summary)
    overview_rows = [
        {
            "field": "local data root",
            "value": inventory.get(
                "local_data_root",
                index_metadata.get(
                    "local_data_root",
                    diagnostics_metadata.get("local_data_root", ""),
                ),
            ),
        },
        {"field": "metadata files found", "value": len(metadata_files)},
        {"field": "profile files found", "value": len(profile_files)},
        {
            "field": "indexed profile rows",
            "value": _first_present(index_metadata, "number_of_rows", "n_embeddings_loaded"),
        },
        {
            "field": "numeric feature columns",
            "value": _first_present(
                index_metadata,
                "number_of_numeric_feature_columns",
                "embedding_dimension",
            ),
        },
        {
            "field": "batch column",
            "value": _first_present(
                index_metadata,
                "detected_batch_column",
                "likely_batch_column",
            ),
        },
        {
            "field": "plate column",
            "value": _first_present(
                index_metadata,
                "detected_plate_column",
                "likely_plate_column",
            ),
        },
        {
            "field": "well column",
            "value": _first_present(index_metadata, "detected_well_column", "likely_well_column"),
        },
        {
            "field": "same-treatment label",
            "value": _jump_treatment_label(index_metadata, diagnostics_summary),
        },
    ]
    lines = [
        "# Phase 2 JUMP Profile Report",
        "",
        (
            "This report is generated from local JUMP CPJUMP1 inventory, index, and "
            "nearest-neighbor diagnostic artifacts. It is a reproducibility and leakage "
            "diagnostic report, not biological evidence and not a natural-language "
            "retrieval result."
        ),
        "",
        "## Artifact Overview",
        "",
        _markdown_table(pd.DataFrame(overview_rows)),
        "",
        "## Local Inputs",
        "",
        f"- Inventory metadata files: {len(metadata_files)}",
        *_bullet_paths([record.get("path", record) for record in metadata_files]),
        f"- Profile files: {len(profile_files)}",
        *_bullet_paths([record.get("path", record) for record in profile_files]),
        "",
    ]
    if warnings:
        lines.extend(["## Warnings", "", *_jump_warning_bullets(warnings), ""])
    if leakage_rows:
        lines.extend(
            [
                "## Acquisition Leakage Diagnostics",
                "",
                (
                    "Unfiltered nearest-neighbor diagnostics can expose acquisition "
                    "structure such as batch, plate, or well-position effects."
                ),
                "",
                _markdown_table(pd.DataFrame(leakage_rows)),
                "",
            ]
        )
    if same_treatment:
        lines.extend(
            [
                "## Same-Treatment Retrieval",
                "",
                (
                    "Same-treatment retrieval is scored against the configured treatment "
                    "label after aggregating nearest-neighbor behavior at the profile row "
                    "level. Prefer `observed_evaluable` when filters leave some queries "
                    "without positive candidates."
                ),
                "",
                _markdown_table(pd.DataFrame(same_treatment)),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Same-Treatment Retrieval",
                "",
                "No same-treatment diagnostic rows were found in the diagnostics summary.",
                "",
            ]
        )
    text_profile_rows = _jump_text_profile_rows(text_profile_summary)
    if text_profile_rows:
        lines.extend(
            [
                "## Text-To-Profile Metadata Baseline",
                "",
                (
                    "These rows summarize metadata-derived text queries retrieving JUMP "
                    "profile rows with a TF-IDF lexical baseline. This moves the benchmark "
                    "toward text-conditioned retrieval, but it is still a metadata control "
                    "rather than biological image understanding."
                ),
                "",
                _markdown_table(pd.DataFrame(text_profile_rows)),
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation Guardrails",
            "",
            (
                "- Passing this report means local profile artifacts can be audited, "
                "indexed, and evaluated with leakage-aware controls."
            ),
            (
                "- It does not prove biological retrieval, image retrieval, or "
                "natural-language retrieval."
            ),
            (
                "- Report random and shuffled-label controls alongside observed retrieval "
                "metrics."
            ),
            (
                "- Treat same-batch results as non-informative when all rows come from one "
                "batch."
            ),
            (
                "- Keep raw data, profile tables, embeddings, indexes, parquet outputs, "
                "model weights, and generated reports out of git."
            ),
            "",
            "## Recommended Next Checks",
            "",
            "1. Repeat with more plates and, when available, more than one batch.",
            "2. Rebuild this report from the generated artifacts rather than hand-copying tables.",
            (
                "3. Stress-test text-to-profile retrieval across additional batches and "
                "with stronger non-metadata baselines."
            ),
            "4. Add selected image/composite baselines after local image path checks pass.",
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


def _status(ok: bool) -> str:
    return "present" if ok else "missing"


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "not checked"
    return f"{numerator / denominator:.3f}"


def _bullet_paths(paths: list[object], *, limit: int = 8) -> list[str]:
    bullets = [f"  - `{path}`" for path in paths[:limit]]
    if len(paths) > limit:
        bullets.append(f"  - ... ({len(paths) - limit} more)")
    return bullets


def _manifest_report_detail(report: dict[str, object] | None) -> str:
    if report is None:
        return "missing"
    optional = report.get("optional_fields_missing", [])
    source = report.get("source_metadata_file", "")
    return f"source={source}; optional missing={optional or 'none'}"


def _manifest_build_section(report: dict[str, object]) -> list[str]:
    mappings = report.get("column_mappings", {})
    mapping_rows = [
        {"canonical_column": key, "source_column": value or ""}
        for key, value in dict(mappings).items()
    ]
    lines = [
        "## Manifest Build Report",
        "",
        f"- Source metadata file: `{report.get('source_metadata_file', '')}`",
        f"- Raw rows: {report.get('n_raw_rows', '')}",
        f"- Optional fields missing: {report.get('optional_fields_missing', []) or 'none'}",
        f"- Required fields missing: {report.get('required_fields_missing', []) or 'none'}",
        "",
    ]
    if mapping_rows:
        lines.extend(["### Column Mappings", "", _markdown_table(pd.DataFrame(mapping_rows)), ""])
    return lines


def _index_metadata_detail(metadata: dict[str, object] | None) -> str:
    if metadata is None:
        return "missing"
    dimension = metadata.get(
        "embedding_dimension",
        metadata.get("number_of_numeric_feature_columns", ""),
    )
    return (
        f"rows={metadata.get('n_embeddings_loaded', metadata.get('number_of_rows', ''))}; "
        f"dim={dimension}"
    )


def _index_metadata_section(metadata: dict[str, object]) -> list[str]:
    rows = [
        {"field": key, "value": value}
        for key, value in metadata.items()
        if key
        in {
            "dataset",
            "backend",
            "metric",
            "id_column",
            "n_embeddings_loaded",
            "embedding_dimension",
            "n_matched_to_manifest",
            "n_unmatched",
            "number_of_rows",
            "number_of_numeric_feature_columns",
        }
    ]
    return ["## Embedding/Index Metadata", "", _markdown_table(pd.DataFrame(rows)), ""]


def _leakage_detail(summary: pd.DataFrame | None) -> str:
    if summary is None or summary.empty:
        return "missing"
    if {"metric", "value"}.issubset(summary.columns):
        metrics = dict(zip(summary["metric"], summary["value"], strict=False))
        return (
            f"queries={metrics.get('n_queries', '')}; "
            f"cross_batch={metrics.get('queries_with_positive_cross_batch', '')}; "
            f"cross_plate={metrics.get('queries_with_positive_cross_plate', '')}; "
            f"cross_split={metrics.get('queries_with_positive_cross_split', '')}"
        )
    return f"{len(summary)} row(s)"


def _composite_detail(composites: pd.DataFrame | None) -> str:
    if composites is None or composites.empty:
        return "missing"
    if "composite_status" not in composites.columns:
        return f"{len(composites)} row(s)"
    counts = composites["composite_status"].value_counts().to_dict()
    return str(counts)


def _composite_section(composites: pd.DataFrame) -> list[str]:
    lines = ["## Composite Rendering Summary", "", _composite_detail(composites), ""]
    if "composite_status" in composites.columns:
        counts = (
            composites["composite_status"]
            .value_counts()
            .rename_axis("status")
            .reset_index(name="count")
        )
        lines.extend([_markdown_table(counts), ""])
    return lines


def _artifact_records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    records = []
    for item in value:
        if isinstance(item, dict):
            records.append(item)
        else:
            records.append({"path": item})
    return records


def _first_present(payload: dict[str, object], *keys: str) -> object:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return ""


def _jump_treatment_label(index_metadata: dict[str, object], summary: pd.DataFrame) -> object:
    treatment_columns = index_metadata.get("detected_perturbation_treatment_columns")
    if isinstance(treatment_columns, list) and treatment_columns:
        return treatment_columns[0]
    if {
        "diagnostic",
        "label_column",
    }.issubset(summary.columns):
        labels = summary.loc[
            summary["diagnostic"].astype(str) == "perturbation_treatment",
            "label_column",
        ].dropna()
        if len(labels):
            return labels.iloc[0]
    return ""


def _jump_warnings(
    inventory: dict[str, object],
    index_metadata: dict[str, object],
    summary: pd.DataFrame,
    diagnostics_metadata: dict[str, object],
) -> list[str]:
    warnings: list[str] = []
    for source in (inventory, index_metadata, diagnostics_metadata):
        value = source.get("warnings")
        if isinstance(value, list):
            warnings.extend(str(item) for item in value if str(item))
        elif isinstance(value, str) and value:
            warnings.append(value)
    if "warning" in summary.columns:
        warnings.extend(str(item) for item in summary["warning"].dropna().unique() if str(item))
    return list(dict.fromkeys(warnings))


def _jump_warning_bullets(warnings: list[str], *, limit: int = 8) -> list[str]:
    bullets = [f"- {warning}" for warning in warnings[:limit]]
    if len(warnings) > limit:
        bullets.append(f"- ... ({len(warnings) - limit} more)")
    return bullets


def _jump_leakage_rows(summary: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for diagnostic in ("batch", "plate", "well"):
        observed = _jump_metric_row(summary, diagnostic, f"same_{diagnostic}_at_1", "unfiltered")
        if observed is None:
            continue
        random = _jump_metric_row(
            summary,
            diagnostic,
            f"random_same_{diagnostic}_at_1",
            "unfiltered",
        )
        shuffled = _jump_metric_row(
            summary,
            diagnostic,
            f"shuffled_same_{diagnostic}_at_1",
            "unfiltered",
        )
        rows.append(
            {
                "diagnostic": diagnostic,
                "label_column": _jump_cell(observed, "label_column"),
                "observed@1": _fmt_metric(_jump_cell(observed, "value_evaluable_queries")),
                "random@1": _fmt_metric(_jump_cell(random, "value_evaluable_queries")),
                "shuffled@1": _fmt_metric(_jump_cell(shuffled, "value_evaluable_queries")),
                "evaluable_queries": _fmt_count(_jump_cell(observed, "n_evaluable_queries")),
                "warning": _jump_cell(observed, "warning"),
            }
        )
    return rows


def _jump_same_treatment_rows(summary: pd.DataFrame) -> list[dict[str, object]]:
    if not {"diagnostic", "metric", "filter_name"}.issubset(summary.columns):
        return []
    observed_rows = summary[
        (summary["diagnostic"].astype(str) == "perturbation_treatment")
        & summary["metric"].astype(str).str.startswith("same_perturbation_treatment_at_")
    ].copy()
    if observed_rows.empty:
        return []
    observed_rows["_sort_k"] = observed_rows["k"].map(_as_int) if "k" in observed_rows else 0
    observed_rows["_sort_filter"] = observed_rows["filter_name"].map(_filter_sort_key)
    observed_rows = observed_rows.sort_values(["_sort_filter", "_sort_k"])
    rows: list[dict[str, object]] = []
    for _, observed in observed_rows.iterrows():
        metric = str(observed["metric"])
        filter_name = str(observed["filter_name"])
        k = _as_int(observed.get("k")) or _metric_k(metric)
        suffix = f"_at_{k}"
        random = _jump_metric_row(
            summary,
            "perturbation_treatment",
            f"random_same_perturbation_treatment{suffix}",
            filter_name,
        )
        shuffled = _jump_metric_row(
            summary,
            "perturbation_treatment",
            f"shuffled_same_perturbation_treatment{suffix}",
            filter_name,
        )
        rows.append(
            {
                "filter": filter_name,
                "k": k,
                "label_column": _jump_cell(observed, "label_column"),
                "observed_all": _fmt_metric(_jump_cell(observed, "value_all_queries")),
                "observed_evaluable": _fmt_metric(
                    _jump_cell(observed, "value_evaluable_queries")
                ),
                "random_evaluable": _fmt_metric(_jump_cell(random, "value_evaluable_queries")),
                "shuffled_evaluable": _fmt_metric(
                    _jump_cell(shuffled, "value_evaluable_queries")
                ),
                "evaluable_queries": _fmt_count(_jump_cell(observed, "n_evaluable_queries")),
                "median_candidates": _fmt_count(
                    _jump_cell(observed, "n_candidates_after_filter_median")
                ),
            }
        )
    return rows


def _jump_text_profile_rows(summary: pd.DataFrame | None) -> list[dict[str, object]]:
    if summary is None or summary.empty or not {"mode", "metric", "value"}.issubset(
        summary.columns
    ):
        return []
    wanted = [
        "n_queries",
        "n_evaluable_queries",
        "mean_average_precision",
        "mean_hit_at_1",
        "mean_hit_at_5",
        "mean_hit_at_10",
        "queries_with_positive_cross_batch",
        "queries_with_positive_cross_plate",
        "queries_with_positive_cross_well",
    ]
    rows: list[dict[str, object]] = []
    for mode in ["metadata_tfidf", "identifier_stripped_tfidf", "random", "shuffled_label"]:
        mode_summary = summary[summary["mode"].astype(str) == mode]
        if mode_summary.empty:
            continue
        metrics = {
            str(row["metric"]): row["value"]
            for _, row in mode_summary.iterrows()
            if str(row["metric"]) in wanted
        }
        rows.append(
            {
                "mode": mode,
                "queries": _fmt_count(metrics.get("n_queries", "")),
                "evaluable": _fmt_count(metrics.get("n_evaluable_queries", "")),
                "mAP": _fmt_metric(metrics.get("mean_average_precision", "")),
                "hit@1": _fmt_metric(metrics.get("mean_hit_at_1", "")),
                "hit@5": _fmt_metric(metrics.get("mean_hit_at_5", "")),
                "hit@10": _fmt_metric(metrics.get("mean_hit_at_10", "")),
                "cross_batch_pos_queries": _fmt_count(
                    metrics.get("queries_with_positive_cross_batch", "")
                ),
                "cross_plate_pos_queries": _fmt_count(
                    metrics.get("queries_with_positive_cross_plate", "")
                ),
                "cross_well_pos_queries": _fmt_count(
                    metrics.get("queries_with_positive_cross_well", "")
                ),
            }
        )
    return rows


def _jump_metric_row(
    summary: pd.DataFrame,
    diagnostic: str,
    metric: str,
    filter_name: str,
) -> pd.Series | None:
    if not {"diagnostic", "metric", "filter_name"}.issubset(summary.columns):
        return None
    matches = summary[
        (summary["diagnostic"].astype(str) == diagnostic)
        & (summary["metric"].astype(str) == metric)
        & (summary["filter_name"].astype(str) == filter_name)
    ]
    if matches.empty:
        return None
    return matches.iloc[0]


def _jump_cell(row: pd.Series | None, column: str) -> object:
    if row is None or column not in row.index:
        return ""
    value = row[column]
    if pd.isna(value):
        return ""
    return value


def _filter_sort_key(value: object) -> int:
    order = {
        "unfiltered": 0,
        "exclude_same_plate": 1,
        "exclude_same_well": 2,
        "exclude_same_plate_and_well": 3,
    }
    return order.get(str(value), 99)


def _metric_k(metric: str) -> int | str:
    try:
        return int(metric.rsplit("_at_", 1)[1])
    except (IndexError, ValueError):
        return ""


def _as_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return int(float(value))


def _fmt_metric(value: object) -> str:
    if value in (None, ""):
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return f"{float(value):.4f}"


def _fmt_count(value: object) -> str:
    if value in (None, ""):
        return ""
    try:
        if pd.isna(value):
            return ""
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return str(value)
