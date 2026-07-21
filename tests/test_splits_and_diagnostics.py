from __future__ import annotations

import pandas as pd
import pytest

from perturb_lm.diagnostics import (
    query_positive_leakage_diagnostics,
    summarize_leakage_diagnostics,
)
from perturb_lm.engineering.summaries import build_query_leakage_dashboard_summary
from perturb_lm.queries.build_queries import build_queries
from perturb_lm.splits import (
    assign_held_out_batch_split,
    assign_held_out_perturbation_split,
    assign_held_out_plate_split,
    assign_held_out_well_split,
)
from scripts.build_rxrx_manifests import build_manifests


def test_batch_aware_split_helpers_keep_groups_together(tmp_path) -> None:
    site_manifest, perturbations = build_manifests("rxrx1", "tests/fixtures", tmp_path)

    by_well = assign_held_out_well_split(site_manifest, test_fraction=0.5, seed=1)
    assert by_well.groupby(["experiment", "plate", "well"])["split"].nunique().max() == 1
    assert "test" in set(by_well["split"])

    by_plate = assign_held_out_plate_split(site_manifest, test_fraction=0.5, seed=1)
    assert by_plate.groupby(["experiment", "plate"])["split"].nunique().max() == 1

    by_batch = assign_held_out_batch_split(site_manifest, test_fraction=0.5, seed=1)
    assert by_batch.groupby("experiment")["split"].nunique().max() == 1

    by_perturbation = assign_held_out_perturbation_split(
        site_manifest,
        test_fraction=0.5,
        seed=1,
    )
    assert by_perturbation.groupby("perturbation_id")["split"].nunique().max() == 1
    assert len(perturbations) == 2


def test_held_out_perturbation_split_requires_labels() -> None:
    with pytest.raises(ValueError, match="perturbation_key"):
        assign_held_out_perturbation_split(pd.DataFrame({"site_id": ["s1"]}))


def test_query_positive_leakage_diagnostics_flag_cross_split_positives(tmp_path) -> None:
    site_manifest, perturbations = build_manifests("rxrx1", "tests/fixtures", tmp_path)
    duplicate = site_manifest.iloc[[0]].copy()
    duplicate["site_id"] = "rxrx1::exp3::plate9::A01::1"
    duplicate["experiment"] = "exp3"
    duplicate["plate"] = "plate9"
    duplicate["split"] = "test"
    site_manifest = pd.concat([site_manifest, duplicate], ignore_index=True)
    queries = build_queries("rxrx1", perturbations)

    diagnostics = query_positive_leakage_diagnostics(queries, site_manifest)
    summary = summarize_leakage_diagnostics(diagnostics)

    first_positive = diagnostics[diagnostics["n_positive_sites"] == 3].iloc[0]
    assert first_positive["positive_cross_batch"]
    assert first_positive["positive_cross_plate"]
    assert first_positive["positive_cross_split"]
    assert summary.set_index("metric").loc["queries_with_positive_cross_batch", "value"] > 0
    dashboard = build_query_leakage_dashboard_summary(summary, dataset="rxrx1")
    dashboard_metrics = {row["metric"]: row for row in dashboard["metrics"]}
    assert dashboard["report_type"] == "dashboard_query_leakage_summary"
    assert dashboard_metrics["queries_with_positive_cross_batch"]["count"] > 0
    assert "positive_batches" not in str(dashboard)
