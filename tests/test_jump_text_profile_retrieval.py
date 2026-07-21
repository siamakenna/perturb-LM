from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from perturb_lm.retrieval.text_profile import (
    IDENTIFIER_STRIPPED_TEXT_COLUMN_CANDIDATES,
    build_metadata_text_queries,
    run_text_profile_retrieval,
    run_text_profile_retrieval_multi_seed,
    select_text_profile_queries,
    summarize_multiseed_text_profile_retrieval,
    summarize_query_bootstrap,
)


def write_text_profile_fixture(data_root: Path) -> Path:
    profile_dir = data_root / "profiles" / "2020_11_04_CPJUMP1" / "BR001"
    profile_dir.mkdir(parents=True)
    profile_path = profile_dir / "BR001_normalized_feature_select_negcon_batch.csv.gz"
    pd.DataFrame(
        {
            "Metadata_Batch": ["batch-1"] * 6,
            "Metadata_Plate": ["BR001", "BR002", "BR003", "BR001", "BR002", "BR003"],
            "Metadata_Well": ["A01", "A01", "A01", "B01", "B01", "B01"],
            "Metadata_broad_sample": ["BRD-A", "BRD-A", "BRD-A", "BRD-B", "BRD-B", "BRD-B"],
            "Metadata_pert_iname": [
                "compound alpha",
                "compound alpha",
                "compound alpha",
                "compound beta",
                "compound beta",
                "compound beta",
            ],
            "Metadata_gene": ["GENE_A", "GENE_A", "GENE_A", "GENE_B", "GENE_B", "GENE_B"],
            "Metadata_pert_type": ["trt_cp"] * 6,
            "Metadata_target_sequence": [
                "ATGCGTACGTAGCTAGCTAA",
                "ATGCGTACGTAGCTAGCTAA",
                "ATGCGTACGTAGCTAGCTAA",
                "CGTACGATCGATCGTACGTA",
                "CGTACGATCGATCGTACGTA",
                "CGTACGATCGATCGTACGTA",
            ],
            "Cells_AreaShape_Area": [1.0, 0.9, 0.8, 0.1, 0.2, 0.3],
            "Nuclei_Texture_Info": [0.1, 0.2, 0.3, 1.0, 0.9, 0.8],
        }
    ).to_csv(profile_path, index=False)
    return profile_path


