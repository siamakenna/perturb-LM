from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from perturb_lm.retrieval.text_profile import (
    build_metadata_text_queries,
    run_text_profile_retrieval,
    run_text_profile_retrieval_multi_seed,
    summarize_multiseed_text_profile_retrieval,
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

    by_seed, aggregate, metadata = run_text_profile_retrieval_multi_seed(
        data_root,
        top_k=[1, 5],
        seeds=[0, 1, 2, 3, 4],
        bootstrap_samples=20,
    )

    aggregate_metrics = set(aggregate["metric"])
    random_map = aggregate.set_index(["mode", "metric"])

    assert metadata["seeds"] == [0, 1, 2, 3, 4]
    assert set(by_seed["seed"]) == {0, 1, 2, 3, 4}
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
