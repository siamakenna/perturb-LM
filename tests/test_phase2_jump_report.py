from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd

from perturb_lm.reports import make_phase2_jump_report


def text_profile_summary_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"mode": "metadata_tfidf", "metric": "n_queries", "value": 2},
            {"mode": "metadata_tfidf", "metric": "n_evaluable_queries", "value": 2},
            {"mode": "metadata_tfidf", "metric": "mean_average_precision", "value": 0.9},
            {"mode": "metadata_tfidf", "metric": "mean_hit_at_1", "value": 1.0},
            {"mode": "metadata_tfidf", "metric": "mean_hit_at_5", "value": 1.0},
            {"mode": "metadata_tfidf", "metric": "mean_hit_at_10", "value": 1.0},
            {
                "mode": "metadata_tfidf",
                "metric": "queries_with_positive_cross_plate",
                "value": 2,
            },
            {"mode": "random", "metric": "n_queries", "value": 2},
            {"mode": "random", "metric": "n_evaluable_queries", "value": 2},
            {"mode": "random", "metric": "mean_average_precision", "value": 0.1},
            {"mode": "random", "metric": "mean_hit_at_1", "value": 0.0},
            {"mode": "random", "metric": "mean_hit_at_5", "value": 0.5},
            {"mode": "random", "metric": "mean_hit_at_10", "value": 0.5},
        ]
    )


def jump_summary_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "diagnostic": "batch",
                "metric": "same_batch_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 1.0,
                "n_evaluable_queries": 4,
                "label_column": "Metadata_Batch",
                "warning": "Same-batch diagnostics are not informative.",
            },
            {
                "diagnostic": "batch",
                "metric": "random_same_batch_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 1.0,
            },
            {
                "diagnostic": "batch",
                "metric": "shuffled_same_batch_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 1.0,
            },
            {
                "diagnostic": "plate",
                "metric": "same_plate_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 0.75,
                "n_evaluable_queries": 4,
                "label_column": "Metadata_Plate",
            },
            {
                "diagnostic": "plate",
                "metric": "random_same_plate_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 0.25,
            },
            {
                "diagnostic": "plate",
                "metric": "shuffled_same_plate_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 0.25,
            },
            {
                "diagnostic": "well",
                "metric": "same_well_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 0.50,
                "n_evaluable_queries": 4,
                "label_column": "Metadata_Well",
            },
            {
                "diagnostic": "well",
                "metric": "random_same_well_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 0.10,
            },
            {
                "diagnostic": "well",
                "metric": "shuffled_same_well_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 0.10,
            },
            {
                "diagnostic": "perturbation_treatment",
                "metric": "same_perturbation_treatment_at_1",
                "filter_name": "unfiltered",
                "value_all_queries": 0.50,
                "value_evaluable_queries": 0.50,
                "n_evaluable_queries": 4,
                "n_candidates_after_filter_median": 3,
                "label_column": "Metadata_broad_sample",
                "k": 1,
            },
            {
                "diagnostic": "perturbation_treatment",
                "metric": "random_same_perturbation_treatment_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 0.05,
                "k": 1,
            },
            {
                "diagnostic": "perturbation_treatment",
                "metric": "shuffled_same_perturbation_treatment_at_1",
                "filter_name": "unfiltered",
                "value_evaluable_queries": 0.02,
                "k": 1,
            },
            {
                "diagnostic": "perturbation_treatment",
                "metric": "same_perturbation_treatment_at_1",
                "filter_name": "exclude_same_plate_and_well",
                "value_all_queries": 0.25,
                "value_evaluable_queries": 0.33,
                "n_evaluable_queries": 3,
                "n_candidates_after_filter_median": 2,
                "label_column": "Metadata_broad_sample",
                "k": 1,
            },
            {
                "diagnostic": "perturbation_treatment",
                "metric": "random_same_perturbation_treatment_at_1",
                "filter_name": "exclude_same_plate_and_well",
                "value_evaluable_queries": 0.03,
                "k": 1,
            },
            {
                "diagnostic": "perturbation_treatment",
                "metric": "shuffled_same_perturbation_treatment_at_1",
                "filter_name": "exclude_same_plate_and_well",
                "value_evaluable_queries": 0.01,
                "k": 1,
            },
        ]
    )


def test_make_phase2_jump_report_summarizes_diagnostics(tmp_path) -> None:
    inventory = {
        "local_data_root": "data/raw/jump_pilot",
        "metadata_files_found": [{"path": "metadata/experiment-metadata.tsv"}],
        "profile_files_found": [{"path": "profiles/batch/plate.csv.gz"}],
        "warnings": ["fixture warning"],
    }
    index_metadata = {
        "number_of_rows": 4,
        "number_of_numeric_feature_columns": 2,
        "detected_batch_column": "Metadata_Batch",
        "detected_plate_column": "Metadata_Plate",
        "detected_well_column": "Metadata_Well",
        "detected_perturbation_treatment_columns": ["Metadata_broad_sample"],
    }

    out = make_phase2_jump_report(
        inventory=inventory,
        index_metadata=index_metadata,
        diagnostics_summary=jump_summary_fixture(),
        diagnostics_metadata={"warnings": ["metadata warning"]},
        text_profile_summary=text_profile_summary_fixture(),
        out_path=tmp_path / "jump_report.md",
    )

    text = out.read_text()
    assert "Phase 2 JUMP Profile Report" in text
    assert "Metadata_broad_sample" in text
    assert "exclude_same_plate_and_well" in text
    assert "0.3300" in text
    assert "Text-To-Profile Metadata Baseline" in text
    assert "metadata_tfidf" in text
    assert "not biological evidence" in text
    assert "fixture warning" in text


def test_make_phase2_jump_report_cli_reads_artifacts(tmp_path) -> None:
    inventory = tmp_path / "inventory.json"
    index_metadata = tmp_path / "index_metadata.json"
    summary = tmp_path / "summary.csv"
    diagnostics_json = tmp_path / "summary.json"
    text_profile_summary = tmp_path / "text_profile_summary.csv"
    out = tmp_path / "report.md"
    inventory.write_text(
        json.dumps(
            {
                "metadata_files_found": [{"path": "metadata.tsv"}],
                "profile_files_found": [{"path": "profiles.csv.gz"}],
            }
        )
    )
    index_metadata.write_text(
        json.dumps(
            {
                "number_of_rows": 4,
                "number_of_numeric_feature_columns": 2,
                "detected_perturbation_treatment_columns": ["Metadata_broad_sample"],
            }
        )
    )
    jump_summary_fixture().to_csv(summary, index=False)
    text_profile_summary_fixture().to_csv(text_profile_summary, index=False)
    diagnostics_json.write_text(json.dumps({"metadata": {"warnings": ["json warning"]}}))

    subprocess.run(
        [
            sys.executable,
            "scripts/make_phase2_jump_report.py",
            "--inventory",
            str(inventory),
            "--index-metadata",
            str(index_metadata),
            "--diagnostics-summary",
            str(summary),
            "--diagnostics-json",
            str(diagnostics_json),
            "--text-profile-summary",
            str(text_profile_summary),
            "--out",
            str(out),
        ],
        check=True,
    )

    payload = out.read_text()
    assert "Phase 2 JUMP Profile Report" in payload
    assert "json warning" in payload
    assert "Same-Treatment Retrieval" in payload
    assert "Text-To-Profile Metadata Baseline" in payload