def test_build_metadata_text_queries_from_profile_labels(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_text_profile_fixture(data_root)
    profiles = pd.read_csv(next(data_root.rglob("*.csv.gz")))

    queries = build_metadata_text_queries(
        profiles,
        label_column="Metadata_broad_sample",
    )

    assert queries["target_label"].tolist() == ["BRD-A", "BRD-B"]
    assert "compound alpha" in queries.iloc[0]["query_text"]
    assert queries.iloc[0]["mechanism_query_text"] == "cells with perturbation of GENE_A"
    assert set(queries["label_column"]) == {"Metadata_broad_sample"}


def test_run_text_profile_retrieval_scores_metadata_baseline_and_controls(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_text_profile_fixture(data_root)

    per_query, hits, summary, metadata = run_text_profile_retrieval(
        data_root,
        top_k=[1, 3],
        seed=4,
    )
    summary_metrics = summary.set_index(["mode", "metric"])["value"]
    observed = per_query[per_query["mode"] == "metadata_tfidf"]
    stripped = per_query[per_query["mode"] == "identifier_stripped_tfidf"]

    assert metadata["label_column"] == "Metadata_broad_sample"
    assert any(
        "metadata-derived lexical text-to-profile baseline" in warning
        for warning in metadata["warnings"]
    )
    assert set(per_query["mode"]) == {
        "metadata_tfidf",
        "identifier_stripped_tfidf",
        "random",
        "shuffled_label",
    }
    assert float(summary_metrics.loc[("metadata_tfidf", "mean_hit_at_1")]) == 1.0
    assert float(summary_metrics.loc[("identifier_stripped_tfidf", "mean_hit_at_1")]) == 1.0
    assert float(summary_metrics.loc[("metadata_tfidf", "queries_with_positive_cross_plate")]) == 2
    assert observed["n_positive_plates"].tolist() == [3, 3]
    assert stripped["scored_query_text"].tolist() == [
        "cells with perturbation of GENE_A",
        "cells with perturbation of GENE_B",
    ]
    assert hits[hits["mode"] == "metadata_tfidf"].groupby("query_id").head(1)[
        "is_positive"
    ].all()


def test_run_jump_text_profile_retrieval_cli_writes_outputs(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_text_profile_fixture(data_root)
    out = tmp_path / "text_profile"

    subprocess.run(
        [
            sys.executable,
            "scripts/run_jump_text_profile_retrieval.py",
            "--data-root",
            str(data_root),
            "--out",
            str(out),
            "--top-k",
            "1",
            "3",
        ],
        check=True,
    )

    assert (out / "jump_text_profile_queries.csv").exists()
    assert (out / "jump_text_profile_per_query.csv").exists()
    assert (out / "jump_text_profile_summary.csv").exists()
    metadata = json.loads((out / "jump_text_profile_metadata.json").read_text())
    assert metadata["number_of_queries"] == 2
    assert "identifier_stripped_tfidf" in metadata["modes"]


def test_run_text_profile_retrieval_multi_seed_reports_stability_and_enrichment(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_text_profile_fixture(data_root)

    by_seed, aggregate, bootstrap, metadata = run_text_profile_retrieval_multi_seed(
        data_root,
        top_k=[1, 5],
        seeds=[0, 1, 2, 3, 4],
        bootstrap_samples=20,
    )

    aggregate_metrics = set(aggregate["metric"])
    random_map = aggregate.set_index(["mode", "metric"])

    assert metadata["seeds"] == [0, 1, 2, 3, 4]
    assert set(by_seed["seed"]) == {0, 1, 2, 3, 4}
    assert not bootstrap.empty
    assert "enrichment_over_random::mean_average_precision" in aggregate_metrics
    assert "n_evaluable_queries" in aggregate_metrics
    assert random_map.loc[("random", "n_evaluable_queries"), "mean"] == 2.0
    assert {
        "mean",
        "std",
        "min",
        "max",
        "median",
        "ci95_low",
        "ci95_high",
    }.issubset(aggregate.columns)


def test_run_jump_text_profile_retrieval_cli_writes_multiseed_outputs(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_text_profile_fixture(data_root)
    out = tmp_path / "text_profile_multiseed"

    subprocess.run(
        [
            sys.executable,
            "scripts/run_jump_text_profile_retrieval.py",
            "--data-root",
            str(data_root),
            "--out",
            str(out),
            "--top-k",
            "1",
            "5",
            "--seeds",
            "0",
            "1",
            "2",
        ],
        check=True,
    )

    assert (out / "jump_text_profile_summary_by_seed.csv").exists()
    assert (out / "jump_text_profile_multiseed_summary.csv").exists()
    metadata = json.loads((out / "jump_text_profile_multiseed_metadata.json").read_text())
    assert metadata["seed_count"] == 3
    assert (out / "jump_text_profile_query_bootstrap_summary.csv").exists()


def test_multiseed_summary_handles_unavailable_metrics_and_query_count_changes() -> None:
    by_seed = pd.DataFrame(
        {
            "seed": [0, 1, 2, 0, 1, 2],
            "mode": ["random", "random", "random", "random", "random", "random"],
            "metric": [
                "mean_average_precision",
                "mean_average_precision",
                "mean_average_precision",
                "n_evaluable_queries",
                "n_evaluable_queries",
                "n_evaluable_queries",
            ],
            "value": [0.1, float("nan"), 0.3, 2, 1, 3],
        }
    )

    aggregate = summarize_multiseed_text_profile_retrieval(by_seed, bootstrap_samples=10)
    by_metric = aggregate.set_index("metric")

    assert by_metric.loc["mean_average_precision", "finite_seed_count"] == 2
    assert by_metric.loc["mean_average_precision", "mean"] == 0.2
    assert by_metric.loc["n_evaluable_queries", "min"] == 1.0
    assert by_metric.loc["n_evaluable_queries", "max"] == 3.0


def test_identifier_stripped_text_excludes_target_sequences(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_text_profile_fixture(data_root)

    per_query, _, _, metadata = run_text_profile_retrieval(data_root, top_k=[1])
    stripped = per_query[per_query["mode"] == "identifier_stripped_tfidf"]

    assert "Metadata_target_sequence" not in IDENTIFIER_STRIPPED_TEXT_COLUMN_CANDIDATES
    assert "Metadata_target_sequence" not in metadata["identifier_stripped_text_columns"]
    assert "ATGCGTACGTAGCTAGCTAA" not in " ".join(stripped["scored_query_text"].astype(str))


def test_identifier_stripped_query_with_sequence_value_fails(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_text_profile_fixture(data_root)
    queries = pd.DataFrame(
        {
            "query_id": ["q1"],
            "query_text": ["cells with perturbation of GENE_A"],
            "mechanism_query_text": ["cells matching ATGCGTACGTAGCTAGCTAA"],
            "target_label": ["BRD-A"],
            "label_column": ["Metadata_broad_sample"],
        }
    )

    with pytest.raises(ValueError, match="Prohibited identifier value"):
        run_text_profile_retrieval(data_root, queries=queries, top_k=[1])


def test_query_selection_is_deterministic_and_not_order_biased() -> None:
    queries = pd.DataFrame(
        {
            "query_id": [f"q{i:02d}" for i in range(12)],
            "query_text": ["x"] * 12,
            "target_label": [f"label-{i:02d}" for i in range(12)],
            "label_column": ["label"] * 12,
            "perturbation_type_stratum": ["a", "b", "c"] * 4,
            "control_status_stratum": ["control", "non_control"] * 6,
            "replicate_count_bin": ["2-3", "4-10", "11+"] * 4,
            "plate_coverage_bin": ["1", "2-3"] * 6,
            "treatment_label_available": [True] * 12,
        }
    )
    shuffled = queries.sample(frac=1, random_state=3).reset_index(drop=True)

    selected_a, report_a = select_text_profile_queries(
        queries,
        query_limit=6,
        mode="stratified",
        seed=7,
    )
    selected_b, report_b = select_text_profile_queries(
        shuffled,
        query_limit=6,
        mode="stratified",
        seed=7,
    )
    selected_c, _ = select_text_profile_queries(
        queries,
        query_limit=6,
        mode="random",
        seed=8,
    )
    all_queries, _ = select_text_profile_queries(queries, query_limit=None, mode="all", seed=0)

    assert selected_a["query_id"].tolist() == selected_b["query_id"].tolist()
    assert report_a["selection_checksum"] == report_b["selection_checksum"]
    assert selected_a["query_id"].tolist() != sorted(queries["query_id"].tolist())[:5]
    assert selected_a["query_id"].tolist() != selected_c["query_id"].tolist()
    assert len(all_queries) == len(queries)


def test_stratified_query_selection_fails_when_limit_smaller_than_strata() -> None:
    queries = pd.DataFrame(
        {
            "query_id": [f"q{i:02d}" for i in range(6)],
            "query_text": ["x"] * 6,
            "target_label": [f"label-{i:02d}" for i in range(6)],
            "label_column": ["label"] * 6,
            "perturbation_type_stratum": [f"type-{i}" for i in range(6)],
            "control_status_stratum": ["non_control"] * 6,
            "replicate_count_bin": ["1"] * 6,
            "plate_coverage_bin": ["1"] * 6,
            "treatment_label_available": [True] * 6,
        }
    )

    with pytest.raises(ValueError, match="at least the number of available strata"):
        select_text_profile_queries(queries, query_limit=3, mode="stratified", seed=0)


def test_query_bootstrap_reports_paired_differences_reproducibly() -> None:
    per_query = pd.DataFrame(
        {
            "seed": [0, 0, 0, 0, 0, 0],
            "mode": [
                "identifier_stripped_tfidf",
                "identifier_stripped_tfidf",
                "identifier_stripped_tfidf",
                "random",
                "random",
                "random",
            ],
            "query_id": ["q1", "q2", "q3", "q1", "q2", "q3"],
            "n_positives": [1, 1, 0, 1, 1, 0],
            "average_precision": [1.0, 0.5, np.nan, 0.1, 0.2, np.nan],
            "hit_at_1": [1.0, 0.0, np.nan, 0.0, 0.0, np.nan],
            "hit_at_5": [1.0, 1.0, np.nan, 0.0, 1.0, np.nan],
            "hit_at_10": [1.0, 1.0, np.nan, 1.0, 1.0, np.nan],
            "recall_at_1": [1.0, 0.0, np.nan, 0.0, 0.0, np.nan],
            "recall_at_5": [1.0, 1.0, np.nan, 0.0, 1.0, np.nan],
            "recall_at_10": [1.0, 1.0, np.nan, 1.0, 1.0, np.nan],
        }
    )

    first = summarize_query_bootstrap(per_query, top_k=[1, 5, 10], bootstrap_samples=20, seed=4)
    second = summarize_query_bootstrap(per_query, top_k=[1, 5, 10], bootstrap_samples=20, seed=4)

    assert first.to_dict("records") == second.to_dict("records")
    assert "paired_difference_vs_identifier_stripped_tfidf" in set(first["comparison"])
    point = first[
        (first["mode"] == "identifier_stripped_tfidf")
        & (first["comparison"] == "point_estimate")
        & (first["metric"] == "average_precision")
    ].iloc[0]
    assert point["n_queries"] == 3
    assert point["n_evaluable_queries"] == 2
